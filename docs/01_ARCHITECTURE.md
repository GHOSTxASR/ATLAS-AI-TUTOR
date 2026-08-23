# 01. Architecture

## 1. Architectural Overview
Atlas utilizes a **local microkernel architecture** with a **service-oriented backend**. It operates on a **two-process model**:
1.  **FastAPI Backend Process**: Handles all core logic, orchestration, database interactions, and communication with AI providers.
2.  **Vite/React Frontend Process**: Handles the user interface, state management, and real-time updates.

This architecture ensures strict separation of concerns while keeping deployment and local execution simple.

## 2. Architectural Principles
*   **Local-First**: All data, including profiles, documents, chat histories, memory, and knowledge graphs, are stored exclusively on the user's machine. Nothing is sent to a central server for storage.
*   **No Cloud Database**: There is no SaaS backend or centralized database. SQLite, ChromaDB, and local JSON files serve as the entire data persistence layer.
*   **No Auth Server**: Authentication is completely omitted. The system assumes that access to the local machine implies authorization.
*   **Persistent Intelligence**: The AI tutor maintains long-term memory across sessions, ensuring continuity in the learning experience without resetting.

## 3. System Context Diagram
```text
┌─────────────────────────────────────────────────────────┐
│                    USER'S MACHINE                       │
│                                                         │
│  ┌───────────┐    HTTP/WS     ┌─────────────────────┐   │
│  │  Browser  │ ◄────────────► │  Atlas Backend │   │
│  │  (React)  │                │  (FastAPI, Port 8000)   │
│  └───────────┘                └─────────┬───────────┘   │
│                                         │               │
│              ┌──────────────────────────┼──────────┐    │
│              │          Data Layer                 │    │
│              │                                     │    │
│         ┌────▼────┐  ┌──────────┐  ┌───▼──────┐    │    │
│         │ SQLite  │  │ ChromaDB │  │ File Sys │    │    │
│         └─────────┘  └──────────┘  └──────────┘    │    │
│              └─────────────────────────────────────┘    │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │            AI Inference (OUTBOUND ONLY)          │   │
│  │  OpenAI API / Anthropic API / Ollama (local)     │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## 4. Component Architecture
*   **Frontend (React/Vite)**: The client application that the user interacts with. It manages UI state, renders data, and handles user inputs.
*   **FastAPI Backend**: The core server processing requests, managing WebSocket connections, and coordinating services.
*   **Profile Service**: Manages user profiles, context switching, and profile-specific settings.
*   **Ingestion Service**: Handles document uploads, triggers text extraction, OCR, chunking, and queues embeddings.
*   **RAG Service**: Manages the Retrieval-Augmented Generation pipeline. It retrieves relevant chunks from ChromaDB and memory, reranks them, and assembles the context.
*   **Memory Service**: Extracts facts, strengths, and weaknesses from chats, deduplicates them, and stores them in SQLite and ChromaDB.
*   **Graph Service**: Manages the knowledge graph. It extracts concepts, updates node mastery scores, and handles graph queries.
*   **Roadmap Service**: Generates learning roadmaps (Strict, Adaptive, Hybrid) and manages node states (not_started, completed, etc.).
*   **Chat Service**: Manages chat sessions, persists messages to SQLite, and handles WebSocket streaming.
*   **Tutor Orchestrator**: The central "brain" that assembles the context (RAG, memory, roadmap, history), selects the prompt based on the learning mode, and calls the Model Abstraction Layer.
*   **Model Abstraction Layer**: A unified interface to communicate with different AI providers (OpenAI, Anthropic, Ollama).
*   **Analytics Service**: Computes progress metrics, learning velocity, and mastery charts.
*   **Assessment Service**: Generates quizzes, evaluates answers, and updates mastery scores.
*   **Vector Store (ChromaDB)**: Embedded vector database storing document chunks, memory embeddings, and note embeddings.
*   **Relational Store (SQLite)**: Stores structured data (profiles, chats, roadmap nodes, analytics events).
*   **Graph Store (NetworkX/JSON)**: Stores the knowledge graph (nodes and edges). NetworkX is used in-memory, serialized to JSON.
*   **File System**: Stores raw uploaded documents and extracted text files.

## 5. Communication Patterns
*   **REST (CRUD)**: Standard HTTP methods for standard operations (e.g., creating a profile, uploading a document, fetching analytics).
*   **WebSocket (streaming)**: Used exclusively for the AI chat interface to stream responses token-by-token and push real-time events (citations, errors).
*   **Internal Python Calls**: Services communicate synchronously within the FastAPI process via direct function calls.
*   **Background Task Queue**: APScheduler is used to offload long-running tasks like embedding chunks, extracting memories, and enriching the graph asynchronously.

## 6. Process Model
The application runs exactly two processes:
1.  **Backend Process**: `uvicorn app.main:app --port 8000`. This process runs the FastAPI server and the APScheduler background tasks.
2.  **Frontend Process**: In development, `vite` dev server on port 5173. In production, FastAPI can mount the static `dist` folder to serve the frontend on port 8000, reducing it to a single visible process for the user.

## 7. High-Level Design (Module Dependency Map)
```text
Frontend (React/Vite)
  └── API Client (Axios/TanStack Query)
        └── FastAPI Router Layer
              ├── Profile Router → Profile Service
              ├── Document Router → Ingestion Service
              │     └── [OCR Pipeline, Chunker, Embedder → ChromaDB]
              ├── Chat Router → Chat Service, Tutor Orchestrator
              │     └── Tutor Orchestrator
              │           ├── RAG Service → ChromaDB
              │           ├── Memory Service → SQLite, ChromaDB
              │           ├── Graph Service → Graph Store
              │           ├── Roadmap Service → SQLite
              │           └── Model Abstraction Layer → AI Provider
              ├── Analytics Router → Analytics Service → SQLite
              ├── Quiz Router → Assessment Service → Model Abstraction, SQLite
              └── Settings Router → Config System
```

## 8. Data Ownership Map
| Data Category | Primary Store | Secondary/Cache |
| :--- | :--- | :--- |
| Profiles | SQLite | In-memory dict |
| Chat sessions/messages | SQLite | - |
| Raw Documents | File System | - |
| Document chunks/embeddings | ChromaDB | SQLite metadata |
| Memory records | SQLite | ChromaDB (embeddings) |
| Knowledge graph | JSON file | In-memory NetworkX |
| Roadmap nodes/edges | SQLite | - |
| Analytics events | SQLite | Aggregated cache |
| Settings/config | TOML file | In-memory |
| API keys | Encrypted JSON | Decrypted in-memory |

## 9. Low-Level Design (Request Lifecycles)

### Chat Message Lifecycle
1. User sends message via WebSocket or POST.
2. Chat Service saves message as `pending` in SQLite.
3. Tutor Orchestrator is invoked.
4. Orchestrator fetches Profile Context, Roadmap Context, and Memory Context (via Memory Service).
5. Orchestrator queries RAG Service for relevant chunks.
6. Context Assembler builds the final prompt (System + Context + History + Query).
7. Model Abstraction Layer sends the prompt to the AI Provider.
8. AI Provider streams tokens back.
9. Tokens are streamed to Frontend via WebSocket.
10. Final message saved to SQLite.
11. Post-turn tasks triggered: Memory Extraction and Graph Enrichment.

### Document Upload Lifecycle
1. User uploads file via POST `/documents`.
2. Ingestion Service saves the raw file to the File System.
3. Extractor extracts text (invoking OCR Pipeline if necessary).
4. Chunker splits text into 512-token chunks.
5. Chunks are added to the SQLite `chunk_embedding_queue`.
6. APScheduler background task picks up chunks, calls Embedder.
7. Embedder stores vectors in ChromaDB.
8. Document status updated to `indexed` in SQLite.
9. WebSocket event notifies frontend.

### Roadmap Generation Lifecycle
1. User requests generation via POST `/roadmaps`.
2. Roadmap Service invokes Syllabus Parser (uses AI to extract structure).
3. If Adaptive Mode, AI reorders topics and determines prerequisites.
4. Nodes and Edges are created in memory.
5. Persisted to SQLite `roadmap_nodes` and `roadmap_edges`.
6. Frontend re-fetches and renders the roadmap.

### Knowledge Graph Update Cycle
1. Triggered post-chat or post-document index.
2. Graph Enricher prompts AI to extract concepts/relationships from the new text.
3. AI returns JSON of nodes and edges.
4. Graph Service loads the NetworkX graph.
5. Nodes and edges are merged/added. Mention counts and mastery scores updated.
6. Graph serialized and saved back to JSON file.

## 10. Startup Sequence
1. Load configuration from `settings.toml`.
2. Initialize SQLite database and run Alembic migrations automatically.
3. Initialize ChromaDB persistent client.
4. Load Knowledge Graph from JSON into NetworkX.
5. Start APScheduler and register background tasks (embedding, backups).
6. Register FastAPI shutdown handlers.
7. Start Uvicorn ASGI server and log "Ready".

## 11. Middleware Stack
1.  **CORS Middleware**: Allows requests from `localhost:5173` (dev frontend).
2.  **Request ID Middleware**: Injects a UUID into each request for log correlation.
3.  **Timing Middleware**: Measures request duration and logs it.
4.  **Error Handler Middleware**: Catches unhandled exceptions, returns a structured JSON error response.
5.  **Static Files Mount**: Mounts the frontend `dist` directory at `/` (production mode only).

## 12. Technology Stack
**Backend Libraries**
| Library | Purpose |
| :--- | :--- |
| Python 3.11+ | Core Language |
| FastAPI | Web Framework |
| SQLAlchemy, Alembic | ORM and Migrations |
| ChromaDB | Vector Database |
| NetworkX | Knowledge Graph Processing |
| PyMuPDF, pytesseract, Pillow | Document Extraction & OCR |
| sentence-transformers | Local Embeddings |
| openai, anthropic, httpx | AI Provider SDKs / API Clients |
| APScheduler | Background Jobs |
| cryptography | API Key Encryption |
| Pydantic | Schema Validation |
| loguru | Structured Logging |
| pytest | Testing Framework |

**Frontend Libraries**
| Library | Purpose |
| :--- | :--- |
| React 18, TypeScript | UI Framework and Typing |
| Vite | Build Tool |
| React Router | Client-side Routing |
| Zustand | Global State Management |
| TanStack Query | Data Fetching & Server State |
| Axios | HTTP Client |
| D3.js | Knowledge Graph Visualization |
| React Flow | Roadmap Visualization |
| Recharts | Analytics Charts |
| Monaco Editor | Markdown Editing |
| React Markdown, KaTeX | Render Markdown and Math |
| Lucide React | Icons |

## 13. Service Boundaries
| Caller | Can Call | Must NOT Call |
| :--- | :--- | :--- |
| Tutor Orchestrator | RAG, Memory, Graph, Roadmap, Chat | Repositories (Data Layer) |
| Chat Service | Tutor Orchestrator, ChatRepo | Vector Store directly |
| Ingestion Service | Graph Service, DocumentRepo, Extractor | Chat Repo |
| Graph Service | GraphStore | ChromaDB directly |
| Memory Service | MemoryRepo, ChromaDB (memory coll) | DocumentRepo |

## 14. Scalability Considerations
*   **Documents**: UI pagination and lazy loading handle 500+ documents.
*   **Chunks in ChromaDB**: ~200,000 chunks. Handled via HNSW tuning and profile-scoped collections.
*   **Chat Messages**: ~100,000 messages. Scaled using SQLite FTS5 indexes and pagination.
*   **Graph Nodes**: ~5,000 nodes. Rendered with level-of-detail and clustering. Future migration to Kuzu DB if limits are reached.
*   **Analytics Events**: ~1,000,000 events. Scaled using aggregation queries and caching.

## 15. Non-Functional Requirements
*   **Performance**: Chat latency < 2s (excluding model). Document embedding (100p PDF) < 5m. Vector search < 500ms.
*   **Reliability**: Atomic database writes. Graceful degradation if AI API fails. Resume capability for background tasks.
*   **Usability**: Single-click launch (`start.bat`). Setup under 3 minutes. No technical expertise required for operation.
*   **Privacy/Security**: 100% local data. Encrypted API keys. HTTP server bound exclusively to `127.0.0.1`.
*   **Maintainability**: Modular architecture. Centralized configuration. Version-controlled schema migrations.
*   **Portability**: Primary target Windows, but fully compatible with macOS and Linux. Standardized path handling.

## 16. Build-Time Architecture Contracts
These contracts fill in details from `00_IMPLEMENTATION_PLAN.md` that coding agents must preserve while building the repository.

### Source of Truth Rules
*   `00_IMPLEMENTATION_PLAN.md` remains the product and system source of truth. This file is the architecture working reference.
*   If this file conflicts with the master plan, prefer the master plan, then update this file in the same change.
*   Any feature that changes data ownership, service boundaries, ports, startup order, or persistence must update this file and the affected specialist document.

### Hard Process Boundaries
*   Development mode runs two visible processes: FastAPI on `127.0.0.1:8000` and Vite on `127.0.0.1:5173`.
*   Production mode serves the compiled frontend from FastAPI and exposes only `127.0.0.1:8000`.
*   The frontend must never read local files directly. All file, database, model, and graph access goes through backend APIs.
*   The backend must not bind to `0.0.0.0` unless an explicit future LAN-sharing feature is designed and documented.

### Service Boundary Rules
*   Routers validate transport concerns only: request shape, response envelope, status codes, and dependency injection.
*   Services own business behavior and cross-domain orchestration.
*   Repositories own SQLAlchemy queries only and must not call services, model clients, ChromaDB, or filesystem helpers directly.
*   Pipeline modules are pure processing units where possible. They should accept input paths or text and return structured results, leaving persistence to services/repositories.
*   `TutorOrchestrator` is the only component allowed to compose chat history, roadmap context, memory, RAG context, and model calls in one request.

### Event Ownership
*   Document ingestion completion may emit three follow-up actions: queue embeddings, enrich the graph, and notify the frontend.
*   Chat completion may emit memory extraction, graph enrichment, analytics logging, and citation persistence.
*   Quiz completion may emit mastery updates, memory updates, roadmap progress recomputation, graph mastery updates, and analytics logging.
*   Background actions must be idempotent. Retrying a failed task must not duplicate ChromaDB vectors, graph edges, memory records, or analytics events.

### Startup Acceptance Checklist
Before the backend accepts traffic, startup must prove:
1. Configuration loaded and data directories exist.
2. SQLite connection opened with WAL and foreign keys enabled.
3. Alembic migrations reached head.
4. ChromaDB persistent client opened and profile/global collection creation helpers are available.
5. Graph JSON loaded or initialized.
6. Scheduler registered embedding, memory, graph, and backup tasks.
7. Static frontend mount is enabled only when a production `dist` directory exists.

### Failure Behavior
*   Model-provider failure returns a structured `MODEL_UNAVAILABLE` error over HTTP or WebSocket without crashing the app.
*   ChromaDB failure marks only the affected document or retrieval request as failed; SQLite remains the source of truth for status.
*   Graph enrichment failure logs an error and leaves the existing graph unchanged.
*   Memory extraction failure never blocks chat completion.
*   Setup/start script failure must print the failing dependency and the next manual action.
