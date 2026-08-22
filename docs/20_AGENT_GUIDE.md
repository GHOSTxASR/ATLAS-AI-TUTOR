# 20. Agent Guide

## 1. Project Overview
LearningOS is a local-first AI tutoring and learning operating system. It runs on the user's machine and combines profile-specific learning history, uploaded documents, RAG, long-term learner memory, roadmaps, quizzes, analytics, and a knowledge graph.

The system is not a generic chatbot. It is a persistent learning workspace where the AI tutor can:
* Answer from uploaded documents with citations.
* Remember learner strengths, weaknesses, preferences, and assessment outcomes.
* Follow or generate a roadmap.
* Update mastery through quizzes and assessments.
* Build a knowledge graph of concepts and relationships.
* Keep all user data local except explicit outbound model-provider calls.

Primary source documents:
* `00_IMPLEMENTATION_PLAN.md`: master source of truth.
* `01_ARCHITECTURE.md`: system architecture and service boundaries.
* `02_REPOSITORY_STRUCTURE.md`: expected files and folders.
* `03_DATABASE_DESIGN.md`: database schema and persistence.
* `04_API_SPECIFICATION.md`: API and WebSocket contracts.
* `05_FRONTEND_ARCHITECTURE.md` and `15_UI_UX_SPEC.md`: frontend and UI behavior.
* `06_BACKEND_ARCHITECTURE.md`: backend services, transactions, and background tasks.
* `07_RAG_ARCHITECTURE.md`, `18_MODEL_INTEGRATION.md`, and `19_VECTOR_DATABASE_DESIGN.md`: retrieval, model, and vector systems.
* `16_TESTING_STRATEGY.md`: required test coverage.
* `17_SECURITY_AND_PRIVACY.md`: security and privacy rules.

If documents conflict, follow `00_IMPLEMENTATION_PLAN.md` first, then update the split doc that drifted.

## 2. Repository Structure
The repository is a monorepo with a FastAPI backend and React/Vite frontend.

Required root structure:
```text
learningos/
├── README.md
├── setup.bat
├── setup.sh
├── start.bat
├── start.sh
├── start-dev.bat
├── update.bat
├── .env.example
├── .gitignore
├── backend/
├── frontend/
└── docs/
```

Backend structure:
```text
backend/
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── alembic.ini
├── alembic/
└── app/
    ├── main.py
    ├── config.py
    ├── dependencies.py
    ├── exceptions.py
    ├── lifespan.py
    ├── routers/
    ├── services/
    ├── pipelines/
    ├── rag/
    ├── models/
    ├── graph/
    ├── db/
    ├── schemas/
    ├── tasks/
    ├── security/
    ├── utils/
    └── tests/
```

Frontend structure:
```text
frontend/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── index.html
├── public/
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── router.tsx
    ├── api/
    ├── stores/
    ├── hooks/
    ├── components/
    ├── pages/
    ├── types/
    └── styles/
```

Local user data lives outside the repository:
```text
~/.learningos/
├── data/
├── profiles/
├── config/
├── logs/
└── backups/
```

Do not store user databases, ChromaDB files, logs, raw uploads, extracted documents, or secrets in git.

## 3. Coding Standards

### General Standards
* Keep changes scoped to the task.
* Prefer existing patterns over new abstractions.
* Add abstractions only when they remove real duplication or clarify ownership.
* Use explicit, typed data contracts at service/API boundaries.
* Keep user-facing errors clear and actionable.
* Never swallow errors silently unless the relevant doc explicitly says a background task is best-effort.

### Python Standards
* Python version: 3.11+.
* Use FastAPI, Pydantic v2, SQLAlchemy async, Alembic, ChromaDB, NetworkX, APScheduler.
* Files and functions use `snake_case`.
* Classes use `PascalCase`.
* Routers must not contain business logic.
* Services own business logic.
* Repositories own SQLAlchemy queries.
* Pydantic schemas own request/response validation.
* Use async APIs for database, HTTP, and WebSocket code.
* Use central utilities for UUIDs, UTC timestamps, path handling, hashing, and logging.

### TypeScript/React Standards
* React components use `PascalCase.tsx`.
* Hooks use `useThing.ts`.
* API wrappers live in `frontend/src/api/`.
* Server state belongs to TanStack Query.
* UI/session state belongs to Zustand.
* Do not duplicate backend records in Zustand.
* All API payloads need TypeScript types matching Pydantic schemas.
* All icon-only buttons need `aria-label` and tooltip text.

### Documentation Standards
When implementation changes behavior, update the relevant doc in the same change:
* Schema changes -> `03_DATABASE_DESIGN.md`.
* Endpoint changes -> `04_API_SPECIFICATION.md`.
* Frontend behavior -> `05_FRONTEND_ARCHITECTURE.md` and/or `15_UI_UX_SPEC.md`.
* Backend service/task behavior -> `06_BACKEND_ARCHITECTURE.md`.
* RAG changes -> `07_RAG_ARCHITECTURE.md`.
* Memory changes -> `08_MEMORY_SYSTEM.md`.
* Graph changes -> `09_KNOWLEDGE_GRAPH.md`.
* Document ingestion changes -> `10_DOCUMENT_PROCESSING.md`.
* Roadmap changes -> `11_ROADMAP_ENGINE.md`.
* Tutor/model changes -> `12_AI_TUTOR_ENGINE.md` or `18_MODEL_INTEGRATION.md`.
* Deployment changes -> `13_DEPLOYMENT.md`.
* Testing changes -> `16_TESTING_STRATEGY.md`.
* Security changes -> `17_SECURITY_AND_PRIVACY.md`.

## 4. Architecture Rules

### Source-of-Truth Rules
* `00_IMPLEMENTATION_PLAN.md` is canonical.
* Split docs are implementation references.
* If code, split docs, and master plan disagree, fix the code and split docs to match the master plan unless the user explicitly approves changing the master plan.

### Process Rules
* Development mode uses two processes: FastAPI on `127.0.0.1:8000` and Vite on `127.0.0.1:5173`.
* Production mode serves the frontend from FastAPI on `127.0.0.1:8000`.
* Backend must not bind to `0.0.0.0`.
* Frontend must not read local files directly.
* All file, database, model, graph, and vector operations go through backend APIs/services.

### Backend Layering
Required flow:
```text
Router -> Service -> Repository -> Database
```

Rules:
* Routers validate transport concerns and return response envelopes.
* Services coordinate workflows and transactions.
* Repositories only query SQLite.
* Pipeline modules process data and should not own persistence decisions.
* `TutorOrchestrator` is the only component that composes profile, roadmap, memory, RAG, history, prompts, and model calls for chat.

### Frontend Layering
Required flow:
```text
Page/Component -> Hook/Store -> API Wrapper -> Backend API
```

Rules:
* Components do not call `fetch` or Axios directly.
* Pages use hooks and typed API wrappers.
* Profile-scoped queries wait for `activeProfileId`.
* All major pages implement loading, empty, error, and populated states.

### Persistence Rules
* SQLite is the source of truth for structured state.
* ChromaDB is the vector index, not the source of truth.
* Graph JSON/NetworkX owns concept relationships.
* Raw/extracted files live under `~/.learningos/profiles/{profile_id}/`.
* `settings.toml` is runtime config.
* `secrets.enc` stores encrypted API keys.

### Background Task Rules
All background tasks must be idempotent:
* Embedding task keyed by queue row or chunk ID.
* Memory extraction keyed by session/message source.
* Graph enrichment keyed by document/message source.
* Backup keyed by timestamp/temp directory.

Post-chat memory and graph tasks must not block the chat response.

## 5. File Ownership

### Backend Domains
| Domain | Owned Files |
| :--- | :--- |
| Profiles | `schemas/profile.py`, `repositories/profile_repo.py`, `services/profile_service.py`, `routers/profiles.py` |
| Documents | `schemas/document.py`, `repositories/document_repo.py`, `pipelines/document_extractor.py`, `pipelines/ocr_pipeline.py`, `pipelines/chunker.py`, `services/ingestion_service.py`, `routers/documents.py` |
| Embeddings/Vectors | `pipelines/embedder.py`, `repositories/embedding_repo.py`, `tasks/embedding_task.py`, `rag/retriever.py`, optional `vector_store.py` |
| Chat | `schemas/chat.py`, `repositories/chat_repo.py`, `services/chat_service.py`, `routers/chat.py`, `routers/ws_chat.py` |
| Tutor | `services/tutor_orchestrator.py`, `models/`, `rag/` |
| Memory | `schemas/memory.py`, `repositories/memory_repo.py`, `services/memory_service.py`, `tasks/memory_extraction_task.py` |
| Roadmap | `schemas/roadmap.py`, `repositories/roadmap_repo.py`, `pipelines/syllabus_parser.py`, `services/roadmap_service.py`, `routers/roadmap.py` |
| Graph | `graph/graph_store.py`, `graph/graph_query.py`, `graph/graph_enricher.py`, `services/graph_service.py`, `routers/graph.py` |
| Quiz | `schemas/quiz.py`, `repositories/quiz_repo.py`, `services/quiz_service.py`, `routers/quiz.py` |
| Analytics | `repositories/analytics_repo.py`, `services/analytics_service.py`, `routers/analytics.py` |
| Settings/Security | `config.py`, `security/keystore.py`, `services/settings_service.py`, `routers/settings.py` |
| Startup/Tasks | `main.py`, `lifespan.py`, `tasks/scheduler.py`, `tasks/backup_task.py` |

### Frontend Domains
| Domain | Owned Files |
| :--- | :--- |
| API | `src/api/client.ts`, domain files in `src/api/` |
| Types | `src/types/` |
| Profile state | `src/stores/profileStore.ts`, profile API/hooks/components |
| Chat | `src/stores/chatStore.ts`, `src/hooks/useStreaming.ts`, `src/pages/ChatPage.tsx`, `src/components/chat/` |
| Documents | `src/pages/DocumentsPage.tsx`, `src/hooks/useDocuments.ts`, `src/components/documents/` |
| Roadmap | `src/pages/RoadmapPage.tsx`, `src/hooks/useRoadmap.ts`, `src/components/roadmap/` |
| Graph | `src/pages/GraphPage.tsx`, `src/hooks/useGraph.ts`, `src/components/graph/` |
| Memory | `src/pages/MemoryPage.tsx` |
| Quiz | `src/pages/QuizPage.tsx` |
| Analytics | `src/pages/AnalyticsPage.tsx` |
| Settings | `src/pages/SettingsPage.tsx`, `src/stores/settingsStore.ts` |
| UI/Layout | `src/components/layout/`, `src/components/common/`, `src/styles/` |

When adding a feature, update the full ownership chain: schema, model, migration, repository, service, router, frontend type, API wrapper, hook/store, component/page, tests, docs.

## 6. Build Order
Follow this order unless the user explicitly instructs otherwise.

### Phase A: Foundation
1. Repository root files.
2. Backend project setup.
3. FastAPI app factory.
4. Config loading.
5. Health endpoint.
6. Async database setup.
7. Alembic setup.
8. Initial SQLAlchemy models and migration.
9. Utility functions.
10. Keystore.

### Phase B: Profiles and Settings
1. Profile repository/service/router.
2. Settings service/router.
3. API key encryption.
4. Frontend setup flow.
5. Profile store/switcher.

### Phase C: Document Ingestion
1. Document repository.
2. Extractors for PDF/DOCX/TXT.
3. OCR pipeline as optional.
4. Chunker.
5. Embedder.
6. Embedding queue.
7. Scheduler and embedding task.
8. Documents page.

### Phase D: RAG and Chat
1. Model abstraction and OpenAI client.
2. Retriever and context assembler.
3. Reranker and citation tracker.
4. Chat repository/service/router.
5. WebSocket streaming.
6. Tutor orchestrator.
7. Chat page.

### Phase E: Memory
1. Memory repository/service.
2. Extraction prompt and task.
3. Deduplication and confidence.
4. Memory retrieval in tutor context.
5. Memory page.

### Phase F: Roadmap MVP
1. Syllabus parser.
2. Roadmap repository/service.
3. Strict mode generation.
4. Node status and progress.
5. Roadmap page list view.

### Phase G: Graph, Quiz, Analytics, Polish
1. Graph store/query/enrichment.
2. Quiz service and page.
3. Analytics service and dashboard.
4. Adaptive/hybrid roadmaps.
5. ReactFlow and D3 visualizations.
6. Exports/imports.
7. Full tests.
8. Packaging and release checks.

## 7. Implementation Priorities

### MVP Priority
Build the core loop first:
```text
Profile -> Upload text PDF -> Chunk/embed -> RAG chat with citations -> Memory extraction -> Strict roadmap
```

MVP must include:
* Profile creation/switching.
* Settings and encrypted API key.
* Text PDF, DOCX, TXT ingestion.
* ChromaDB document embeddings.
* WebSocket chat streaming.
* RAG citations.
* Basic memory extraction/retrieval.
* Strict roadmap generation from syllabus.
* Start/setup scripts.
* Usable dark UI.
* Tests for critical paths.

### Defer Until Core Loop Works
* OCR for scanned PDFs/images.
* Adaptive/hybrid roadmaps.
* Full D3 graph visualization.
* Formal timed assessments.
* Spaced repetition.
* Anthropic/Ollama full support.
* Plugin loader.
* Browser extension.
* Advanced analytics.

### Quality Priorities
1. Correct data isolation by profile.
2. Reliable local startup.
3. Clear error handling.
4. No API key leakage.
5. Deterministic database migrations.
6. Recoverable background tasks.
7. Typed API/frontend contracts.
8. Tests around core workflows.

## 8. What Agents Must Never Change
Agents must not change these without explicit user approval:
* Local-first architecture.
* Backend binding to `127.0.0.1`.
* No-auth local assumption.
* Response envelope format.
* UUID string ID convention.
* UTC ISO timestamp convention.
* Profile data isolation.
* Encrypted API-key storage.
* SQLite as structured source of truth.
* ChromaDB as local vector store.
* `00_IMPLEMENTATION_PLAN.md` source-of-truth status.
* Existing user data under `~/.learningos/`.

Agents must never:
* Store raw API keys in code, logs, SQLite, TOML, frontend state, or exports.
* Commit local databases, ChromaDB files, logs, uploaded files, extracted text, or secrets.
* Bind the backend to `0.0.0.0`.
* Add telemetry or cloud sync.
* Send unrelated profiles, full databases, or unnecessary full documents to model providers.
* Bypass service boundaries by putting business logic in routers.
* Let frontend directly read local files or local databases.
* Delete or rewrite user data without an explicit destructive action.
* Break existing documented API contracts without updating docs and frontend types.
* Add background tasks without idempotency and failure behavior.
* Treat ChromaDB as the only copy of source text or metadata.

## 9. Dependencies Between Systems

### System Dependency Graph
```text
Config
  -> Database
  -> Profiles
  -> Settings/Keystore
  -> Documents
  -> Embedding Queue
  -> Vector Database
  -> RAG
  -> Chat
  -> Tutor Orchestrator
  -> Memory
  -> Roadmap
  -> Graph
  -> Quiz
  -> Analytics
  -> UI Pages
```

### Critical Dependencies
| System | Depends On | Used By |
| :--- | :--- | :--- |
| Config | filesystem | all backend systems |
| Keystore | config, filesystem | model clients, settings |
| Profiles | database | nearly every domain |
| Documents | profiles, filesystem, database | RAG, roadmap, graph |
| Embeddings | documents, model provider, ChromaDB | RAG, memory, notes |
| RAG | ChromaDB, documents, memory, notes | tutor orchestrator |
| Chat | profiles, model clients, RAG | memory, graph, analytics |
| Memory | chat, embeddings, model clients | tutor context, dashboard |
| Roadmap | documents, syllabus parser, model clients | tutor context, quiz, analytics |
| Graph | documents, chat, roadmap, quiz | graph UI, tutor context |
| Quiz | roadmap, model clients | memory, graph, analytics |
| Analytics | all event-producing systems | dashboard, reports |
| Frontend | API contracts | user workflows |

### Build Dependency Rules
* Do not build RAG before document chunking and embeddings exist.
* Do not build tutor context before chat persistence exists.
* Do not build memory retrieval before embeddings and memory records exist.
* Do not build adaptive roadmaps before Strict mode works.
* Do not build graph visualization before graph API returns stable nodes/edges.
* Do not build analytics dashboards before analytics events are written.
* Do not build export/import before profile ownership is stable.

## 10. Definition of Done
A task is done only when all applicable items below are complete.

### Code
* Implementation follows documented architecture.
* Feature is scoped to the requested domain.
* Service boundaries are respected.
* Typed schemas/contracts are added or updated.
* Errors return structured envelopes.
* Background work is idempotent where applicable.
* Profile isolation is enforced.

### Data
* Database schema changes have Alembic migrations.
* ORM models match `03_DATABASE_DESIGN.md`.
* ChromaDB metadata includes profile/model/version where applicable.
* File writes use safe paths and cleanup behavior.
* Destructive actions are explicit and tested.

### Frontend
* UI uses typed API wrappers.
* Loading, empty, error, and success states exist.
* Accessibility basics are met.
* Text does not overflow controls.
* Production build works, not only dev server.

### Tests
* Unit tests cover core logic.
* Integration/API tests cover persistence and response shape.
* WebSocket behavior is tested for streaming features.
* Frontend hooks/components are tested where changed.
* E2E or manual verification covers user-facing flows.

### Security and Privacy
* No raw secrets in logs, code, exports, or frontend state.
* Backend remains localhost-only.
* Upload paths are sanitized.
* Cross-profile access is prevented.
* Model calls include only needed context.

### Documentation
* Relevant docs are updated.
* Any intentional deviation from the master plan is documented.
* New dependencies or setup requirements are documented.

### Verification
Before marking complete, run the relevant commands:
```bash
# Backend
pytest backend/app/tests

# Frontend
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

If a command cannot be run, record why and what remains unverified.

