# 19. Vector Database Design

## 1. Purpose
This document defines LearningOS vector storage using ChromaDB. It covers collections, metadata schemas, IDs, embedding versioning, query behavior, deletion, backup, performance, and tests.

Related documents:
* `03_DATABASE_DESIGN.md`: SQLite and ChromaDB relationship.
* `07_RAG_ARCHITECTURE.md`: retrieval pipeline.
* `10_DOCUMENT_PROCESSING.md`: chunking and embedding queue.
* `18_MODEL_INTEGRATION.md`: embedding models and provider behavior.

## 2. Vector Store Goals
* Keep all vectors local.
* Isolate profiles.
* Support document, memory, notes, chat-summary, and graph retrieval.
* Support embedding model changes safely.
* Make deletion complete and testable.
* Keep retrieval fast enough for chat.

## 3. ChromaDB Mode
Use embedded persistent ChromaDB.

Default path:
```text
~/.learningos/data/chroma/
```

Initialization:
* Create persistent client during backend startup.
* Ensure global collections exist lazily or at startup.
* Ensure profile collections exist when profile is created or first used.
* Do not run a remote Chroma server for MVP.

## 4. Collection Strategy

### Profile-Scoped Collections
Each profile owns:
```text
{profile_id}_documents
{profile_id}_memory
{profile_id}_notes
{profile_id}_chat_summaries
```

### Global Collections
```text
global_graph_nodes
```

Global graph nodes are used for concept matching only. Results must still be filtered or mapped safely before being shown in profile-specific UI.

## 5. Collection Schemas

### Document Collection
Collection: `{profile_id}_documents`

Document text:
* Chunk text.

Metadata:
```json
{
  "profile_id": "uuid",
  "doc_id": "uuid",
  "chunk_id": "uuid",
  "chunk_index": 12,
  "source_filename": "syllabus.pdf",
  "page_number": 4,
  "char_offset_start": 1000,
  "char_offset_end": 1400,
  "file_type": "pdf",
  "is_syllabus": true,
  "roadmap_node_id": "uuid-or-null",
  "embedding_model": "text-embedding-3-small",
  "embedding_dim": 1536,
  "created_at": "2026-06-13T10:00:00Z"
}
```

Vector ID:
```text
doc:{doc_id}:chunk:{chunk_index}:model:{embedding_model}
```

### Memory Collection
Collection: `{profile_id}_memory`

Document text:
* Memory content.

Metadata:
```json
{
  "profile_id": "uuid",
  "memory_id": "uuid",
  "category": "weakness",
  "subject": "recursion",
  "confidence": 0.85,
  "source": "chat",
  "source_id": "uuid",
  "is_active": true,
  "embedding_model": "text-embedding-3-small",
  "embedding_dim": 1536,
  "created_at": "2026-06-13T10:00:00Z"
}
```

Vector ID:
```text
memory:{memory_id}:model:{embedding_model}
```

### Notes Collection
Collection: `{profile_id}_notes`

Document text:
* Note chunk text.

Metadata:
```json
{
  "profile_id": "uuid",
  "note_id": "uuid",
  "chunk_index": 0,
  "title": "Backprop notes",
  "tags": "json-string-or-comma-list",
  "roadmap_node_id": "uuid-or-null",
  "embedding_model": "text-embedding-3-small",
  "embedding_dim": 1536,
  "updated_at": "2026-06-13T10:00:00Z"
}
```

Vector ID:
```text
note:{note_id}:chunk:{chunk_index}:model:{embedding_model}
```

### Chat Summary Collection
Collection: `{profile_id}_chat_summaries`

Document text:
* Summary of a chat session or long conversation segment.

Metadata:
```json
{
  "profile_id": "uuid",
  "session_id": "uuid",
  "summary_id": "uuid",
  "message_start_id": "uuid",
  "message_end_id": "uuid",
  "roadmap_node_id": "uuid-or-null",
  "embedding_model": "text-embedding-3-small",
  "embedding_dim": 1536,
  "created_at": "2026-06-13T10:00:00Z"
}
```

Vector ID:
```text
chat-summary:{summary_id}:model:{embedding_model}
```

### Global Graph Nodes Collection
Collection: `global_graph_nodes`

Document text:
* Graph node label and description.

Metadata:
```json
{
  "node_id": "uuid",
  "label": "Dynamic Programming",
  "type": "concept",
  "profile_id": "uuid-or-null",
  "embedding_model": "text-embedding-3-small",
  "embedding_dim": 1536
}
```

Vector ID:
```text
graph-node:{node_id}:model:{embedding_model}
```

## 6. Embedding Queue Relationship
SQLite table `chunk_embedding_queue` is the durable work queue. ChromaDB is the vector index, not the task source of truth.

Queue row lifecycle:
```text
queued -> embedding -> done
queued -> embedding -> error
error -> queued   (manual retry/reprocess)
```

Rules:
* Queue rows store text and metadata needed for embedding.
* Embedding task writes ChromaDB vectors.
* After successful vector write, queue row stores `embedding_id` where applicable and status `done`.
* If vector write fails, queue row status becomes `error` after retry limit.

## 7. Embedding Cache
SQLite `embedding_cache` prevents duplicate paid embedding calls.

Cache key:
```text
sha256(normalized_text + embedding_model)
```

Cache record:
* `text_hash`
* `embedding_model`
* `embedding_dim`
* `embedding_json` or `embedding_id`
* `created_at`

Rules:
* Do not reuse vectors across different embedding models.
* Do not reuse vectors with different dimensions.
* Normalize text consistently before hashing.

## 8. Query Patterns

### RAG Document Query
Inputs:
* `profile_id`
* query embedding
* optional document IDs
* optional roadmap node ID
* top-k

Chroma filters:
```json
{
  "profile_id": {"$eq": "uuid"}
}
```

Optional:
```json
{
  "doc_id": {"$in": ["uuid1", "uuid2"]}
}
```

### Memory Query
Inputs:
* `profile_id`
* query embedding
* top-k
* optional category

Filter:
```json
{
  "profile_id": {"$eq": "uuid"},
  "is_active": {"$eq": true}
}
```

### Notes Query
Filter by `profile_id` and optional `roadmap_node_id`.

### Graph Concept Match
Use graph node collection for semantic concept matching during enrichment. Final graph mutations must still go through `GraphService`.

## 9. Retrieval Normalization
Every ChromaDB result must be normalized before use:
```json
{
  "id": "vector-id",
  "source_type": "document",
  "source_id": "uuid",
  "profile_id": "uuid",
  "text": "chunk text",
  "score": 0.82,
  "metadata": {}
}
```

Allowed source types:
* `document`
* `memory`
* `note`
* `chat_summary`
* `graph_node`

## 10. HNSW Tuning
Default HNSW parameters:
| Parameter | Value | Reason |
| :--- | :--- | :--- |
| `M` | 32 | Balance recall and local memory use. |
| `ef_construction` | 200 | Better index quality during build. |
| `ef` | 100 | Good query recall. |

These values should be configurable only if performance profiling proves a need.

## 11. Embedding Versioning
Embedding version is defined by:
* Provider.
* Model name.
* Dimension.
* Text normalization version.
* Chunking version.

Suggested version string:
```text
{provider}:{model}:{dim}:chunk-v1:textnorm-v1
```

Store version in:
* ChromaDB metadata.
* SQLite document metadata or queue rows.
* Embedding cache.

When version changes:
1. Detect mismatch.
2. Mark affected resources stale.
3. Drop or archive incompatible vectors.
4. Requeue embeddings.
5. Show re-indexing progress in UI.

## 12. Deletion Strategy

### Document Deletion
Delete from `{profile_id}_documents` where:
```json
{
  "doc_id": {"$eq": "uuid"}
}
```

Then delete SQLite queue rows and files as described in `10_DOCUMENT_PROCESSING.md`.

### Memory Deletion
Delete vector by `embedding_id` or filter by `memory_id`.

### Note Deletion
Delete all vectors with `note_id`.

### Profile Deletion
Drop profile collections:
* `{profile_id}_documents`
* `{profile_id}_memory`
* `{profile_id}_notes`
* `{profile_id}_chat_summaries`

Also remove profile-specific graph node embeddings if stored in global collection.

## 13. Backup and Restore
ChromaDB files are backed up with local data backups.

Backup rules:
* Prefer idle period backup.
* Stop writes or ensure snapshot consistency where possible.
* Copy ChromaDB directory with SQLite backup metadata.
* Keep backup and SQLite from the same approximate time.

Restore rules:
* Stop server.
* Restore SQLite and ChromaDB together.
* If ChromaDB missing or incompatible, rebuild vectors from SQLite source text/queues where possible.

## 14. Performance Targets
| Operation | Target |
| :--- | :--- |
| Add 100 embeddings | < 2s excluding provider latency |
| Query one collection | < 100ms |
| Query all RAG collections | < 500ms before model call |
| Delete document vectors | < 2s for typical document |
| Profile collection creation | < 1s |

## 15. Failure Handling
| Failure | Required Behavior |
| :--- | :--- |
| ChromaDB unavailable at startup | Health fails; backend should not claim ready. |
| ChromaDB write fails during indexing | Mark queue/document error; keep SQLite metadata. |
| ChromaDB query fails for one collection | Log and continue with other collections. |
| Collection missing | Recreate if safe; otherwise return storage error. |
| Dimension mismatch | Stop write/query for affected collection and trigger re-embedding flow. |

## 16. Profile Isolation Rules
Defense in depth:
* Separate profile collections.
* Include `profile_id` metadata.
* Apply metadata filter in queries.
* Repository/service methods require active profile ID.
* Tests must prove cross-profile retrieval returns no data.

## 17. Implementation Files
Required files:
```text
backend/app/pipelines/embedder.py
backend/app/db/repositories/embedding_repo.py
backend/app/tasks/embedding_task.py
backend/app/rag/retriever.py
backend/app/rag/context_assembler.py
backend/app/models/abstraction.py
backend/app/models/provider_factory.py
```

Optional helper:
```text
backend/app/vector_store.py
```

If a helper exists, it should wrap ChromaDB collection creation, query, add, delete, and reset operations.

## 18. Tests Required

### Unit Tests
* Vector ID generation.
* Metadata normalization.
* Embedding version string.
* Cache key generation.
* Retrieval result normalization.

### Integration Tests
* Create profile collections.
* Add document vectors.
* Query document vectors by profile.
* Query memory vectors excluding inactive records.
* Delete document vectors.
* Drop profile collections.
* Detect dimension mismatch.
* Reuse embedding cache.

### Performance Tests
* Query 10,000 vectors.
* Add batch of 100 vectors.
* Delete all vectors for one document.

## 19. Acceptance Checklist
Vector database work is complete when:
1. ChromaDB initializes in persistent local mode.
2. Profile-scoped collections are created.
3. Document chunks embed and query successfully.
4. Memory and notes use separate collections.
5. Embedding metadata includes model and dimension.
6. Deletion removes vectors completely.
7. Profile isolation is tested.
8. Embedding model changes trigger safe re-embedding behavior.
9. Backup/restore behavior is documented and tested at least manually.

