# 02. Repository Structure

## 1. Repository Overview
Atlas uses a monorepo structure containing two primary domains: a Python/FastAPI `backend` and a React/TypeScript/Vite `frontend`. This structure ensures tight coupling of the API contracts and simplifies deployment.

## 2. Root Level Files
*   `README.md`: High-level project description, features, and quickstart instructions.
*   `start.bat` / `start.sh`: The main entrypoint scripts for running the application in production mode.
*   `start-dev.bat`: Launches both the backend with reload and the frontend dev server.
*   `setup.bat` / `setup.sh`: Environment initialization (installs dependencies, sets up DB).
*   `.env.example`: Template for optional environment variables (though most config is in `settings.toml`).
*   `.gitignore`: Prevents checking in `.venv`, `node_modules`, SQLite databases, ChromaDB files, or log files.

## 3. Complete Directory Tree
```text
atlas/
├── README.md
├── start.bat
├── start.sh
├── start-dev.bat
├── setup.bat
├── setup.sh
├── .env.example
├── .gitignore
├── backend/
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── dependencies.py
│       ├── lifespan.py
│       ├── routers/ (profiles, documents, chat, roadmap, graph, memory, quiz, analytics, notes, settings, health)
│       ├── services/ (profile, ingestion, chat, roadmap, graph, memory, quiz, analytics, notes, tutor_orchestrator)
│       ├── pipelines/ (ocr, document_extractor, chunker, embedder, syllabus_parser)
│       ├── rag/ (retriever, reranker, context_assembler, citation_tracker)
│       ├── models/ (abstraction, openai_client, anthropic_client, ollama_client)
│       ├── graph/ (graph_store, graph_enricher, graph_query)
│       ├── db/ (database.py, models.py, repositories/)
│       ├── schemas/
│       ├── tasks/
│       ├── security/
│       ├── utils/
│       └── tests/
└── frontend/
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

## 4. Backend Directory Deep-Dive (`backend/app/`)
*   `main.py`: Entry point. Creates the FastAPI app, sets up middleware, and includes routers. Imports: `routers/*`, `lifespan.py`, `config.py`. Imported by: `uvicorn`.
*   `config.py`: Defines the `Settings` Pydantic model and loads `settings.toml`. Imported globally.
*   `dependencies.py`: Defines FastAPI dependency injection functions (e.g., `get_db`, `get_profile`). Imports: `db/database.py`, `services/*`.
*   `lifespan.py`: Manages startup and shutdown events (DB initialization, scheduling background tasks).
*   `routers/`: Contains all FastAPI endpoint definitions. They validate requests and delegate logic to `services/`.
*   `services/`: Core business logic. Classes like `ProfileService`, `ChatService`, `TutorOrchestrator`. They coordinate repositories and external pipelines.
*   `pipelines/`: Specialized modules for data processing (OCR, PDF text extraction, chunking, and text embeddings).
*   `rag/`: Retrieval-Augmented Generation modules. Contains retrieval algorithms, ranking models, and context assemblers.
*   `models/`: AI model integration layer. Contains an abstraction interface and specific clients for OpenAI, Anthropic, and Ollama.
*   `graph/`: Knowledge Graph management. Includes the store interface, graph query logic, and the enrichment engine.
*   `db/`: Database layer. `database.py` manages SQLAlchemy sessions. `models.py` defines ORM schemas. `repositories/` contains classes for executing specific queries.
*   `schemas/`: Pydantic v2 models defining the shape of API requests and responses.
*   `tasks/`: Background jobs intended to be run by APScheduler (e.g., async embedding, memory extraction).
*   `security/`: Key management and encryption utilities for securing API keys locally.
*   `utils/`: Generic helpers (logging setup, time utilities).

## 5. Frontend Directory Deep-Dive (`frontend/src/`)
*   `main.tsx`: React DOM entry point. Sets up the QueryClientProvider.
*   `App.tsx`: Root component defining global layout providers and Toast containers.
*   `router.tsx`: React Router configuration mapping URLs to Pages.
*   `api/`: Axios instances and wrapper functions for calling backend endpoints.
*   `stores/`: Zustand stores for global state (e.g., active profile, UI themes).
*   `hooks/`: Custom React hooks (e.g., `useChat`, `useStreaming`) bridging stores, queries, and UI.
*   `components/`: Reusable UI elements (buttons, modals, layout shells).
*   `pages/`: Top-level view components mapped directly to routes.
*   `types/`: TypeScript interfaces representing backend schemas.
*   `styles/`: Global CSS or Tailwind configuration files.

## 6. File Naming Conventions
*   **Python (Backend)**: `snake_case.py` for files and variables, `PascalCase` for Classes.
*   **React Components**: `PascalCase.tsx` (e.g., `ChatPanel.tsx`).
*   **TypeScript Utilities/Hooks**: `camelCase.ts` (e.g., `useChat.ts`, `apiClient.ts`).

## 7. Data Directory Structure (`~/.atlas/`)
```text
~/.atlas/
├── data/
│   ├── sqlite/
│   │   ├── atlas.db
│   │   └── atlas.db-wal
│   ├── chroma/ (Vector database files)
│   └── graph/
│       └── knowledge_graph.json
├── profiles/
│   └── {profile_id}/
│       └── documents/
│           ├── raw/ (Original uploads)
│           └── extracted/ (Parsed text)
├── config/
│   ├── settings.toml
│   └── secrets.enc
└── logs/
    ├── backend.log
    ├── errors.log
    └── ingestion.log
```

## 8. Configuration Files
*   `settings.toml`: User-editable configuration detailing database paths, default LLM provider, port, and tuning parameters.
*   `secrets.enc`: An encrypted local file storing API keys (OpenAI, Anthropic).
*   `.env.example`: Environment variables mainly used to override `settings.toml` in Docker/CI environments.

## 9. Test Directory Structure
`backend/app/tests/`
*   `unit/`: Tests individual functions or classes in isolation (mocked DB/AI).
*   `integration/`: Tests the interaction between services and the local database.
*   `e2e/`: End-to-end tests calling the actual FastAPI endpoints.
*   `fixtures/`: Dummy PDFs, text samples, and JSON objects for tests.

## 10. Import Rules
*   **Routers** may import **Services** and **Schemas**.
*   **Services** may import **Repositories**, **Pipelines**, **RAG**, and **Models**.
*   **Repositories** may import **DB Models** and **Schemas**.
*   **Data Models** (`db/models.py`) must NOT import anything from `routers/` or `services/`.
*   **Frontend Components** should primarily interact with data via **Hooks**, not direct `api/` calls.

## 11. Adding New Features (Step-by-Step)
To add a new feature (e.g., "Flashcards"):
1.  **Backend Schema**: Create `app/schemas/flashcard.py`.
2.  **Database Model**: Add `Flashcard` to `app/db/models.py`. Run Alembic migration.
3.  **Repository**: Create `app/db/repositories/flashcard_repo.py`.
4.  **Service**: Create `app/services/flashcard_service.py` to contain the business logic.
5.  **Router**: Create `app/routers/flashcard.py` and register it in `main.py`.
6.  **Frontend Types**: Add `Flashcard` interface in `frontend/src/types/index.ts`.
7.  **Frontend API**: Add endpoints in `frontend/src/api/flashcards.ts`.
8.  **Frontend Hook/Store**: Add `useFlashcards.ts` if needed.
9.  **Frontend Component/Page**: Create the UI in `frontend/src/pages/FlashcardsPage.tsx` and register the route.

## 12. Master Plan File Coverage Addendum
The master implementation plan calls out several files that are not obvious from the abbreviated tree above. Builders should create these exact files unless the final implementation consolidates them with a clearly documented reason.

### Backend Required Files
```text
backend/app/
├── exceptions.py
├── lifespan.py
├── routers/
│   ├── profiles.py
│   ├── documents.py
│   ├── chat.py
│   ├── ws_chat.py
│   ├── roadmap.py
│   ├── graph.py
│   ├── memory.py
│   ├── quiz.py
│   ├── analytics.py
│   ├── notes.py
│   ├── settings.py
│   └── health.py
├── services/
│   ├── profile_service.py
│   ├── ingestion_service.py
│   ├── chat_service.py
│   ├── roadmap_service.py
│   ├── graph_service.py
│   ├── memory_service.py
│   ├── quiz_service.py
│   ├── analytics_service.py
│   ├── notes_service.py
│   ├── settings_service.py
│   └── tutor_orchestrator.py
├── pipelines/
│   ├── document_extractor.py
│   ├── ocr_pipeline.py
│   ├── chunker.py
│   ├── embedder.py
│   └── syllabus_parser.py
├── rag/
│   ├── retriever.py
│   ├── reranker.py
│   ├── context_assembler.py
│   └── citation_tracker.py
├── models/
│   ├── abstraction.py
│   ├── provider_factory.py
│   ├── openai_client.py
│   ├── anthropic_client.py
│   └── ollama_client.py
├── graph/
│   ├── graph_store.py
│   ├── graph_query.py
│   └── graph_enricher.py
├── db/
│   ├── database.py
│   ├── models.py
│   └── repositories/
│       ├── profile_repo.py
│       ├── document_repo.py
│       ├── embedding_repo.py
│       ├── chat_repo.py
│       ├── roadmap_repo.py
│       ├── graph_repo.py
│       ├── memory_repo.py
│       ├── quiz_repo.py
│       ├── analytics_repo.py
│       └── notes_repo.py
├── tasks/
│   ├── scheduler.py
│   ├── embedding_task.py
│   ├── memory_extraction_task.py
│   ├── graph_enrichment_task.py
│   └── backup_task.py
├── security/
│   └── keystore.py
└── utils/
    ├── id_utils.py
    ├── date_utils.py
    ├── file_utils.py
    ├── text_utils.py
    └── logging.py
```

### Frontend Required Files
```text
frontend/src/
├── api/
│   ├── client.ts
│   ├── profiles.ts
│   ├── documents.ts
│   ├── chat.ts
│   ├── roadmap.ts
│   ├── graph.ts
│   ├── memory.ts
│   ├── quiz.ts
│   ├── analytics.ts
│   ├── notes.ts
│   └── settings.ts
├── stores/
│   ├── profileStore.ts
│   ├── chatStore.ts
│   ├── uiStore.ts
│   └── settingsStore.ts
├── hooks/
│   ├── useStreaming.ts
│   ├── useChat.ts
│   ├── useRoadmap.ts
│   ├── useGraph.ts
│   └── useDocuments.ts
├── components/
│   ├── layout/
│   ├── chat/
│   ├── roadmap/
│   ├── graph/
│   ├── documents/
│   └── common/
├── pages/
│   ├── SetupPage.tsx
│   ├── DashboardPage.tsx
│   ├── ChatPage.tsx
│   ├── RoadmapPage.tsx
│   ├── DocumentsPage.tsx
│   ├── GraphPage.tsx
│   ├── QuizPage.tsx
│   ├── AnalyticsPage.tsx
│   ├── MemoryPage.tsx
│   └── SettingsPage.tsx
└── styles/
    ├── tokens.css
    └── globals.css
```

### Repository Build Rules
*   Every backend domain should have this chain where applicable: schema -> repository -> service -> router -> tests.
*   Every frontend domain should have this chain where applicable: type -> API wrapper -> hook/store -> page/component -> UI test.
*   Do not add a new route without adding the matching TypeScript API wrapper and response type.
*   Do not add a new table without adding the SQLAlchemy model, Alembic migration, repository method coverage, and backup/export consideration.
*   Do not add a background task without documenting trigger conditions, retry behavior, idempotency key, and failure logging.

## 13. Setup Artifacts Required at Repository Root
The implementation plan expects these root files before MVP QA:
*   `README.md`: project overview, setup, launch, and troubleshooting.
*   `.env.example`: optional env overrides only; canonical runtime config is `settings.toml`.
*   `.gitignore`: ignore `.venv`, `node_modules`, local DBs, Chroma files, logs, secrets, build artifacts.
*   `setup.bat` and `setup.sh`: first-time setup.
*   `start.bat` and `start.sh`: production launch.
*   `start-dev.bat`: developer launch.
*   `update.bat`: pull/update dependencies/migrate/build for repo-tracking users.
