# 07. RAG Architecture

## 1. RAG Overview
Retrieval-Augmented Generation (RAG) in LearningOS goes beyond simply querying PDFs. It uses a **multi-source retrieval** strategy drawing from five distinct contextual sources:
1. Document Chunks (uploaded files)
2. Memory Records (extracted facts, strengths, weaknesses)
3. Past Chat Summaries (context from previous sessions)
4. Knowledge Graph Nodes (concepts and relationships)
5. User Notes (markdown files created by the user)

## 2. Why Multi-Source RAG
Standard RAG provides factual context. Multi-source RAG provides *personal* context. By combining a paragraph from a textbook with a memory that says "The user struggles with this concept," the AI Tutor can frame the explanation specifically for the user's current level of understanding.

## 3. RAG Pipeline End-to-End
```text
User Query 
   │
   ▼
Query Expansion (Append Roadmap Node Title)
   │
   ▼
HyDE (Generate Hypothetical Answer)
   │
   ▼
Parallel Multi-Collection Search (Async) ───► documents (top-10)
                                         ───► memory (top-5)
                                         ───► notes (top-5)
                                         ───► chat_summaries (top-3)
   │
   ▼
Merge (23 Candidates)
   │
   ▼
Rerank (Cross-Encoder ms-marco-MiniLM-L-6-v2)
   │
   ▼
MMR (Maximal Marginal Relevance filter)
   │
   ▼
Context Assembly (Format into Markdown block)
   │
   ▼
Prompt Injection
   │
   ▼
AI Response Generation
   │
   ▼
Citation Tracking
```

## 4. ChromaDB Collections
Collections are scoped per profile to ensure strict data separation.
*   `{profile_id}_documents`: 
    *   **Schema**: `text`
    *   **Metadata**: `doc_id`, `chunk_index`, `page_number`, `source_filename`
*   `{profile_id}_memory`:
    *   **Schema**: `text`
    *   **Metadata**: `memory_id`, `category`, `confidence`
*   `{profile_id}_notes`:
    *   **Schema**: `text`
    *   **Metadata**: `note_id`, `title`
*   `{profile_id}_chat_summaries`:
    *   **Schema**: `text`
    *   **Metadata**: `session_id`
*   `global_graph_nodes` (Not profile scoped, used for general concept matching):
    *   **Schema**: `description text`
    *   **Metadata**: `node_id`, `label`, `type`

## 5. Embedding Strategy
Users can configure their preferred embedding model in `settings.toml`.
1.  **OpenAI `text-embedding-3-small`**: 1536-dim (Default, best balance of cost/performance)
2.  **OpenAI `text-embedding-3-large`**: 3072-dim
3.  **Local: `BAAI/bge-small-en-v1.5`**: 384-dim (Via `sentence-transformers`, for offline use)
4.  **Local: `nomic-embed-text`**: 768-dim (Via Ollama)

**Stale Embeddings**: If a user switches embedding models (e.g., from OpenAI to Local), the dimensions mismatch. The system detects this, clears ChromaDB, and triggers a background job to re-embed all SQLite data using the new model.

## 6. Query Expansion
Before searching, the current context is appended to the query.
If the user is on the Roadmap node "Recursion" and asks "How does it work?", the query is expanded to: `"How does it work? (Context: Recursion)"`

## 7. HyDE (Hypothetical Document Embedding)
Instead of embedding the user's short question, the orchestrator asks the AI provider (via a fast, cheap model) to generate a hypothetical, ideal answer to the question. This hypothetical answer is then embedded and used to search ChromaDB.
*   **Why**: Questions often lack the vocabulary present in the source documents. HyDE bridges the lexical gap.
*   **Fallback**: If the AI provider fails or times out during HyDE generation, the pipeline falls back to embedding the raw expanded query.

## 8. Parallel Multi-Collection Search
Using Python's `asyncio.gather()`, queries are dispatched to ChromaDB simultaneously across the collections.
*   Documents: Request `n_results=10`
*   Memory: Request `n_results=5`
*   Notes: Request `n_results=5`
*   Chat Summaries: Request `n_results=3`
Total candidates pooled: 23 chunks.

## 9. Metadata Filtering
Mandatory `where` clause on ChromaDB queries (except global graph):
`{"profile_id": {"$eq": current_profile_id}}`
Optional filters:
`{"doc_id": {"$in": allowed_document_ids}}` (If restricting chat to specific files).

## 10. Reranker
The 23 candidates are retrieved using cosine similarity, which is fast but imprecise. A cross-encoder model (`cross-encoder/ms-marco-MiniLM-L-6-v2`) evaluates the actual user query against each candidate chunk and assigns an exact relevance score.
The top 8 chunks are selected.

## 11. MMR (Maximal Marginal Relevance)
Applied to the top 8 chunks with `lambda = 0.7`.
MMR ensures diversity. If 3 chunks are highly relevant but say the exact same thing, MMR penalizes the duplicates and pulls up a slightly less relevant but novel chunk, maximizing information density in the context window.

## 12. Context Assembly
The final chunks are formatted into a markdown block:
```markdown
<CONTEXT>
[Source: syllabus.pdf, Page 4] (ID: chunk-uuid-1)
Recursion is a method of solving a problem where the solution depends on solutions to smaller instances...

[Source: Memory (Weakness)] (ID: mem-uuid-2)
User struggles to identify base cases in recursive functions.
</CONTEXT>
```

## 13. Context Window Budget
Assuming a 128K total context window (e.g., GPT-4o):
*   System Prompt: 1K tokens
*   Memory Context: 2K tokens
*   RAG Context (Documents/Notes): 8K tokens
*   Chat History (Sliding window): 6K tokens
*   Buffer/Response generation: 4K tokens
Total typical usage: ~21K tokens. Truncation priority drops oldest chat history first, then trims RAG context.

## 14. Citation Tracking
When the AI generates a response, it is prompted to use citation markers like `[1]`.
`citation_tracker.py` maintains a mapping during the request:
`[1]` -> `chunk-uuid-1` -> `{ "filename": "syllabus.pdf", "page": 4 }`
This mapping is emitted via WebSocket as a `citations` event so the frontend can render clickable badges.

## 15. Prompt Templates
**System Prompt Injection**:
```text
... You are LearningOS Tutor ...
Use the following context to answer the user. Cite sources using [1], [2].
{assembled_context_block}

Current Topic: {roadmap_node_title}
```

## 16. Retriever Implementation
`rag/retriever.py`: Contains the `MultiSourceRetriever` class. Handles the `asyncio.gather` ChromaDB calls and HyDE generation.

## 17. Reranker Implementation
`rag/reranker.py`: Wraps the HuggingFace `SentenceTransformer` cross-encoder. If running locally without GPU, falls back to simple cosine similarity sorting to save CPU cycles.

## 18. Context Assembler Implementation
`rag/context_assembler.py`: Handles token counting (via `tiktoken`) and formatting the retrieved chunks into the XML-like `<CONTEXT>` tags.

## 19. Citation Tracker Implementation
`rag/citation_tracker.py`: Parses the final AI output with regex to find `\[\d+\]` patterns, verifies they match provided context IDs, and builds the JSON citation array.

## 20. Chunking Strategy
Handled by `pipelines/chunker.py`.
*   Uses `tiktoken` (cl100k_base).
*   Chunk size: 512 tokens.
*   Overlap: 64 tokens.
*   **Sentence Boundary Snapping**: Never cuts a chunk in the middle of a sentence. It looks for the nearest `. ` or `\n\n` within a 20-token radius of the boundary.

## 21. Embedding Queue
`chunk_embedding_queue` in SQLite.
Chunks are inserted here. A background task (`APScheduler`) reads batches of 100, calls the Embedder, inserts to ChromaDB, and marks as `done`.
Retry logic: If API rate limit hit, backoff exponentially. Max 3 retries.

## 22. Embedding Cache
`SHA-256(chunk_text) -> embedding_vector` stored in SQLite `embedding_cache`.
Before calling OpenAI, check the cache. Prevents spending money re-embedding identical text if a user deletes and re-uploads a file.

## 23. Embedding Versioning
When the embedding model changes, a migration script marks all documents as `status = 'pending'`, clears ChromaDB collections, and pushes all text back into the `chunk_embedding_queue`.

## 24. HNSW Index Tuning
Set in ChromaDB client initialization:
*   `M = 32`
*   `ef_construction = 200`
*   `ef = 100`

## 25. Performance Benchmarks
Target Latency for the entire RAG pipeline (Query -> Context Assembly):
*   HyDE Generation: ~300ms
*   ChromaDB Parallel Search: ~50ms
*   Reranking (Local CPU): ~150ms
*   Total Target: **< 500ms** before streaming begins.

## 26. Implementation Contracts Missing from the Short Spec

### Retrieval Result Shape
All retrievers should normalize their output into one internal shape before reranking:
```json
{
  "id": "chunk-or-memory-id",
  "source_type": "document",
  "source_id": "uuid",
  "profile_id": "uuid",
  "text": "retrieved text",
  "score": 0.82,
  "metadata": {
    "filename": "syllabus.pdf",
    "page_number": 4,
    "chunk_index": 12
  }
}
```

Allowed `source_type` values: `document`, `memory`, `note`, `chat_summary`, `graph_node`.

### Ranking Pipeline Rules
1. Expand the query with active roadmap node, profile goal, and selected learning mode.
2. Run HyDE only when `settings.rag.use_hyde = true` and the active model provider is available.
3. Retrieve from all enabled collections in parallel.
4. Drop results with missing `profile_id` unless the collection is intentionally global.
5. Merge by canonical ID and keep the highest retrieval score.
6. Rerank against the original user query, not the HyDE text.
7. Apply MMR after reranking.
8. Enforce token budget in `context_assembler.py`, not in the retriever.

### Citation Requirements
*   Every document chunk included in the final context must receive a stable citation index.
*   Memory and graph context can be used without citation markers in the final answer, but they must be tracked in `chat_messages.memory_ids_used` and `graph_nodes_mentioned`.
*   If the model emits citation markers that were not provided in context, `citation_tracker.py` should remove or flag them before final persistence.
*   Citation payloads sent to the frontend must include `filename`, `page_number`, `chunk_index`, and a short source preview when available.

### Failure and Fallback Behavior
| Failure | Required Fallback |
| :--- | :--- |
| HyDE model call fails | Embed the expanded raw query. |
| Reranker model unavailable | Use vector similarity order. |
| One ChromaDB collection fails | Log the collection error and continue with other collections. |
| All retrieval fails | Continue chat with memory/roadmap/history only and warn through metadata. |
| Token counting fails | Use conservative character estimate: 4 chars = 1 token. |

### Tests Required Before MVP
*   Chunk retrieval returns only active profile results.
*   MMR removes near-duplicates while preserving high-relevance chunks.
*   Context assembler never exceeds a supplied token budget.
*   Citation tracker maps `[1]` style citations to the intended chunk IDs.
*   HyDE failure path still produces a response context.
