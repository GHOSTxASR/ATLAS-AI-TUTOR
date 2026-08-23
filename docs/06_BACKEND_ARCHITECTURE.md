# 06. Backend Architecture

## 1. Backend Overview
Atlas runs a single Python FastAPI process served by Uvicorn on `127.0.0.1:8000`. It is entirely self-contained, handling HTTP requests, WebSocket streaming, and background task scheduling within the same process.

## 2. Application Factory
`app/main.py` uses the Application Factory pattern. It initializes the FastAPI instance, configures CORS, applies middleware, and imports all routers. It uses the `lifespan` context manager to handle startup/shutdown sequences.

## 3. Startup Sequence
Defined in `lifespan.py`:
1.  **Config Load**: Parse `settings.toml` and decrypt API keys.
2.  **DB Migration**: Run `alembic upgrade head` programmatically.
3.  **ChromaDB Init**: Instantiate persistent client and ensure collections exist.
4.  **Graph Load**: Parse JSON graph into NetworkX DiGraph.
5.  **Scheduler Start**: Initialize APScheduler for background tasks.
6.  **Yield**: FastAPI starts accepting requests.
7.  **Shutdown**: Flush Graph to JSON, shutdown APScheduler, close DB connections.

## 4. Router Organization
All routers are located in `app/routers/` and prefixed with `/api/v1/`:
*   `profiles.py`, `documents.py`, `chat.py`, `roadmap.py`, `graph.py`, `memory.py`, `quiz.py`, `analytics.py`, `settings.py`, `health.py`.
*   `ws_chat.py`: Handles the WebSocket connections specifically.

## 5. Service Layer Pattern
Architecture follows: **Router → Service → Repository → Database**.
*   **Routers**: Parse requests, handle HTTP errors, call Services.
*   **Services**: Business logic. Coordinate multiple repositories or external APIs (e.g., RAG pipeline).
*   **Repositories**: Exclusively handle SQLAlchemy queries. No business logic.
*   **DataLayer**: The actual SQLite/ChromaDB drivers.

## 6. Complete Service Specifications

### ProfileService
*   **Purpose**: Manages user contexts.
*   **Methods**: `create_profile()`, `get_profile()`, `export_profile()`.

### IngestionService
*   **Purpose**: Coordinates document processing.
*   **Methods**: `process_upload()` (saves file, triggers extractor), `reprocess_document()`.
*   **Dependencies**: DocumentRepo, DocumentExtractor pipeline.

### ChatService
*   **Purpose**: Manages session history.
*   **Methods**: `create_session()`, `save_message()`, `get_session_history()`.
*   **Dependencies**: ChatRepo.

### RoadmapService
*   **Purpose**: Generates and tracks learning paths.
*   **Methods**: `generate_roadmap()`, `update_node_status()`, `compute_progress()`.
*   **Dependencies**: RoadmapRepo, SyllabusParser.

### GraphService
*   **Purpose**: Interface to the in-memory knowledge graph.
*   **Methods**: `get_subgraph()`, `update_mastery()`, `search_nodes()`.
*   **Dependencies**: GraphStore.

### MemoryService
*   **Purpose**: Long-term intelligence extraction.
*   **Methods**: `extract_memories()` (calls LLM), `retrieve_relevant()` (queries ChromaDB).
*   **Dependencies**: MemoryRepo, VectorStore.

### TutorOrchestrator
*   **Purpose**: The central "brain" for chat.
*   **Methods**: `handle_chat_turn()`.
*   **Dependencies**: ChatService, RAGService, MemoryService, RoadmapService, ModelAbstractionLayer.

## 7. Repository Layer
Repositories (e.g., `DocumentRepo`, `MemoryRepo`) encapsulate SQLAlchemy statements.
Example `DocumentRepo.get_by_status(status="queued")` returns ORM models. This abstraction makes it easier to mock the database during unit testing.

## 8. Dependency Injection
FastAPI's `Depends()` is heavily used in routers to inject services and DB sessions.
*   `get_db()`: Yields an `AsyncSession`.
*   `get_vector_store()`: Returns the ChromaDB client.
*   `get_profile(profile_id)`: Validates the profile exists before proceeding.

## 9. Middleware Stack
1.  **CORS**: `CORSMiddleware` (local origins only).
2.  **Request ID**: Injects a unique UUID into the `asgi` scope for request tracing.
3.  **Timing**: Calculates time taken for a request and logs it.
4.  **Error Handler**: Captures unhandled `Exception` and returns a standardized 500 JSON.
5.  **Static Files**: Serves the frontend bundle if running in production mode.

## 10. Async Architecture
The entire backend uses Python `async/await`.
*   `AsyncSession` for SQLAlchemy (uses `aiosqlite`).
*   `httpx.AsyncClient` for LLM provider calls.
*   WebSocket endpoints use `async for` generators to stream tokens without blocking the event loop.

## 11. Background Task Scheduler
Uses `APScheduler` (AsyncIOScheduler).
Tasks registered:
*   `embedding_task`: Runs every 5 seconds. Polls `chunk_embedding_queue` and calls `Embedder`.
*   `memory_extraction_task`: Triggered asynchronously after a chat turn finishes.
*   `graph_enrichment_task`: Triggered after a document finishes indexing.
*   `backup_task`: Runs every 24 hours.

## 12. Error Hierarchy
Custom Python Exceptions mapping to HTTP codes:
*   `AtlasError` (Base)
    *   `ValidationError` -> 422
    *   `NotFoundError` -> 404
    *   `ConflictError` -> 409
    *   `StorageError` -> 500
    *   `ModelError` -> 503

## 13. Configuration System
Uses Pydantic `BaseSettings` reading from `settings.toml`. Singleton instance loaded at startup.
Keys include: `db_path`, `chroma_path`, `default_model`, `tesseract_path`, `log_level`.

## 14. Security Implementation
*   **Keystore**: API keys are not stored in plaintext. `settings/apikey` endpoint encrypts the key using `cryptography.Fernet`. The encryption key is derived from a machine-specific UUID.
*   **Network Binding**: Uvicorn is strictly bound to `127.0.0.1`.
*   **Path Traversal**: File upload paths are sanitized.

## 15. Logging Implementation
Uses `loguru`. Logs are written to `~/.atlas/logs/`.
Log rotation is set to 10MB or 1 week.
Format includes timestamp, log level, module, and `request_id` for tracing errors across asynchronous boundaries.

## 16. Schema Validation
Pydantic v2 models in `app/schemas/`.
Strict separation:
*   `DocumentCreate`: Fields allowed on POST.
*   `DocumentResponse`: Full serialization (includes IDs and timestamps).
Prevents over-posting vulnerabilities.

## 17. Service Boundary Enforcement
*   **TutorOrchestrator** is the top-level composer. It calls other Services.
*   **Services** NEVER call the TutorOrchestrator.
*   **Services** NEVER call Repositories outside their domain (e.g., `ChatService` shouldn't call `DocumentRepo`).

## 18. Testing Architecture
*   **Framework**: `pytest` and `pytest-asyncio`.
*   **Mocking**: AI provider responses are mocked using `pytest-httpx` or by overriding the `ModelAbstractionLayer`.
*   **Database**: Tests run against an in-memory SQLite database (`sqlite+aiosqlite:///:memory:`).

## 19. pyproject.toml
Contains project metadata, build system requirements, and configurations for tools like `pytest`, `black`, `ruff`, and `mypy`.

## 20. requirements.txt
Pinned dependencies to guarantee reproducibility.
```text
fastapi==0.111.0
uvicorn==0.29.0
sqlalchemy==2.0.30
alembic==1.13.1
aiosqlite==0.20.0
chromadb==0.5.0
networkx==3.3
pymupdf==1.24.4
pytesseract==0.3.10
sentence-transformers==2.7.0
openai==1.30.1
anthropic==0.26.0
httpx==0.27.0
apscheduler==3.10.4
cryptography==42.0.7
pydantic==2.7.1
loguru==0.7.2
```

## 21. Master Plan Backend Contract Addendum

### Application Factory Requirements
`create_app()` in `app/main.py` must:
1. Instantiate FastAPI with title/version from `Settings`.
2. Attach exception handlers before routers are included.
3. Add CORS only for local origins.
4. Add request ID and timing middleware.
5. Include every `/api/v1` router.
6. Include the WebSocket chat router.
7. Mount the frontend `dist` directory only when running in production and the directory exists.

### Required Exception Classes
Create `app/exceptions.py` with:
*   `AtlasError(code: str, message: str, status_code: int, details: dict | None)`
*   `ValidationError`
*   `NotFoundError`
*   `ConflictError`
*   `StorageError`
*   `ModelError`
*   `ConfigurationError`

The global exception handler must convert these to the API envelope. Unexpected exceptions become `STORAGE_ERROR` or `INTERNAL_ERROR` with stack traces only in logs.

### Service Method Minimums
| Service | Required Methods |
| :--- | :--- |
| `ProfileService` | `create_profile`, `list_profiles`, `get_profile`, `set_active_profile`, `update_profile`, `delete_profile`, `export_profile`, `import_profile` |
| `IngestionService` | `process_upload`, `get_document`, `list_documents`, `get_status`, `reprocess_document`, `delete_document` |
| `ChatService` | `create_session`, `list_sessions`, `get_session_with_messages`, `rename_session`, `archive_session`, `save_user_message`, `save_assistant_message`, `search_messages`, `export_session` |
| `RoadmapService` | `generate_roadmap`, `get_active_roadmap`, `get_roadmap`, `update_node_status`, `get_next_node`, `compute_progress`, `regenerate`, `archive` |
| `GraphService` | `get_full_graph`, `get_node`, `get_subgraph`, `search_nodes`, `update_mastery`, `add_concept`, `link_concepts`, `export_graph` |
| `MemoryService` | `extract_memories`, `retrieve_relevant`, `list_records`, `create_manual`, `update`, `delete`, `decay_old_records` |
| `QuizService` | `generate_quiz`, `submit_answers`, `get_history`, `get_results`, `update_mastery_from_score` |
| `AnalyticsService` | `record_event`, `overview`, `heatmap`, `mastery`, `velocity`, `weaknesses`, `model_costs` |
| `SettingsService` | `get_settings`, `update_settings`, `set_api_key`, `delete_api_key`, `list_models`, `test_connection` |

### Transaction Rules
*   A request that writes multiple SQLite tables must use one transaction at the service layer.
*   File-system writes should happen before database commit only when they can be safely deleted on rollback.
*   ChromaDB writes should happen after SQLite metadata exists. If ChromaDB write fails, update the SQLite status/error field.
*   Graph JSON writes should use atomic temp-file replacement and an `asyncio.Lock`.
*   Profile deletion must delete/disable data in this order: scheduler jobs, ChromaDB collections, graph nodes, profile files, SQLite rows.

### Background Task Idempotency
| Task | Idempotency Key | Duplicate Prevention |
| :--- | :--- | :--- |
| `embedding_task` | `chunk_embedding_queue.id` | Do not insert vector if `embedding_id` already stored. |
| `memory_extraction_task` | `session_id` + assistant `message_id` | Store extraction source in `memory_records.source_id`. |
| `graph_enrichment_task` | `document_id` or `message_id` | Merge by normalized label and edge tuple. |
| `backup_task` | backup timestamp | Write to temp dir, then rename. |

Failed tasks should increment retry counters where persisted. Non-critical post-chat tasks must log errors and never alter the saved chat response.

### Configuration Loading Rules
*   `settings.toml` is canonical for runtime configuration.
*   Environment variables may override settings only for CI/dev and should be documented in `.env.example`.
*   API keys are never stored in `settings.toml`; they live in encrypted `secrets.enc`.
*   Model provider settings should be reloadable through `SettingsService` without restarting the app where practical.

### Backend Test Minimums
*   Unit tests for pure utilities: chunking, text cleanup, path sanitization, token counting, response envelope helpers.
*   Repository tests for each domain using temporary SQLite.
*   Service tests for profile deletion cascade, document reprocess, roadmap status transition, memory dedupe, and quiz mastery update.
*   Router tests for validation errors and response envelope shape.
*   WebSocket test for token streaming, done event, and model error event.
