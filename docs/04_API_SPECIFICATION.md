# 04. API Specification

## 1. API Overview
The Atlas backend exposes a local REST API running on `localhost:8000`.
*   **Base URL**: `http://127.0.0.1:8000/api/v1`
*   **Authentication**: None. The system relies on local machine access.
*   **WebSocket Base**: `ws://127.0.0.1:8000/ws`

## 2. Request/Response Conventions
All JSON responses follow a standard envelope format:
```json
{
  "data": { ... },
  "error": null,
  "meta": { "pagination": null }
}
```
*   `data`: The requested resource or array of resources.
*   `error`: Present if the request failed. Format: `{ "code": "STRING", "message": "Human readable", "details": {} }`
*   `meta`: Contains metadata like pagination (`page`, `limit`, `total_pages`, `total_count`).

**Data Types**:
*   All IDs are standard UUIDv4 strings.
*   All timestamps are ISO 8601 strings (e.g., `2026-06-13T15:00:00Z`).

## 3. Error Codes
| Code | HTTP Status | Description |
| :--- | :--- | :--- |
| `VALIDATION_ERROR` | 422 | Request body or parameters failed Pydantic validation. |
| `NOT_FOUND` | 404 | The requested resource (profile, document, session) does not exist. |
| `CONFLICT` | 409 | Resource already exists or state transition is invalid. |
| `STORAGE_ERROR` | 500 | Database or ChromaDB encountered an error. |
| `MODEL_UNAVAILABLE` | 503 | The configured AI provider is unreachable or timing out. |
| `CONFIGURATION_ERROR` | 500 | System is misconfigured (e.g., missing API key). |

## 4. Complete Endpoint Reference

### Profiles
*   **`GET /profiles`**: List all profiles.
*   **`POST /profiles`**: Create a new profile.
*   **`GET /profiles/{id}`**: Get profile details.
*   **`PATCH /profiles/{id}`**: Update profile name/settings.
*   **`DELETE /profiles/{id}`**: Delete profile and all associated data.
*   **`POST /profiles/{id}/export`**: Export profile data as ZIP.
*   **`POST /profiles/import`**: Import a profile ZIP.

**Example: `POST /profiles`**
*Request:*
```json
{ "name": "Computer Science" }
```
*Response:*
```json
{
  "data": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "name": "Computer Science",
    "created_at": "2026-06-13T10:00:00Z"
  },
  "error": null,
  "meta": null
}
```

### Documents
*   **`POST /profiles/{pid}/documents`**: Upload file (multipart/form-data).
*   **`GET /profiles/{pid}/documents`**: List documents.
*   **`GET /profiles/{pid}/documents/{id}`**: Get document metadata.
*   **`DELETE /profiles/{pid}/documents/{id}`**: Delete document and its chunks.
*   **`GET /profiles/{pid}/documents/{id}/status`**: Polling endpoint for ingestion progress.
*   **`POST /profiles/{pid}/documents/{id}/reprocess`**: Force re-extraction.

### Chat
*   **`GET /profiles/{pid}/sessions`**: List chat sessions.
*   **`POST /profiles/{pid}/sessions`**: Create new chat session.
*   **`GET /profiles/{pid}/sessions/{id}`**: Get session details and all messages.
*   **`PATCH /profiles/{pid}/sessions/{id}`**: Rename session.
*   **`DELETE /profiles/{pid}/sessions/{id}`**: Delete session.
*   **`POST /profiles/{pid}/sessions/{id}/messages`**: Send a message (Non-streaming fallback).
*   **`GET /profiles/{pid}/sessions/search`**: FTS5 search across all messages.
*   **`POST /profiles/{pid}/sessions/{id}/export`**: Export chat to Markdown.

### Roadmap
*   **`GET /profiles/{pid}/roadmaps`**: List roadmaps.
*   **`POST /profiles/{pid}/roadmaps`**: Generate a new roadmap. Body requires `document_id` and `mode`.
*   **`GET /profiles/{pid}/roadmaps/{id}`**: Get full roadmap DAG.
*   **`PATCH /profiles/{pid}/roadmaps/{id}/nodes/{nid}`**: Update node status (e.g., 'completed').
*   **`POST /profiles/{pid}/roadmaps/{id}/regenerate`**: Re-run AI generation.

### Knowledge Graph
*   **`GET /profiles/{pid}/graph`**: Get the entire graph (nodes and edges).
*   **`GET /profiles/{pid}/graph/nodes/{id}`**: Get specific node.
*   **`PATCH /profiles/{pid}/graph/nodes/{id}`**: Manually update node (e.g., mastery score).
*   **`GET /profiles/{pid}/graph/subgraph`**: Get graph focused around a node (depth=2).
*   **`GET /profiles/{pid}/graph/search`**: Find nodes by label.

### Memory
*   **`GET /profiles/{pid}/memory`**: List memory records (supports filtering by category).
*   **`POST /profiles/{pid}/memory`**: Create a manual memory record.
*   **`PATCH /profiles/{pid}/memory/{id}`**: Update memory record.
*   **`DELETE /profiles/{pid}/memory/{id}`**: Delete memory record.

### Quiz
*   **`POST /profiles/{pid}/quiz/generate`**: Generate a quiz for a specific topic/node.
*   **`POST /profiles/{pid}/quiz/{id}/submit`**: Submit answers and calculate score.
*   **`GET /profiles/{pid}/quiz/history`**: View past attempts.
*   **`GET /profiles/{pid}/quiz/{id}/results`**: Get specific quiz results.

### Analytics
*   **`GET /profiles/{pid}/analytics/overview`**: High-level stats.
*   **`GET /profiles/{pid}/analytics/heatmap`**: Activity calendar data.
*   **`GET /profiles/{pid}/analytics/mastery`**: Topic mastery distribution.
*   **`GET /profiles/{pid}/analytics/velocity`**: Learning velocity over time.
*   **`GET /profiles/{pid}/analytics/weaknesses`**: Top 5 weakest concepts.

### Settings
*   **`GET /settings`**: Get global settings.
*   **`PATCH /settings`**: Update global settings.
*   **`POST /settings/apikey`**: Set/update encrypted API key.
*   **`DELETE /settings/apikey`**: Remove API key.
*   **`GET /settings/models`**: List available models for selected provider.
*   **`POST /settings/test-connection`**: Verify provider connectivity.

**Implemented deviation (Milestones 06/07, reconciled in Milestone 08 cleanup)**: the provider/model selection flow was built as two combined endpoints instead of the six above. `app/routers/settings.py` delegates to `SettingsService`, which is now backed by the encrypted `KeyStore` (Fernet, `secrets.enc`) described in `17_SECURITY_AND_PRIVACY.md`, so this is a naming difference only, not a security gap:
*   **`GET /settings/providers`**: List all supported providers plus `active_provider`, `active_model`, and per-provider `key_set`/`active` flags. Serves the role of `GET /settings` + `GET /settings/models`.
*   **`POST /settings/provider`**: Body `{provider, api_key?, model?}`. Persists the provider/model choice to `.env` and, if an API key is supplied, encrypts and stores it via `KeyStore` (never written to `.env`/`settings.toml`/SQLite). Serves the role of `PATCH /settings` + `POST /settings/apikey`.
*   **`DELETE /settings/apikey?provider=...`**: Removes the stored key for a provider from the keystore.
*   `GET /settings/models` and `POST /settings/test-connection` are not implemented yet.

### Health
*   **`GET /health`**: Returns `{"status": "ok"}`. Used by startup script to detect when server is ready.
*   **`GET /health/storage`**: Checks SQLite and ChromaDB connectivity.

## 5. WebSocket API
**Endpoint**: `ws://127.0.0.1:8000/ws/chat/{session_id}?profile_id={pid}`

**Connection Lifecycle**:
1. Frontend opens connection.
2. Backend accepts and joins session room.
3. Frontend sends a message.
4. Backend streams tokens back.
5. Backend sends a `done` signal with final metadata.

## 6. Streaming Protocol
Events sent from the Backend to Frontend over WebSocket:
*   **`token`**: A piece of the generated text. `{"type": "token", "content": "The "}`
*   **`done`**: Stream finished. `{"type": "done", "message_id": "uuid"}`
*   **`citations`**: Sent right before `done`. `{"type": "citations", "data": [...]}`
*   **`error`**: Processing failed. `{"type": "error", "message": "Model timeout"}`

## 7. File Upload Specification
*   **Content-Type**: `multipart/form-data`
*   **Field Name**: `file`
*   **Accepted MIME Types**: `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `text/plain`, `image/*`
*   **Max Size**: Validated on the frontend (e.g., 50MB limit), backend handles streaming upload to avoid memory bloat.

## 8. Filtering and Pagination
Query parameters for list endpoints:
*   `page`: Integer (default 1)
*   `limit`: Integer (default 50)
*   `sort_by`: Field name (e.g., `created_at`)
*   `order`: `asc` or `desc`

## 9. API Versioning
All endpoints are prefixed with `/api/v1/`. The `v1` namespace is considered stable for the MVP. Any breaking schema changes in Phase 2/3 will be introduced under `/api/v2/`.

## 10. Cross-Origin Policy
CORS is explicitly configured in FastAPI `CORSMiddleware` to allow requests ONLY from local origins:
*   `http://localhost:5173` (Vite dev server)
*   `http://127.0.0.1:5173`
In production, since the frontend is served statically by FastAPI, requests originate from the same origin.

## 11. Build Contract for Endpoint Implementation
Every endpoint must have:
*   A Pydantic request schema where a body exists.
*   A Pydantic response schema matching the `data` payload.
*   A service-layer method that owns business logic.
*   Repository tests if the endpoint reads/writes SQLite.
*   Frontend TypeScript type and API wrapper in `frontend/src/api/`.

Routers must return the shared response envelope. They must not return raw ORM objects, ChromaDB payloads, or unvalidated dictionaries.

## 12. Core Payload Schemas
These are the minimum MVP payloads. Future fields may be added, but these names should remain stable.

### Profile Payloads
```json
{
  "ProfileCreate": {
    "name": "GATE CSE",
    "description": "Computer science exam prep",
    "goal": "GATE_CSE",
    "mode": "strict",
    "settings": {
      "pace": "normal",
      "depth": "deep"
    }
  },
  "ProfileResponse": {
    "id": "uuid",
    "name": "GATE CSE",
    "description": "Computer science exam prep",
    "goal": "GATE_CSE",
    "mode": "strict",
    "is_active": true,
    "color": "#3B82F6",
    "icon": "graduation-cap",
    "created_at": "2026-06-13T10:00:00Z",
    "updated_at": "2026-06-13T10:00:00Z"
  }
}
```

### Document Payloads
`POST /profiles/{pid}/documents` uses `multipart/form-data`.

Required form fields:
*   `file`: uploaded file.
*   `is_syllabus`: optional boolean, default `false`.
*   `roadmap_node_id`: optional UUID.

```json
{
  "DocumentResponse": {
    "id": "uuid",
    "profile_id": "uuid",
    "filename": "syllabus.pdf",
    "file_type": "pdf",
    "status": "indexing",
    "page_count": 12,
    "chunk_count": 0,
    "word_count": 3400,
    "is_syllabus": true,
    "roadmap_node_id": null,
    "uploaded_at": "2026-06-13T10:00:00Z",
    "indexed_at": null,
    "error_message": null
  }
}
```

### Chat Payloads
```json
{
  "ChatSessionCreate": {
    "title": "Recursion basics",
    "mode": "deep",
    "roadmap_node_id": "uuid-or-null"
  },
  "MessageCreate": {
    "content": "Explain recursion with a simple example.",
    "mode": "deep",
    "document_ids": ["uuid"]
  },
  "MessageResponse": {
    "id": "uuid",
    "session_id": "uuid",
    "role": "assistant",
    "content": "Recursion is...",
    "citations": [
      {
        "index": 1,
        "document_id": "uuid",
        "chunk_id": "uuid",
        "filename": "notes.pdf",
        "page": 4
      }
    ],
    "model_used": "gpt-4o",
    "latency_ms": 1350,
    "created_at": "2026-06-13T10:00:00Z"
  }
}
```

### Roadmap Payloads
```json
{
  "RoadmapCreate": {
    "document_id": "uuid",
    "mode": "strict",
    "title": "GATE CSE Roadmap"
  },
  "RoadmapNodeUpdate": {
    "status": "completed"
  },
  "RoadmapResponse": {
    "id": "uuid",
    "profile_id": "uuid",
    "name": "GATE CSE Roadmap",
    "mode": "strict",
    "version": 1,
    "is_active": true,
    "nodes": [],
    "edges": []
  }
}
```

### Memory Payloads
```json
{
  "MemoryCreate": {
    "category": "weakness",
    "subject": "recursion",
    "content": "Struggles to identify base cases.",
    "confidence": 0.8,
    "source": "manual"
  },
  "MemoryResponse": {
    "id": "uuid",
    "category": "weakness",
    "subject": "recursion",
    "content": "Struggles to identify base cases.",
    "confidence": 0.8,
    "source": "manual",
    "is_active": true,
    "created_at": "2026-06-13T10:00:00Z",
    "updated_at": "2026-06-13T10:00:00Z"
  }
}
```

### Quiz Payloads
```json
{
  "QuizGenerateRequest": {
    "roadmap_node_id": "uuid",
    "mode": "practice",
    "question_count": 10,
    "time_limit_seconds": null
  },
  "QuizSubmitRequest": {
    "answers": [
      {
        "question_id": "q1",
        "answer": "A"
      }
    ]
  },
  "QuizResultResponse": {
    "attempt_id": "uuid",
    "score": 0.8,
    "correct_count": 8,
    "total_questions": 10,
    "feedback": "Review base cases and stack traces.",
    "mastery_delta": 0.12
  }
}
```

## 13. WebSocket Message Contract
Client-to-server messages:
```json
{
  "type": "message",
  "content": "Explain recursion.",
  "mode": "deep",
  "document_ids": [],
  "roadmap_node_id": "uuid-or-null"
}
```

Server-to-client events:
| Type | Required Fields | Meaning |
| :--- | :--- | :--- |
| `ack` | `client_message_id`, `server_message_id` | User message accepted and persisted. |
| `token` | `content` | One streamed assistant token/string fragment. |
| `citations` | `data` | Citation list for the final response. |
| `done` | `message_id`, `latency_ms`, `model_used` | Stream completed and assistant message persisted. |
| `document_progress` | `doc_id`, `status`, `progress` | Async ingestion progress update. |
| `error` | `code`, `message`, `details` | Structured recoverable error. |

If the socket disconnects mid-generation, the backend should save the partial assistant message with `status="incomplete"` and allow the frontend to reconnect and refresh the session.

## 14. Error Mapping Requirements
| Exception | HTTP Status | Error Code |
| :--- | :--- | :--- |
| `ValidationError` | 422 | `VALIDATION_ERROR` |
| `NotFoundError` | 404 | `NOT_FOUND` |
| `ConflictError` | 409 | `CONFLICT` |
| `StorageError` | 500 | `STORAGE_ERROR` |
| `ModelError` | 503 | `MODEL_UNAVAILABLE` |
| `ConfigurationError` | 500 | `CONFIGURATION_ERROR` |

Error `details` should include machine-actionable fields where possible, such as `field`, `resource_id`, `retry_after_seconds`, or `provider`.
