# 14. Development Roadmap

## 1. Project Overview
**Atlas** is a local-first, AI-powered personal learning operating system. It aims to replace disjointed notes, folders of PDFs, and amnesic chatbots with a single, unified local environment that remembers the user's progress, maps their knowledge, and acts as a persistent Socratic tutor.

## 2. MVP Definition
The Minimum Viable Product (MVP) focuses on proving the core loop: Ingest Document -> RAG Chat -> Memory Extraction.
**Success Criteria (MVP):**
1. User can create a profile and input an API key.
2. User can upload a text-based PDF and the system chunks/embeds it into ChromaDB.
3. User can chat with the AI, which correctly streams answers citing the PDF.
4. The system successfully extracts a "strength" or "weakness" from the chat and uses it in the next session.
5. User can generate a Strict Mode roadmap from a syllabus and track completion.

## 3. MVP Feature Set
*   ✅ Profile creation and switching.
*   ✅ PDF upload (Text-based only), DOCX, TXT.
*   ✅ Syllabus parsing (Strict Mode only).
*   ✅ Roadmap list view & manual status tracking.
*   ✅ AI Tutor Chat (Streaming, standard Socratic mode).
*   ✅ RAG (Querying the document collection only).
*   ✅ Memory System (Extraction via LLM + basic retrieval).
*   ✅ OpenAI API integration.
*   ✅ `start.bat` and `setup.bat` scripts.
*   ✅ Dark mode React UI.
*   ✅ Image/PDF OCR (Tesseract, with graceful degradation when missing) — Milestone 09.
*   ❌ *Deferred*: Adaptive/Hybrid roadmaps.
*   ❌ *Deferred*: Knowledge Graph visualization (D3).
*   ❌ *Deferred*: Formal Assessment/Quiz mode.
*   ❌ *Deferred*: Anthropic/Ollama integrations.

## 4. Phase 2 Scope (6-8 Weeks post-MVP)
*   **Knowledge Graph**: Implement `graph_enricher`, NetworkX in-memory graph, and the D3.js visualization.
*   **OCR Pipeline**: Implemented in Milestone 09 (Tesseract for scanned PDFs and image uploads); remaining work is system-level Tesseract bundling for packaging.
*   **Advanced Roadmaps**: Implement Adaptive and Hybrid generation modes, and the ReactFlow DAG visualization.
*   **Quiz Engine**: Implement the Assessment Service for formal testing and automatic mastery scoring.
*   **Local Models**: Integrate Ollama and HuggingFace SentenceTransformers for a 100% offline mode.

## 5. Phase 3 Scope (3-6 Months post-MVP)
*   **Analytics**: Heatmaps, learning velocity charts, mastery distributions.
*   **Spaced Repetition**: Flashcard generation based on weak graph nodes.
*   **Browser Extension**: Send web articles directly to the Ingestion Service.
*   **Plugin System**: Allow third-party Python scripts to add new extractors or tutor modes.
*   **Data Portability**: Full JSON/CSV export and import.

## 6. Recommended Build Order (MVP)
*   **Phase A**: Foundation (FastAPI setup, SQLite config, Vite setup, Layout).
*   **Phase B**: Profile System (CRUD, state management).
*   **Phase C**: Document System (Upload, PyMuPDF extraction, tiktoken chunker).
*   **Phase D**: RAG + Basic Chat (OpenAI client, ChromaDB embedder, WebSocket router).
*   **Phase E**: Memory System (Extraction prompt, SQLite storage, context injection).
*   **Phase F**: Roadmap Engine (Syllabus parser, Strict mode DAG generation).

## 7. Exact Implementation Sequence (Tasks 001-015)

*   **TASK-001**: Initialize monorepo, `pyproject.toml`, `package.json`.
*   **TASK-002**: Setup FastAPI `main.py`, CORS, and basic logging.
*   **TASK-003**: Create SQLite `database.py` and Alembic migrations folder.
*   **TASK-004**: Define all MVP SQLAlchemy models in `models.py`.
*   **TASK-005**: Initialize React + Vite + Tailwind/CSS foundation.
*   **TASK-006**: Implement `ProfileService` and `/profiles` router.
*   **TASK-007**: Build Frontend `SetupPage` and `ProfileStore`.
*   **TASK-008**: Implement `IngestionService` file upload endpoint.
*   **TASK-009**: Implement `document_extractor.py` (PyMuPDF).
*   **TASK-010**: Implement `chunker.py` and `embedder.py` (ChromaDB init).
*   **TASK-011**: Setup `APScheduler` and the `embedding_task`.
*   **TASK-012**: Build Frontend `DocumentsPage` with upload and status polling.
*   **TASK-013**: Implement `ModelAbstractionLayer` and `OpenAIClient`.
*   **TASK-014**: Implement `RAGService` (retrieval and context assembly).
*   **TASK-015**: Implement `ws_chat.py` WebSocket streaming and Frontend `ChatPage`.

## 8. Development Timeline (Estimates)
*   **Weeks 1-2**: Phase A & B (Infrastructure & Profiles).
*   **Weeks 3-5**: Phase C (Document Ingestion & ChromaDB).
*   **Weeks 6-8**: Phase D (LLM Integration, RAG, WebSockets).
*   **Weeks 9-10**: Phase E (Memory System).
*   **Weeks 11-12**: Phase F (Roadmap Engine MVP).
*   **Weeks 13-14**: MVP QA, Bug bashes, UI Polish.
*   **Week 15**: MVP Release.

## 9. Team Structure (Reference)
*   **Backend Lead**: Core FastAPI, Database architecture, Model integrations.
*   **Data/AI Engineer**: PyMuPDF extraction, RAG tuning, Prompts, Memory logic.
*   **Frontend Lead**: React architecture, Zustand stores, WebSocket handling.
*   **UI/UX**: Design system, component styling.

## 10. Risk Register
| Risk | Probability | Impact | Mitigation |
| :--- | :--- | :--- | :--- |
| **OpenAI Rate Limits** | High | Medium | Implement robust exponential backoff in `embedder.py`. |
| **Large PDF OOM** | Medium | High | Process PDFs via generators. Limit upload size in MVP to 50MB. |
| **Context Window Overflow**| High | High | Strict token counting via `tiktoken`. Aggressive sliding window for chat history. |
| **Tesseract Installation**| High | Medium | Make OCR entirely optional. Gracefully degrade to error messages if missing. |
| **Hallucinated Memory** | Medium | Medium | Keep Memory extraction prompts strict. Provide UI for user to delete bad memories. |

## 11. Success Metrics
*   **Ingestion Speed**: > 5 pages per second chunked and embedded.
*   **Chat Latency**: Time to First Token (TTFT) < 2 seconds.
*   **RAG Recall**: The correct document chunk is present in the top-8 candidates > 90% of the time.
*   **Stability**: Zero backend crashes during concurrent upload and chatting.

## 12. Dependency Graph (ASCII)
```text
[Profiles] ──► [Documents] ──► [RAG Engine]
                   │                │
                   ▼                ▼
             [Roadmaps]       [Chat Interface]
                   │                │
                   ▼                ▼
             [Assessment]     [Memory System]
                   │                │
                   ▼                ▼
            [Knowledge Graph] ◄─────┘
```

## 13. Testing Milestones
*   **Unit Tests**: Must be written simultaneously with `chunker.py`, `extractor.py`, and `context_assembler.py` (pure functions).
*   **Integration Tests**: Written during Phase D to ensure ChromaDB and SQLite sync correctly.
*   **E2E Tests**: Manual UI testing for MVP. Playwright introduced in Phase 2.

## 14. Definition of Done (DoD)
A feature is "Done" when:
1. Code is merged to `main` without linting errors.
2. Pydantic schemas validate all edge cases.
3. Relevant Markdown documentation is updated.
4. Feature works correctly in the compiled Vite build (`npm run build`), not just dev mode.
5. Background tasks recover gracefully from mocked failures.

## 15. Future Extension Points
*   **Extractors**: `document_extractor.py` is designed to accept new mime-type handlers (e.g., Audio transcripts via Whisper).
*   **Providers**: `BaseModelClient` can easily wrap Google Gemini or Cohere in the future.
*   **RAG**: The Context Assembler can pull from web search APIs later.

## 16. Scalability Path
While local-first, if data grows excessively:
*   `SQLite` -> Can be swapped for `DuckDB` if analytics queries slow down.
*   `NetworkX` -> Can be swapped for `KuzuDB` (embedded graph database) if node count > 50,000.
*   `ChromaDB` -> Highly scalable locally, up to millions of vectors.

## 17. Expanded Implementation Sequence (Tasks 016-065)
The master implementation plan includes the full ordered sequence below. Tasks 001-015 are listed in Section 7; continue with these tasks without reordering unless a dependency is explicitly documented.

*   **TASK-016**: Create `backend/app/pipelines/embedder.py` for batch embedding with retry/backoff and ChromaDB writes. Create `backend/app/db/repositories/embedding_repo.py` for queue management.
*   **TASK-017**: Create `backend/app/services/ingestion_service.py` to orchestrate upload, extraction, chunking, queueing, and status updates. Create `backend/app/routers/documents.py`.
*   **TASK-018**: Create `backend/app/tasks/scheduler.py` and `backend/app/tasks/embedding_task.py`. Register the embedding task on a short polling interval.
*   **TASK-019**: Create `backend/app/models/abstraction.py`, `backend/app/models/openai_client.py`, and provider factory wiring.
*   **TASK-020**: Create `backend/app/rag/retriever.py` and `backend/app/rag/context_assembler.py`.
*   **TASK-021**: Create `backend/app/rag/reranker.py` and implement MMR diversification.
*   **TASK-022**: Create `backend/app/rag/citation_tracker.py`.
*   **TASK-023**: Create `chat_repo.py`, `chat_service.py`, `routers/chat.py`, and `routers/ws_chat.py`.
*   **TASK-024**: Create `tutor_orchestrator.py` with profile, roadmap, memory stub, RAG, history, prompt, and token-budget assembly.
*   **TASK-025**: Create `graph_store.py`, `graph_query.py`, and `graph_enricher.py`.
*   **TASK-026**: Create `graph_service.py` and `routers/graph.py`.
*   **TASK-027**: Create `memory_repo.py`, `memory_service.py`, and `memory_extraction_task.py`; integrate memory retrieval into `TutorOrchestrator`.
*   **TASK-028**: Create `syllabus_parser.py`, `roadmap_repo.py`, `roadmap_service.py`, and `routers/roadmap.py`; implement Strict mode first.
*   **TASK-029**: Create `quiz_repo.py`, `quiz_service.py`, and `routers/quiz.py`.
*   **TASK-030**: Create `analytics_repo.py`, `analytics_service.py`, and `routers/analytics.py`.
*   **TASK-031**: Create `ollama_client.py` and `anthropic_client.py`; register both in provider factory.
*   **TASK-032**: Create `routers/settings.py` and `settings_service.py` for config and encrypted API-key management.
*   **TASK-033**: Create `backup_task.py` and register daily backup/rotation.
*   **TASK-034**: Complete `lifespan.py`: config load, data dir init, DB migration, ChromaDB init, graph load, scheduler start/shutdown.
*   **TASK-035**: Initialize `frontend/` with Vite, React, TypeScript, and required dependencies.
*   **TASK-036**: Create `frontend/src/styles/tokens.css` and `frontend/src/styles/globals.css`.
*   **TASK-037**: Create `frontend/src/api/client.ts` and domain API wrappers.
*   **TASK-038**: Create all Zustand stores.
*   **TASK-039**: Create layout components: Sidebar, TopBar, Layout wrapper, NavigationMenu, ProfileSwitcher, StatusIndicator.
*   **TASK-040**: Create `HomePage.tsx` with profile grid and create-profile flow.
*   **TASK-041**: Create `SetupPage.tsx` with API key entry, model selection, and first-time profile creation.
*   **TASK-042**: Create `useStreaming.ts` and `ChatPage.tsx` with streaming.
*   **TASK-043**: Create `DashboardPage.tsx`.
*   **TASK-044**: Create `DocumentsPage.tsx` with dropzone, list, status, and polling/progress.
*   **TASK-045**: Create `RoadmapPage.tsx` list view and node status controls.
*   **TASK-046**: Create `QuizPage.tsx`.
*   **TASK-047**: Create `AnalyticsPage.tsx`.
*   **TASK-048**: Create `MemoryPage.tsx`.
*   **TASK-049**: Create `SettingsPage.tsx`.
*   **TASK-050**: Create `GraphPage.tsx` with D3 force-directed graph, filters, and node detail sidebar.
*   **TASK-051**: Add ReactFlow roadmap graph view.
*   **TASK-052**: Add FTS5 migrations for chat messages, memory records, and notes; implement search endpoints/UI.
*   **TASK-053**: Implement Hybrid and Adaptive roadmap generation.
*   **TASK-054**: Implement timed Assessment Mode in backend and frontend.
*   **TASK-055**: Implement spaced repetition scheduler.
*   **TASK-056**: Implement chat export and profile export.
*   **TASK-057**: Write backend unit and integration tests.
*   **TASK-058**: Write Playwright E2E tests for profile creation, document upload, chat, and quiz.
*   **TASK-059**: Set up GitHub Actions CI.
*   **TASK-060**: Create setup/start scripts for Windows and Unix.
*   **TASK-061**: Add setup validation for Python, Node.js, Tesseract, venv, dependencies, and migrations.
*   **TASK-062**: Run full-system integration test from `start.bat`.
*   **TASK-063**: Profile RAG latency, DB query time, and graph rendering FPS; document and optimize.
*   **TASK-064**: Complete security review for API keys, localhost binding, MIME validation, and path traversal prevention.
*   **TASK-065**: Build release package and test on clean Windows 10/11 machine.

## 18. Phase Gates
| Gate | Required Evidence |
| :--- | :--- |
| Foundation complete | Health endpoint, config load, migrations, frontend shell, setup/dev scripts. |
| Ingestion complete | Upload text PDF, extract text, chunk, queue, embed, list status, delete cleanly. |
| RAG chat complete | WebSocket stream, answer with citations, persisted messages, search-ready history. |
| Memory complete | Extract memory after chat, retrieve in later prompt, edit/delete in UI. |
| Roadmap MVP complete | Generate Strict roadmap from syllabus, update node status, compute progress. |
| MVP release candidate | Clean setup, build, restart persistence, basic tests, no secrets in logs. |

## 19. Documentation Update Rule
A task is not complete until the relevant specialist doc is updated:
*   Schema changes -> `03_DATABASE_DESIGN.md`
*   Endpoint changes -> `04_API_SPECIFICATION.md`
*   UI behavior -> `05_FRONTEND_ARCHITECTURE.md`
*   Service/background behavior -> `06_BACKEND_ARCHITECTURE.md`
*   RAG changes -> `07_RAG_ARCHITECTURE.md`
*   Memory changes -> `08_MEMORY_SYSTEM.md`
*   Graph changes -> `09_KNOWLEDGE_GRAPH.md`
*   Ingestion changes -> `10_DOCUMENT_PROCESSING.md`
*   Roadmap changes -> `11_ROADMAP_ENGINE.md`
*   Tutor/model changes -> `12_AI_TUTOR_ENGINE.md`
*   Setup/release changes -> `13_DEPLOYMENT.md`
