# 16. Testing Strategy

## 1. Purpose
This document defines the complete testing approach for LearningOS. It turns the implementation plan into concrete test layers, fixtures, commands, quality gates, and acceptance checks.

Related documents:
* `03_DATABASE_DESIGN.md`: schema and migration requirements.
* `04_API_SPECIFICATION.md`: endpoint and WebSocket contracts.
* `05_FRONTEND_ARCHITECTURE.md`: frontend state and page behavior.
* `06_BACKEND_ARCHITECTURE.md`: services, tasks, and transaction rules.
* `13_DEPLOYMENT.md`: setup and release verification.

## 2. Testing Principles
* Test behavior at the lowest useful layer.
* Mock external AI providers by default.
* Use real SQLite migrations in integration tests.
* Use temporary ChromaDB directories for vector tests.
* Keep unit tests fast and deterministic.
* Make every background task idempotency rule testable.
* Never require a real API key for CI.
* E2E tests should cover the core learner journey, not every branch.

## 3. Test Pyramid
| Layer | Purpose | Target Speed | Examples |
| :--- | :--- | :--- | :--- |
| Unit | Pure logic and isolated services | milliseconds | chunker, token budget, memory dedupe |
| Integration | Real DB/files/vector store with mocked model | seconds | upload -> queue -> embed, chat persistence |
| API | FastAPI routes and envelopes | seconds | validation, status codes, payload shape |
| WebSocket | Streaming protocol | seconds | token/done/error events |
| Frontend unit | Hooks/components | milliseconds | API client, stores, render states |
| E2E | Browser user flows | minutes | setup, upload, chat, roadmap |
| Release smoke | Clean-machine behavior | manual/automated | setup.bat/start.bat validation |

## 4. Backend Test Stack
Required tools:
* `pytest`
* `pytest-asyncio`
* `httpx`
* `pytest-httpx` or equivalent HTTP mocking
* FastAPI `TestClient` or `httpx.AsyncClient`
* temporary SQLite files for integration tests
* temporary directories for data, uploads, graph, and ChromaDB

Recommended test structure:
```text
backend/app/tests/
├── unit/
├── integration/
├── api/
├── websocket/
├── fixtures/
└── conftest.py
```

## 5. Frontend Test Stack
Required tools:
* Vitest
* React Testing Library
* MSW for API mocking
* Playwright for E2E
* TypeScript type checking through `tsc --noEmit`

Recommended structure:
```text
frontend/src/
├── __tests__/
├── test/
│   ├── mocks/
│   └── fixtures/
└── pages/
```

Playwright structure:
```text
frontend/e2e/
├── setup.spec.ts
├── documents.spec.ts
├── chat.spec.ts
├── roadmap.spec.ts
└── fixtures/
```

## 6. Test Data and Fixtures

### Required File Fixtures
Store small fixtures in `backend/app/tests/fixtures/`:
* `sample_text.pdf`: text PDF with 2-3 pages.
* `sample_syllabus.pdf`: predictable hierarchy.
* `sample_notes.txt`: plain text.
* `sample_doc.docx`: headings and table.
* `sample_image.png`: OCR fixture, optional if Tesseract is available.
* `malformed.pdf`: corrupted or invalid file.

### Model Response Fixtures
Required JSON fixtures:
* `chat_completion_stream.jsonl`
* `embedding_response.json`
* `memory_extraction_valid.json`
* `memory_extraction_invalid.txt`
* `roadmap_strict_response.json`
* `roadmap_adaptive_response_with_cycle.json`
* `quiz_generation_response.json`
* `quiz_scoring_response.json`
* `graph_enrichment_response.json`

### Database Fixtures
Use factories instead of static database dumps:
* `profile_factory`
* `document_factory`
* `chat_session_factory`
* `roadmap_factory`
* `memory_factory`
* `quiz_attempt_factory`

Factories should create valid records with UUIDs and UTC timestamps.

## 7. Backend Unit Tests

### Utilities
Test:
* UUID generation returns valid UUIDv4 strings.
* UTC helper returns timezone-aware ISO strings.
* File hash is stable.
* Filename sanitization removes traversal and control characters.
* Safe write uses temp-file replacement where required.
* Settings path expansion handles `~`.

### Chunker
Test:
* Chunk size stays within configured token budget.
* Overlap is applied.
* Sentence boundary snapping works.
* Empty input returns no chunks.
* Very long sentence still chunks safely.
* Metadata includes page and offsets.

### Token Budget
Test:
* Latest user message is always preserved.
* System prompt is always preserved.
* Oldest chat messages are dropped first.
* Low-ranked RAG chunks are dropped before high-ranked chunks.
* Low-confidence memory is dropped before high-confidence memory.

### Citation Tracker
Test:
* Valid markers map to chunks.
* Unknown markers are removed or flagged.
* Duplicate markers map once.
* Citation payload includes filename/page/chunk preview.

### Memory Logic
Test:
* Similar memory above threshold reinforces existing record.
* Contradiction lowers confidence.
* Decay removes low-confidence automatic memories.
* Manual memories do not auto-delete by decay.
* Deleted memory is excluded from retrieval.

### Roadmap Logic
Test:
* Strict mode preserves order.
* Unlock logic requires all hard prerequisites.
* Skipped nodes unlock dependents.
* Regeneration migrates matching progress.
* Adaptive cycles are repaired or rejected.

### Graph Logic
Test:
* Normalized label match merges concepts.
* Duplicate edge increases weight/evidence.
* Subgraph depth is honored.
* Corrupt graph file is quarantined.

## 8. Backend Integration Tests

### Database and Migration
Test:
1. Create empty temp DB.
2. Run Alembic `upgrade head`.
3. Verify all tables exist.
4. Verify required indexes exist.
5. Verify FTS5 tables/triggers exist.
6. Verify foreign-key cascades.

### Profile Flow
Test:
* Create profile.
* Set active profile.
* Switch profile.
* Delete profile cascade.
* Export profile excludes API keys.
* Import profile creates new IDs where required.

### Document Flow
Test:
* Upload text PDF.
* Extract text.
* Chunk.
* Queue embeddings.
* Process embedding task with mocked embeddings.
* Verify ChromaDB vectors.
* Delete document and verify cleanup.

### RAG Flow
Test:
* Insert document chunks.
* Query retriever.
* Verify profile isolation.
* Verify reranking/MMR output order.
* Assemble context within budget.

### Chat Flow
Test:
* Create session.
* Save user message.
* Mock model stream.
* Save assistant message.
* Store citations/retrieved chunks.
* Dispatch memory and graph tasks without blocking response.

### Quiz Flow
Test:
* Generate quiz with mocked model JSON.
* Submit answers.
* Score result.
* Update roadmap mastery.
* Update graph mastery.
* Create memory record.
* Write analytics event.

## 9. API Tests
Every route must be tested for:
* Success response envelope.
* Validation error envelope.
* Not found behavior.
* Profile isolation.
* Invalid state transition where applicable.

Required endpoint groups:
* Profiles.
* Documents.
* Chat sessions/messages.
* Roadmaps.
* Graph.
* Memory.
* Quiz.
* Analytics.
* Settings.
* Health.

Response envelope assertion:
```json
{
  "data": {},
  "error": null,
  "meta": null
}
```

Error envelope assertion:
```json
{
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "string",
    "details": {}
  },
  "meta": null
}
```

## 10. WebSocket Tests
Required cases:
* Connect to valid session.
* Send message event.
* Receive `ack`.
* Receive multiple `token` events.
* Receive `citations`.
* Receive `done`.
* Provider failure emits `error`.
* Disconnect mid-stream saves incomplete assistant message.
* Invalid profile/session closes or errors gracefully.

## 11. Frontend Unit and Component Tests

### API Client
Test:
* Base URL selection.
* Envelope unwrapping.
* Error normalization.
* Multipart upload wrapper.
* WebSocket URL creation.

### Stores
Test:
* Active profile persistence.
* Profile switch invalidates expected query keys.
* UI context panel persistence.
* Chat store session selection.

### Hooks
Test:
* `useStreaming` handles `ack`, `token`, `citations`, `done`, and `error`.
* `useDocuments` merges polling and progress events.
* `useRoadmap` optimistic update rolls back on failure.
* `useGraph` transforms backend graph into D3 node/link shape.

### Components
Test:
* Loading/empty/error states.
* Icon buttons have accessible labels.
* Modals trap focus.
* Tables render action columns.
* Chat message renders markdown/citations.

## 12. End-to-End Tests

### MVP Happy Path
1. Start backend and frontend.
2. Visit app.
3. Complete setup.
4. Create profile.
5. Upload text PDF.
6. Wait for indexed status.
7. Start chat.
8. Ask "Summarize the document."
9. Verify streamed answer.
10. Verify citation visible.
11. Refresh page.
12. Verify chat persisted.

### Roadmap Path
1. Upload syllabus.
2. Mark as syllabus.
3. Generate Strict roadmap.
4. Verify nodes render.
5. Start first node.
6. Mark node complete.
7. Verify progress changes.

### Memory Path
1. Chat with mocked response that triggers weakness extraction.
2. Wait for task.
3. Visit Memory page.
4. Verify memory appears.
5. Edit memory.
6. Delete memory.
7. Verify it disappears.

### Settings Path
1. Open Settings.
2. Enter API key.
3. Mock connection test success.
4. Change model setting.
5. Verify warning when embedding model changes.

## 13. Performance Tests
Required benchmarks:
| Area | Target |
| :--- | :--- |
| Health endpoint | < 100ms |
| Document list | < 300ms for 500 docs |
| RAG retrieval | < 500ms before model call |
| Chat time to first token | < 2s excluding provider latency |
| Text PDF indexing | 100 pages < 15s extraction/chunking target |
| Graph render | interactive at 1,000 nodes |

Performance tests can be manual at first, but TASK-063 must document measured results.

## 14. Security and Privacy Tests
Required checks:
* Backend binds to `127.0.0.1`.
* CORS rejects non-local origins.
* API key never appears in logs.
* API key stored encrypted.
* Path traversal filenames are rejected/sanitized.
* Unsupported file types rejected.
* Profile deletion removes SQLite rows, files, and ChromaDB collections.
* Export ZIP excludes secrets.
* Logs do not include raw document text or memory content by default.

## 15. CI Quality Gates
Minimum CI commands:
```bash
# Backend
ruff check backend
pytest backend/app/tests

# Frontend
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
```

Optional/release CI:
```bash
npm --prefix frontend run e2e
```

## 16. Coverage Targets
Targets are pragmatic, not vanity metrics:
| Area | Target |
| :--- | :--- |
| Pure backend utilities | 90%+ |
| Services | 80%+ for MVP paths |
| Repositories | meaningful query/cascade coverage |
| Routers | every route has at least success and one failure test |
| Frontend hooks/stores | 80%+ |
| Components | critical states covered |
| E2E | core learner journey covered |

## 17. Release Test Checklist
Before release:
1. Run full CI.
2. Run production frontend build.
3. Run `setup.bat` on clean Windows profile.
4. Run `start.bat`.
5. Complete setup.
6. Upload PDF.
7. Chat with citation.
8. Restart app.
9. Confirm data persists.
10. Confirm logs contain no secrets.
11. Export profile.
12. Delete profile and confirm data cleanup.

## 18. Definition of Done for Tests
A feature is not done until:
* Unit tests cover core logic.
* API/service integration tests cover persistence behavior.
* Frontend tests cover loading/empty/error/success states.
* Any new background task has idempotency tests.
* Documentation lists relevant manual checks if automation is not practical yet.

