# 10. Document Processing

## 0. Milestone 08/09 Implementation Status
Milestone 08/09 (`app/services/ingestion_service.py`, `app/pipelines/document_extractor.py`,
`app/pipelines/ocr_pipeline.py`, `app/routers/documents.py`) implements **Upload -> Extract (+ OCR)**:
* PDF (text-based, via PyMuPDF), DOCX (via python-docx), and TXT (via chardet) are fully extracted synchronously during the upload request.
* Images (PNG/JPG/JPEG/WEBP/TIFF/GIF/BMP) and scanned/image PDFs are processed through the Milestone 09 OCR pipeline (`app/pipelines/ocr_pipeline.py`) when Tesseract is installed: pre-processing (grayscale, Otsu threshold, deskew, 300 DPI scaling), Tesseract OCR (PSM 3, OEM 3), post-processing (dehyphenation, orphan-character join, words below 40% confidence dropped), and an average confidence score. Low-confidence results (< 60%) are kept but flagged with a warning in `error_message`.
* When Tesseract is unavailable the pipeline degrades gracefully: images and scanned PDFs land in `status="pending_ocr"` with a clear `error_message` telling the user to install Tesseract, while text-based PDFs, DOCX, and TXT keep working normally. `pending_ocr` is an intentional, documented use of the degradation path described in Section 19, using a distinct status value instead of the generic `error` so the UI can distinguish "expected, dependency missing" from a real failure.
* Chunking, the embedding queue, ChromaDB indexing, and the `chunking -> queuing -> indexing -> indexed` statuses described below are introduced in Milestones 10/11 and do not exist yet. `chunk_count` stays `0` and `indexed_at` stays `null` until then.
* Extraction (including OCR) currently runs inline on the upload request (via `asyncio.to_thread` to avoid blocking the event loop) rather than through a background queue, since there is no embedding step yet to justify one. The APScheduler-based queue arrives with the embedder in Milestone 10.

## 1. Document Processing Overview
The Document Processing pipeline in Atlas is responsible for taking raw user uploads and transforming them into searchable, semantic chunks stored in ChromaDB, while updating the Knowledge Graph.
**Five Stages**: Upload → Extract → OCR (if needed) → Chunk → Embed.

## 2. Supported File Types
Validated via MIME types upon upload:
*   **PDF (text & image)**: `application/pdf`
*   **DOCX**: `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
*   **TXT**: `text/plain`
*   **Images**: `image/png`, `image/jpeg`, `image/webp`, `image/tiff`

## 3. File Upload Flow
1.  **Endpoint**: `POST /api/v1/profiles/{pid}/documents` (multipart/form-data)
2.  **Staging**: File is temporarily saved to `~/.atlas/temp/uploads/`.
3.  **Hashing**: A SHA-256 hash of the file content is computed.
4.  **Deduplication**: If the hash exists in the `documents` table for this profile, the upload is rejected as a duplicate.
5.  **Storage**: Moved to `~/.atlas/profiles/{pid}/documents/raw/{uuid}_{filename}`.
6.  **Database**: Record created in SQLite `documents` with status `pending`.

## 4. File Type Detection
MIME types provided by the browser are untrusted. The backend verifies the file type using the first few bytes (magic numbers) via `python-magic` (or Python's built-in `mimetypes` + header checking as a fallback).
For PDFs, `PyMuPDF` (`fitz`) analyzes the first page. If no font or text objects are found, it is flagged as an "image-PDF" requiring OCR.

## 5. Text Extractors
Different handlers based on file type (`pipelines/document_extractor.py`):
*   **PDF (text)**: `PyMuPDF` extracts text block by block. Crucially, it preserves page numbers and attempts to reconstruct paragraphs.
*   **PDF (image)**: `PyMuPDF` renders each page to a PNG bitmap, passing it to the OCR Pipeline.
*   **DOCX**: `python-docx` iterates through paragraphs and tables. It detects heading styles to preserve structure.
*   **TXT**: `chardet` detects the encoding (UTF-8, Windows-1252), then reads directly.

## 6. OCR Pipeline (`ocr_pipeline.py`)
Triggered for images and image-PDFs.
1.  **Pre-processing**: OpenCV converts to grayscale, applies Otsu's adaptive thresholding, deskews if rotation > 2°, and scales to 300 DPI minimum for Tesseract.
2.  **Tesseract Call**: Runs `pytesseract.image_to_data()` using:
    *   PSM 3 (Fully automatic page segmentation)
    *   OEM 3 (Default, based on what is available)
3.  **Post-processing**: Joins orphaned characters, removes unnatural hyphenation at line breaks.
4.  **Output**: Returns the extracted string and an average confidence score. If confidence < 60%, a warning is logged and saved in the document's `error_message` field.

## 7. Tesseract Setup
Tesseract is an external C++ dependency.
*   **Detection**: `setup.bat` attempts to find it in `C:\Program Files\Tesseract-OCR\tesseract.exe`.
*   **Configuration**: The path is stored in `settings.toml`.
*   **Graceful Degradation**: If Tesseract is not installed, the OCR pipeline returns an error, and image uploads are rejected with a clear message instructing the user to install Tesseract. Text-PDFs continue to work normally.

## 8. Chunker (`chunker.py`)
Splits large text into smaller semantic pieces for vector search.
*   **Tokenizer**: `tiktoken` (using `cl100k_base`).
*   **Algorithm**:
    1. Iterate through text, adding tokens until window hits 512.
    2. Step back to find the nearest sentence boundary (`. `, `? `, `! `, or `\n\n`).
    3. Finalize chunk. Start the next chunk overlapping the last 64 tokens.
*   **Metadata Attachment**: Each chunk receives a dictionary:
    `{ "doc_id": "...", "chunk_index": 1, "page_number": 4, "char_offset_start": 1000 }`

## 9. Embedding Queue
To prevent blocking the HTTP response, chunks are pushed to the SQLite `chunk_embedding_queue` table.
An APScheduler task (`embedding_task.py`) polls this table every 5 seconds.
*   **Batch Size**: Pulls 100 chunks at a time.
*   **Retry Logic**: On API failure, increments `retries`. At 3 retries, status becomes `error`.

## 10. Embedder (`embedder.py`)
Takes a batch of text chunks and calls the configured AI Provider (OpenAI, Anthropic, or Ollama).
*   Implements exponential backoff for `HTTP 429 Too Many Requests`.
*   Formats the returned vectors and metadata into the ChromaDB insert format.
*   Executes `collection.add(ids=..., embeddings=..., metadatas=..., documents=...)`.

## 11. Embedding Cache
Before calling the AI API, the Embedder calculates the SHA-256 hash of the chunk's text and checks the SQLite `embedding_cache` table. If found, it skips the API call and reuses the vector. This saves significant cost if users frequently delete and re-upload similar documents.

## 12. Document Status State Machine
Displayed in the frontend Documents page:
1.  `pending`: In queue.
2.  `extracting`: Running PyMuPDF / OCR.
3.  `chunking`: Splitting text.
4.  `queuing`: Writing to `chunk_embedding_queue`.
5.  `indexing`: APScheduler is currently embedding chunks.
6.  `indexed`: Fully available for RAG.
*   `error`: Failed at any step.

## 13. Document Metadata
Stored in SQLite `documents` table: `id`, `filename`, `file_type`, `status`, `hash`, `created_at`, `error_message`.

## 14. Document Update Handling
If a user uploads a file with the exact same name but different content (different hash):
1.  The old document record is updated to `status = 'pending'`.
2.  All chunks in ChromaDB with `doc_id == current_id` are deleted.
3.  The pipeline runs again from the extraction phase.

## 15. Syllabus Parser (`syllabus_parser.py`)
A specialized pipeline step triggered *only* when the user marks a document as a "Syllabus" to generate a Roadmap.
*   **AI Prompt**: Asks the LLM to extract the hierarchical structure (Subjects -> Chapters -> Topics) from the extracted text.
*   **Response**: Expected JSON schema matching the `roadmap_nodes` structure.
*   **Fallback**: If the LLM fails or hallucinations occur, a fallback regex method attempts to build the hierarchy based on font sizes (if PDF) or markdown heading levels (`#`, `##`).

## 16. Concept Extraction from Documents
When a document reaches `indexed` status, it triggers the `graph_enricher_task`. This asynchronous job scans the document text to extract technical concepts and adds them to the Knowledge Graph as `concept` nodes, linked to the `document` node via `taught_in` edges.

## 17. File System Organization
`~/.atlas/profiles/{profile_id}/documents/`
*   `raw/`: The original files exactly as uploaded.
*   `extracted/`: `.txt` files containing the raw text output from the Extractor/OCR pipeline. Used for debugging and fast re-chunking without re-running OCR.

## 18. WebSocket Notifications
While a document processes, the backend emits events to the `ws://...` endpoint (if the user has the app open):
*   `{"type": "document_progress", "doc_id": "...", "status": "indexing", "progress": 45}`
Allows the frontend to show a real-time progress bar.

## 19. Error Handling
*   If a PDF is encrypted, it catches the PyMuPDF exception and marks the document status as `error` with `error_message = "Password protected PDF"`.
*   If OCR is illegible, `error_message = "Low quality image/scan"`.
*   Errors are isolated per document; one failing document does not halt the queue.

## 20. Document Deletion
When `DELETE /documents/{id}` is called:
1.  Delete vector chunks from ChromaDB `where={"doc_id": id}`.
2.  Delete SQLite `chunk_embedding_queue` and `documents` rows.
3.  Delete files from `raw/` and `extracted/` directories.

## 21. Performance Considerations
*   **Target**: A text-based 100-page PDF should hit `indexed` status in < 15 seconds.
*   **Target**: A 20-page scanned image-PDF should hit `indexed` in < 2 minutes (CPU dependent).
*   **Memory**: Files are processed using generators and temporary disk buffers to prevent OOM (Out Of Memory) errors when users upload 500MB textbooks.

## 22. Implementation Sequence
1.  `document_extractor.py` (PyMuPDF & python-docx).
2.  `ocr_pipeline.py` (Tesseract integration).
3.  `chunker.py` (tiktoken integration).
4.  `embedder.py` (OpenAI embedding API calls).
5.  `embedding_task.py` (APScheduler queue logic).
6.  `ingestion_service.py` (Orchestrates the above).
7.  `routers/documents.py` (FastAPI endpoints).

## 23. Master Plan Completion Addendum

### Extraction Result Shape
All extractors should return the same internal object:
```json
{
  "text": "full extracted text",
  "pages": [
    {
      "page_number": 1,
      "text": "page text",
      "ocr_used": false,
      "ocr_confidence": null
    }
  ],
  "metadata": {
    "page_count": 12,
    "word_count": 3400,
    "detected_type": "pdf",
    "is_image_pdf": false
  },
  "warnings": []
}
```

Chunk metadata must preserve `doc_id`, `profile_id`, `chunk_index`, `page_number`, `char_offset_start`, `char_offset_end`, and `source_filename`.

### Status Transition Contract
Allowed transitions:
```text
pending -> extracting -> chunking -> queuing -> indexing -> indexed
pending -> extracting -> error
extracting -> error
chunking -> error
queuing -> error
indexing -> error
indexed -> pending      (only via reprocess)
```

The service should reject impossible transitions with `ConflictError`. The frontend can display status from SQLite as the single source of truth.

### Upload Validation Rules
*   Max file size defaults to `settings.ingestion.max_file_size_mb`.
*   Browser MIME type is advisory only; backend verifies extension and magic bytes.
*   Store original filename for display, but write files using UUID-prefixed safe names.
*   Prevent path traversal by rejecting separators and control characters in display names.
*   Duplicate detection is per profile using SHA-256 of raw file bytes.

### Reprocess Rules
When reprocessing a document:
1. Set document status to `pending`.
2. Delete queued embedding jobs for the document.
3. Delete existing vectors from `{profile_id}_documents` by `doc_id`.
4. Preserve the original raw file.
5. Regenerate extracted text, chunks, embeddings, and graph links.
6. Update `indexed_at`, `chunk_count`, `word_count`, and `error_message`.

### Deletion Rules
Document deletion must clean up:
*   Raw file.
*   Extracted text file.
*   SQLite document row.
*   SQLite embedding queue rows.
*   ChromaDB vectors with matching `doc_id`.
*   Graph document node and `taught_in` edges where safe.
*   Roadmap `source_document_id` references only through explicit roadmap archive/regeneration flow; do not silently delete active roadmaps without user confirmation.

### OCR Degradation Rules
*   Text PDFs, DOCX, and TXT must continue working when Tesseract is missing.
*   Image uploads and image PDFs should fail with a clear `CONFIGURATION_ERROR` or document-level `error` status explaining that OCR is unavailable.
*   Low OCR confidence should not automatically discard text; store text with a warning unless confidence is unusably low.
*   OCR language defaults to `settings.ingestion.ocr_language`.

### Tests Required
*   Text PDF extraction preserves page numbers.
*   Duplicate upload is rejected within the same profile.
*   Reprocess deletes old vectors and queues new chunks.
*   Missing Tesseract does not break text-based PDFs.
*   Document deletion removes files, queue rows, and vectors.
*   Large files are streamed or chunked without loading the entire file into memory after upload staging.
