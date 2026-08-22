# 03. Database Design

## 1. Database Overview
LearningOS utilizes three distinct data stores, each chosen for its specific strengths in a local-first architecture:
1.  **SQLite (Relational)**: The source of truth for structured data (profiles, document metadata, chat history, roadmap progress, settings).
2.  **ChromaDB (Vector)**: An embedded vector database used for Retrieval-Augmented Generation (RAG). It stores embeddings of document chunks, memory records, and notes to enable semantic search.
3.  **JSON + NetworkX (Graph)**: A local JSON file representing the Knowledge Graph, loaded into memory via NetworkX at runtime for complex relationship traversals and D3.js visualization.

## 2. SQLite Design Principles
*   **WAL Mode**: Write-Ahead Logging is enabled (`PRAGMA journal_mode=WAL;`) to allow concurrent reads and writes, crucial for the background task queue and async FastApi.
*   **Foreign Keys ON**: Enforced at the connection level (`PRAGMA foreign_keys=ON;`) to guarantee data integrity across profiles.
*   **UUID as TEXT**: All primary and foreign keys use UUIDv4 strings stored as `TEXT`.
*   **ISO 8601 Timestamps**: All dates and times are stored as `TEXT` in UTC ISO 8601 format.
*   **FTS5 for Search**: SQLite's Full-Text Search extension is used to index and search chat messages, notes, and memory records rapidly.

## 3. Complete Table Schemas

### `profiles`
| Column | Type | Constraints | Purpose | Example |
| :--- | :--- | :--- | :--- | :--- |
| `id` | TEXT | PRIMARY KEY | Unique profile identifier | `uuid4` |
| `name` | TEXT | NOT NULL | Display name of the profile | "Computer Science" |
| `created_at` | TEXT | NOT NULL | Creation timestamp | `2026-06-13T10:00:00Z` |
| `updated_at` | TEXT | NOT NULL | Last update timestamp | `2026-06-13T10:00:00Z` |
| `settings_json`| TEXT | | Profile specific settings overrides | `{"theme": "dark"}` |

### `documents`
Implemented in Milestone 08 (`app/db/models.py::Document`, migration `f1a4c8e6b3d2_create_documents_table`).

| Column | Type | Constraints | Purpose | Example |
| :--- | :--- | :--- | :--- | :--- |
| `id` | TEXT | PRIMARY KEY | Unique document ID | `uuid4` |
| `profile_id` | TEXT | FK(profiles.id) NOT NULL, CASCADE, indexed | Owning profile | `uuid4` |
| `filename` | TEXT | NOT NULL | Sanitized original filename | "syllabus.pdf" |
| `file_path` | TEXT | NOT NULL | Path to the raw file, relative to the data dir | "profiles/{id}/documents/raw/{uuid}_syllabus.pdf" |
| `extracted_text_path` | TEXT | | Path to extracted `.txt`, relative to the data dir (null until extracted) | "profiles/{id}/documents/extracted/{doc_id}.txt" |
| `file_type` | TEXT | NOT NULL | Short type, detected from magic bytes | "pdf" \| "docx" \| "txt" \| "image" |
| `content_hash` | TEXT | NOT NULL, indexed | SHA-256 of raw bytes; used for per-profile dedup | "a1b2c3d4..." |
| `status` | TEXT | NOT NULL, default `pending` | Processing status (see below) | "extracted" |
| `page_count` | INTEGER | | Pages (PDF) or 1 (image); null for DOCX/TXT | 12 |
| `chunk_count` | INTEGER | NOT NULL, default 0 | Set by the chunker/embedder (Milestone 10) | 0 |
| `word_count` | INTEGER | | Word count of extracted text | 3400 |
| `uploaded_at` | TEXT | NOT NULL | Upload timestamp | `2026-06-13T10:00:00Z` |
| `indexed_at` | TEXT | | Set once embedding lands (Milestone 10/11) | null |
| `error_message`| TEXT | | Error/degradation detail | "Password protected PDF" |
| `is_syllabus` | BOOLEAN | NOT NULL, default false | Marks the primary syllabus doc | false |
| `roadmap_node_id` | TEXT | | Optional link, set once Roadmap exists | null |

**Milestone 08/09 status values**: `pending`, `extracting`, `extracted`, `pending_ocr` (images and scanned/image PDFs when Tesseract OCR is unavailable), `error`. The full `chunking -> queuing -> indexing -> indexed` chain described elsewhere in this document is introduced in Milestones 10/11 alongside the embedder and vector store.

### `chat_sessions`
| Column | Type | Constraints | Purpose | Example |
| :--- | :--- | :--- | :--- | :--- |
| `id` | TEXT | PRIMARY KEY | Unique session ID | `uuid4` |
| `profile_id` | TEXT | FK(profiles.id) NOT NULL | Owning profile | `uuid4` |
| `title` | TEXT | NOT NULL | Auto-generated chat title | "Understanding Graph Theory" |
| `created_at` | TEXT | NOT NULL | Session start timestamp | `2026-06-13T10:00:00Z` |
| `updated_at` | TEXT | NOT NULL | Last message timestamp | `2026-06-13T10:00:00Z` |

### `chat_messages`
| Column | Type | Constraints | Purpose | Example |
| :--- | :--- | :--- | :--- | :--- |
| `id` | TEXT | PRIMARY KEY | Unique message ID | `uuid4` |
| `session_id` | TEXT | FK(chat_sessions.id) NOT NULL| Owning session | `uuid4` |
| `role` | TEXT | NOT NULL | 'user', 'assistant', 'system' | "user" |
| `content` | TEXT | NOT NULL | Message body | "What is a DAG?" |
| `citations` | TEXT | | JSON array of citation references | `[{"doc_id": "uuid"}]` |
| `created_at` | TEXT | NOT NULL | Message timestamp | `2026-06-13T10:00:00Z` |

### `roadmaps`
| Column | Type | Constraints | Purpose | Example |
| :--- | :--- | :--- | :--- | :--- |
| `id` | TEXT | PRIMARY KEY | Unique roadmap ID | `uuid4` |
| `profile_id` | TEXT | FK(profiles.id) NOT NULL | Owning profile | `uuid4` |
| `title` | TEXT | NOT NULL | Title of the roadmap | "CS101 Mastery" |
| `mode` | TEXT | NOT NULL | 'strict', 'adaptive', 'hybrid' | "hybrid" |
| `created_at` | TEXT | NOT NULL | Creation timestamp | `2026-06-13T10:00:00Z` |

### `roadmap_nodes`
| Column | Type | Constraints | Purpose | Example |
| :--- | :--- | :--- | :--- | :--- |
| `id` | TEXT | PRIMARY KEY | Unique node ID | `uuid4` |
| `roadmap_id` | TEXT | FK(roadmaps.id) NOT NULL | Owning roadmap | `uuid4` |
| `title` | TEXT | NOT NULL | Node title | "Variables and Types" |
| `description` | TEXT | | Node summary | "Introduction to..." |
| `node_type` | TEXT | NOT NULL | 'subject', 'chapter', 'topic' | "topic" |
| `status` | TEXT | NOT NULL | 'not_started', 'in_progress', 'completed'| "in_progress" |
| `parent_id` | TEXT | FK(roadmap_nodes.id) | Parent node for hierarchy | `uuid4` |
| `mastery_score`| REAL | DEFAULT 0.0 | Calculated mastery | 0.85 |
| `ai_generated` | BOOLEAN| DEFAULT FALSE | Created by Adaptive mode? | 0 |

### `roadmap_edges`
| Column | Type | Constraints | Purpose | Example |
| :--- | :--- | :--- | :--- | :--- |
| `id` | TEXT | PRIMARY KEY | Unique edge ID | `uuid4` |
| `roadmap_id` | TEXT | FK(roadmaps.id) NOT NULL | Owning roadmap | `uuid4` |
| `source_id` | TEXT | FK(roadmap_nodes.id) NOT NULL| Prerequisite node | `uuid4` |
| `target_id` | TEXT | FK(roadmap_nodes.id) NOT NULL| Dependent node | `uuid4` |
| `edge_type` | TEXT | NOT NULL | 'prerequisite', 'sequential' | "prerequisite" |

### `memory_records`
| Column | Type | Constraints | Purpose | Example |
| :--- | :--- | :--- | :--- | :--- |
| `id` | TEXT | PRIMARY KEY | Unique memory ID | `uuid4` |
| `profile_id` | TEXT | FK(profiles.id) NOT NULL | Owning profile | `uuid4` |
| `category` | TEXT | NOT NULL | 'strength', 'weakness', 'fact' | "weakness" |
| `content` | TEXT | NOT NULL | The memory statement | "Struggles with recursion" |
| `confidence` | REAL | NOT NULL | System confidence (0.0 - 1.0) | 0.9 |
| `created_at` | TEXT | NOT NULL | Extraction timestamp | `2026-06-13T10:00:00Z` |

### `chunk_embedding_queue`
| Column | Type | Constraints | Purpose | Example |
| :--- | :--- | :--- | :--- | :--- |
| `id` | TEXT | PRIMARY KEY | Unique job ID | `uuid4` |
| `document_id` | TEXT | FK(documents.id) NOT NULL | Owning document | `uuid4` |
| `chunk_index` | INTEGER| NOT NULL | Order within document | 5 |
| `text` | TEXT | NOT NULL | Chunk text content | "Graph theory is..." |
| `status` | TEXT | NOT NULL | 'queued', 'embedding', 'done' | "queued" |
| `retries` | INTEGER| DEFAULT 0 | Retry count on failure | 0 |

## 4. Entity Relationship Diagram (ERD)
```text
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────────┐
│    profiles     │◄──────┤    documents    │◄──────┤chunk_embedding_queue│
└────────┬────────┘       └─────────────────┘       └─────────────────────┘
         │
         ├────────────────┌─────────────────┐       ┌─────────────────────┐
         │                │  chat_sessions  │◄──────┤    chat_messages    │
         │                └─────────────────┘       └─────────────────────┘
         │
         ├────────────────┌─────────────────┐       ┌─────────────────────┐
         │                │    roadmaps     │◄──────┤    roadmap_edges    │
         │                └────────┬────────┘       └──────────┬──────────┘
         │                         │                           │
         │                         │ ┌──────────────────────┐  │
         │                         └─┤    roadmap_nodes     │◄─┘
         │                           └──────────────────────┘
         │
         └────────────────┌─────────────────┐
                          │ memory_records  │
                          └─────────────────┘
```

## 5. Index Strategy
*   `idx_documents_profile_status`: `(profile_id, status)` - For dashboard document lists.
*   `idx_messages_session_created`: `(session_id, created_at)` - For rendering chat streams sequentially.
*   `idx_nodes_roadmap_parent`: `(roadmap_id, parent_id)` - For building roadmap hierarchy.
*   `idx_memory_profile_category`: `(profile_id, category)` - For quick memory filtering.
*   `idx_embedding_queue_status`: `(status)` - For the background worker to poll quickly.

## 6. FTS5 Full-Text Search
Virtual FTS5 tables are created via Alembic triggers to mirror data.
```sql
CREATE VIRTUAL TABLE chat_messages_fts USING fts5(content, content='chat_messages', content_rowid='id');
```
A trigger inserts, updates, or deletes rows in the FTS table whenever `chat_messages` changes.

## 7. SQLAlchemy ORM Models
Defined in `app/db/models.py`, mapping exactly to the schema above. Relationships use `back_populates` and `lazy="selectin"` for eager loading where appropriate (e.g., loading a session and its messages).

## 8. Alembic Migration Strategy
*   Migrations stored in `alembic/versions/`.
*   Numbering format: `YYYYMMDD_HHMM_slug.py`.
*   Auto-generate relies on comparing `models.py` to the current SQLite schema.
*   Migrations run automatically on app startup inside `lifespan.py` before the web server binds.

## 9. ChromaDB Vector Store Design
ChromaDB uses persistent local storage (`~/.learningos/data/chroma`).
Collections are scoped per profile:
*   `{profile_id}_documents`: Embeddings of all document chunks. Metadata: `doc_id`, `chunk_index`, `page_number`.
*   `{profile_id}_memory`: Embeddings of memory records. Metadata: `memory_id`, `category`, `confidence`.
*   `{profile_id}_notes`: Embeddings of user notes.
*   `global_graph_nodes`: Shared collection of graph node concepts for fuzzy semantic matching.

## 10. ChromaDB HNSW Tuning
The HNSW index in ChromaDB is configured for optimal local performance:
*   `M`: 32 (Max connections per node, good balance of speed and recall).
*   `ef_construction`: 200 (Depth of search during index building).
*   `ef`: 100 (Depth of search during query).

## 11. Graph Store (JSON + NetworkX)
Stored locally at `~/.learningos/data/graph/knowledge_graph.json`.
*   **Node Schema**: `{"id": "uuid", "label": "String", "type": "concept", "mastery_score": 0.5}`
*   **Edge Schema**: `{"source": "uuid1", "target": "uuid2", "type": "prerequisite_of"}`
Loaded entirely into memory as a `networkx.DiGraph` on boot. Writes are flushed back to JSON atomically.

## 12. Embedding Cache Table
SQLite table `embedding_cache` maps a `SHA-256(text)` to a ChromaDB `embedding_id` or the raw vector array. This prevents re-calling the AI provider for identical chunks.

## 13. Data Relationships
*   **SQLite -> ChromaDB**: `chunk_embedding_queue` records process text and push vectors to ChromaDB. Memory records in SQLite map 1:1 to ChromaDB via their `id`.
*   **SQLite -> Graph**: Roadmap nodes often share names with Graph nodes. Mastery score updates in a Roadmap trigger mastery updates in the Graph via label matching.

## 14. Backup Strategy
*   **SQLite**: Handled by APScheduler weekly using SQLite's built-in online backup API (copies without locking the DB).
*   **ChromaDB**: File-level copy of the directory during an idle period.
*   **Retention**: 7 rolling backups stored in `~/.learningos/backups/`.

## 15. Storage Estimates
*   **100-page PDF**: ~300 chunks. SQLite metadata (~50KB), ChromaDB vectors (~1.5MB for 1536-dim).
*   **Per Profile**: Moderate use over a year (~50 docs, 100 chats) equals roughly 150MB total database size.
*   **Total System Limit**: Practically unbounded locally, but UI performance requires pagination above 10,000 items per view.

## 16. Migration Rollback
If Alembic `upgrade head` fails on startup:
1. The exception is caught.
2. The system logs a CRITICAL error and refuses to start the FastAPI server.
3. Users must restore from the automated backup (instructions provided in logs).

## 17. Performance Considerations
*   **WAL Mode**: Ensures the embedding background worker writing to Chroma/SQLite doesn't block the UI reading from SQLite.
*   **Query Patterns**: Most queries filter by `profile_id`, making `idx_*_profile_id` indexes critical.
*   **Window Functions**: Used heavily in `AnalyticsService` for computing moving averages of mastery without pulling all rows into Python.

## 18. Master Plan Schema Alignment
The table list in Section 3 is a compact starting point. The implementation must use the fuller schema below so the database matches `00_IMPLEMENTATION_PLAN.md`.

### Required Field Additions
| Table | Add / Preserve These Fields | Reason |
| :--- | :--- | :--- |
| `profiles` | `description`, `goal`, `mode`, `is_active`, `color`, `icon` | Onboarding, profile switching, visual identity, and roadmap defaults. |
| `documents` | `file_path`, `page_count`, `chunk_count`, `word_count`, `uploaded_at`, `indexed_at`, `is_syllabus`, `roadmap_node_id` | Enables progress display, reprocessing, syllabus detection, and node-scoped source material. |
| `chat_sessions` | `mode`, `roadmap_node_id`, `tags`, `message_count`, `is_archived` | Supports learning modes, topic anchoring, search/filtering, and soft archive. |
| `chat_messages` | `profile_id`, `token_count`, `retrieved_chunks`, `memory_ids_used`, `graph_nodes_mentioned`, `model_used`, `latency_ms`, `status` | Required for citations, analytics, debugging, and incomplete stream recovery. |
| `roadmaps` | `name`, `version`, `is_active`, `source_document_id`, `archived_at` | Required for regeneration, migration, and one active roadmap per profile. |
| `roadmap_nodes` | `profile_id`, `order_index`, `time_spent_minutes`, `completed_at`, `metadata_json` | Required for progress, sorting, ReactFlow layout, and analytics. |
| `roadmap_edges` | `from_node_id`, `to_node_id` | Prefer these names over `source_id`/`target_id` in SQL to avoid confusion with graph node IDs. API can serialize as `source`/`target`. |
| `memory_records` | `subject`, `source`, `source_id`, `updated_at`, `is_active`, `embedding_id` | Required for deduplication, provenance, soft delete, and vector cleanup. |

### Additional Required Tables
#### `quiz_attempts`
| Column | Type | Constraints | Purpose |
| :--- | :--- | :--- | :--- |
| `id` | TEXT | PRIMARY KEY | Attempt identifier. |
| `profile_id` | TEXT | FK(profiles.id) NOT NULL | Owning profile. |
| `roadmap_node_id` | TEXT | FK(roadmap_nodes.id), nullable | Topic assessed. |
| `mode` | TEXT | NOT NULL | `practice` or `timed_assessment`. |
| `started_at` | TEXT | NOT NULL | UTC start time. |
| `completed_at` | TEXT | nullable | UTC completion time. |
| `score` | REAL | nullable | 0.0 to 1.0 score. |
| `total_questions` | INTEGER | NOT NULL | Number generated. |
| `correct_count` | INTEGER | nullable | Correct answers. |
| `time_limit_seconds` | INTEGER | nullable | Timed assessment limit. |
| `questions_json` | TEXT | NOT NULL | Full generated questions, answers, rubric, and user answers. |

#### `analytics_events`
| Column | Type | Constraints | Purpose |
| :--- | :--- | :--- | :--- |
| `id` | TEXT | PRIMARY KEY | Event identifier. |
| `profile_id` | TEXT | FK(profiles.id) NOT NULL | Owning profile. |
| `event_type` | TEXT | NOT NULL | `topic_started`, `topic_completed`, `quiz_taken`, `time_logged`, `model_call`, `document_indexed`. |
| `entity_type` | TEXT | NOT NULL | `roadmap_node`, `document`, `session`, `quiz`, `model`. |
| `entity_id` | TEXT | nullable | Related record ID. |
| `value` | REAL | nullable | Numeric payload such as minutes, score, latency, or cost. |
| `metadata_json` | TEXT | nullable | Additional structured payload. |
| `occurred_at` | TEXT | NOT NULL | UTC event time. |

#### `notes`
| Column | Type | Constraints | Purpose |
| :--- | :--- | :--- | :--- |
| `id` | TEXT | PRIMARY KEY | Note identifier. |
| `profile_id` | TEXT | FK(profiles.id) NOT NULL | Owning profile. |
| `roadmap_node_id` | TEXT | FK(roadmap_nodes.id), nullable | Optional topic link. |
| `title` | TEXT | NOT NULL | Display title. |
| `content` | TEXT | NOT NULL | Markdown body. |
| `source` | TEXT | NOT NULL | `ai_generated` or `user_written`. |
| `created_at` | TEXT | NOT NULL | UTC creation time. |
| `updated_at` | TEXT | NOT NULL | UTC update time. |
| `tags` | TEXT | nullable | JSON array of tags. |

#### `embedding_cache`
| Column | Type | Constraints | Purpose |
| :--- | :--- | :--- | :--- |
| `text_hash` | TEXT | PRIMARY KEY | SHA-256 hash of normalized chunk text. |
| `embedding_model` | TEXT | NOT NULL | Model that produced the vector. |
| `embedding_dim` | INTEGER | NOT NULL | Dimension guard. |
| `embedding_json` | TEXT | nullable | Cached local vector if stored in SQLite. |
| `embedding_id` | TEXT | nullable | ChromaDB vector ID if stored externally. |
| `created_at` | TEXT | NOT NULL | Cache insertion time. |

### Required Constraints
*   `profiles.name` should be unique after case-folding per local installation.
*   `documents(profile_id, hash)` should be unique to prevent duplicate uploads inside a profile.
*   Only one `profiles.is_active = true` row should exist at a time; enforce in service logic because SQLite partial uniqueness across booleans is awkward cross-platform.
*   Only one `roadmaps.is_active = true` row should exist per profile; enforce with a partial unique index where supported and service-level fallback.
*   `roadmap_edges(from_node_id, to_node_id, edge_type)` should be unique per roadmap.
*   `memory_records.is_active = false` means hidden from retrieval but retained for export/audit until profile deletion.

### Required FTS5 Tables
Create FTS5 mirrors for:
*   `chat_messages(content)`
*   `memory_records(content, subject)`
*   `notes(title, content, tags)`

Each FTS table must be maintained by insert/update/delete triggers in Alembic migrations. Search endpoints should return source IDs plus highlighted snippets, not full internal rows by default.

## 19. Migration Implementation Instructions
1. Create all ORM models before generating the initial migration; do not let Alembic produce a partial schema.
2. Initial migration must enable `PRAGMA foreign_keys=ON` during connection setup, not only migration execution.
3. Store JSON as `TEXT` in SQLite for portability, but validate shape through Pydantic schemas at service boundaries.
4. Use UTC timestamps from a single utility function so tests can freeze time.
5. Add repository tests for cascade delete of profile-owned records before implementing profile deletion in the API.
6. Add migration tests that create a fresh database, run `upgrade head`, and verify all tables/indexes/FTS triggers exist.
