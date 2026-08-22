# LearningOS — Complete Implementation Specification

> **Document Version**: 1.0.0  
> **Status**: Implementation-Ready  
> **Audience**: Autonomous Coding Agents, Senior Engineers, Technical Leads  
> **Last Updated**: 2026-06-13  
> **Classification**: Single Source of Truth

---

## Table of Contents

1. [Product Vision](#1-product-vision)
2. [User Stories](#2-user-stories)
3. [Functional Requirements](#3-functional-requirements)
4. [Non-Functional Requirements](#4-non-functional-requirements)
5. [System Architecture](#5-system-architecture)
6. [High-Level Design](#6-high-level-design)
7. [Low-Level Design](#7-low-level-design)
8. [Technology Stack](#8-technology-stack)
9. [Frontend Architecture](#9-frontend-architecture)
10. [Backend Architecture](#10-backend-architecture)
11. [Database Architecture](#11-database-architecture)
12. [Local Storage Strategy](#12-local-storage-strategy)
13. [File System Layout](#13-file-system-layout)
14. [Repository Structure](#14-repository-structure)
15. [Directory Tree](#15-directory-tree)
16. [Profile System](#16-profile-system)
17. [Memory System](#17-memory-system)
18. [Knowledge Graph System](#18-knowledge-graph-system)
19. [Roadmap Engine](#19-roadmap-engine)
20. [Syllabus Processing Pipeline](#20-syllabus-processing-pipeline)
21. [Document Processing Pipeline](#21-document-processing-pipeline)
22. [OCR Pipeline](#22-ocr-pipeline)
23. [RAG Architecture](#23-rag-architecture)
24. [Embedding Strategy](#24-embedding-strategy)
25. [Vector Database Design](#25-vector-database-design)
26. [Retrieval Strategy](#26-retrieval-strategy)
27. [Chat System Design](#27-chat-system-design)
28. [AI Tutor Orchestration Layer](#28-ai-tutor-orchestration-layer)
29. [Model Abstraction Layer](#29-model-abstraction-layer)
30. [Analytics System](#30-analytics-system)
31. [Assessment System](#31-assessment-system)
32. [Quiz Engine](#32-quiz-engine)
33. [Knowledge Graph Visualization](#33-knowledge-graph-visualization)
34. [UI Architecture](#34-ui-architecture)
35. [State Management Architecture](#35-state-management-architecture)
36. [API Design](#36-api-design)
37. [Internal Service Boundaries](#37-internal-service-boundaries)
38. [Event Flow Diagrams](#38-event-flow-diagrams)
39. [Data Flow Diagrams](#39-data-flow-diagrams)
40. [Persistence Layer](#40-persistence-layer)
41. [Caching Layer](#41-caching-layer)
42. [Logging Strategy](#42-logging-strategy)
43. [Error Handling](#43-error-handling)
44. [Security Model](#44-security-model)
45. [Privacy Model](#45-privacy-model)
46. [Testing Strategy](#46-testing-strategy)
47. [CI/CD Strategy](#47-cicd-strategy)
48. [Packaging Strategy](#48-packaging-strategy)
49. [Local Deployment Strategy](#49-local-deployment-strategy)
50. [start.bat Behaviour](#50-startbat-behaviour)
51. [Future Extension Points](#51-future-extension-points)
52. [Plugin System](#52-plugin-system)
53. [Scalability Considerations](#53-scalability-considerations)
54. [MVP Scope](#54-mvp-scope)
55. [Phase 2 Scope](#55-phase-2-scope)
56. [Phase 3 Scope](#56-phase-3-scope)
57. [Development Roadmap](#57-development-roadmap)
58. [Recommended Build Order](#58-recommended-build-order)
59. [Risks and Mitigations](#59-risks-and-mitigations)
60. [Exact Implementation Sequence](#60-exact-implementation-sequence)

---

## 1. Product Vision

### 1.1 Concept

LearningOS is a **local-first, AI-powered personal learning operating system** that runs entirely on the user's computer. It combines the conversational intelligence of a personal AI tutor with the structural depth of a knowledge management system and the pedagogical rigor of a learning platform.

The system is designed to feel like a deeply personalized educational companion — one that knows the learner's history, adapts to their pace, remembers every concept they've studied, and orchestrates their learning journey from first contact with a subject to mastery.

### 1.2 Design Philosophy

- **Local-first**: All data, memory, and state live on the user's machine. Nothing is sent to a server except AI inference calls to a configurable model API.
- **Persistent Intelligence**: The system accumulates a rich model of the learner over time — never resetting, never forgetting.
- **Structured Freedom**: The user may follow a strict syllabus, an AI-generated roadmap, or a hybrid of both.
- **Active Knowledge**: The system actively surfaces connections, prerequisites, and related concepts through a living knowledge graph.
- **Assessment-Driven**: The system tests knowledge, identifies gaps, and adjusts priorities dynamically.

### 1.3 Inspirations

| System | Inspiration Drawn |
|--------|-------------------|
| ChatGPT | Conversational interface, natural language tutor |
| Obsidian | Local-first file system, linked knowledge graph |
| Khan Academy | Topic sequencing, mastery-based progression |
| Notion | Structured workspace, profile organization |
| Anki | Spaced repetition, assessment feedback loop |

### 1.4 Target Users

- Students preparing for competitive exams (GATE, JEE, UPSC, GMAT, GRE)
- Self-learners pursuing technical skills (ML, programming, mathematics)
- Professionals upskilling in new domains
- Researchers organizing domain knowledge
- Anyone who wants a personal AI tutor that remembers them

### 1.5 Core Value Proposition

> A single unified system where your AI tutor knows your full learning history, your uploaded materials, your current roadmap, your strengths and gaps — and can answer any question, test your knowledge, and adapt its teaching in real time — all stored privately on your own machine.

---

## 2. User Stories

### 2.1 Profile & Onboarding

- **US-001**: As a new user, I want to create a learning profile for a specific subject or exam goal, so that the system can track my learning independently per domain.
- **US-002**: As a returning user, I want to switch between multiple learning profiles (e.g., GATE_CSE, JEE, Machine_Learning), so that my different study tracks remain separate.
- **US-003**: As a user, I want to set my learning preferences (pace, depth, mode) during profile creation, so that the AI adapts to my style from day one.
- **US-004**: As a user, I want to see an overview dashboard for each profile showing progress, active roadmap, and recent activity.

### 2.2 Syllabus & Document Upload

- **US-005**: As a user, I want to upload a PDF syllabus and have the system automatically extract subjects, chapters, and subtopics, so I don't have to manually organize my curriculum.
- **US-006**: As a user, I want to upload supporting documents (textbooks, notes, papers) that the AI can reference when answering questions.
- **US-007**: As a user, I want to upload image-based documents and have the system use OCR to extract text.
- **US-008**: As a user, I want to see which documents are currently indexed and searchable.

### 2.3 Roadmap

- **US-009**: As a user, I want to choose between Strict Mode, Adaptive Mode, or Hybrid Mode for my roadmap, so I can control how the AI organizes my learning.
- **US-010**: As a user, I want to see my full roadmap visualized as a structured list or graph, so I understand the complete learning path.
- **US-011**: As a user, I want to mark topics as complete, skip topics, or flag them for revisit.
- **US-012**: As a user in Adaptive Mode, I want the system to reorder topics based on my performance and identified weaknesses.

### 2.4 AI Tutor Chat

- **US-013**: As a user, I want to have a persistent conversation with an AI tutor that remembers everything from previous sessions.
- **US-014**: As a user, I want the tutor to answer questions by drawing from my uploaded documents, not just its base training.
- **US-015**: As a user, I want to search through all past conversations.
- **US-016**: As a user, I want the tutor to know my current topic in the roadmap and proactively guide me through it.
- **US-017**: As a user, I want to switch between learning modes (Deep, Revision, Summary, Quiz, Assessment) within a chat session.

### 2.5 Knowledge Graph

- **US-018**: As a user, I want to see a visual knowledge graph of all concepts I've encountered, showing how they connect.
- **US-019**: As a user, I want to click on a node in the graph and get a summary, links to related chats, and documents.
- **US-020**: As a user, I want the graph to automatically grow as I learn more topics.

### 2.6 Quizzes & Assessment

- **US-021**: As a user, I want the system to generate quizzes on any topic from my roadmap.
- **US-022**: As a user, I want quiz results to update my mastery scores and be reflected in the roadmap.
- **US-023**: As a user, I want to take timed assessments simulating exam conditions.
- **US-024**: As a user, I want to see a detailed breakdown of my assessment performance.

### 2.7 Progress & Analytics

- **US-025**: As a user, I want to see my completion percentage per subject, chapter, and subtopic.
- **US-026**: As a user, I want to see my learning velocity (topics per week) over time.
- **US-027**: As a user, I want to see my mastery scores per topic graphically.
- **US-028**: As a user, I want to identify my top strengths and most significant weaknesses.

### 2.8 Memory & Personalization

- **US-029**: As a user, I want the AI to remember that I struggle with recursion and proactively offer extra support.
- **US-030**: As a user, I want the system to surface "spaced repetition" reminders for topics I've not revisited recently.
- **US-031**: As a user, I want to browse and edit the memory the system has built about me.

---

## 3. Functional Requirements

### 3.1 Profile Management

- **FR-P01**: The system shall support creation of multiple independent learning profiles.
- **FR-P02**: Each profile shall have a unique identifier, name, description, goals, and metadata.
- **FR-P03**: Switching profiles shall be instantaneous and persist the last active profile across sessions.
- **FR-P04**: Profiles shall be deletable with full cascade deletion of associated data.
- **FR-P05**: Profile data export to a ZIP archive shall be supported.

### 3.2 Document Ingestion

- **FR-D01**: The system shall accept PDF, DOCX, TXT, PNG, JPG, JPEG, WEBP, and TIFF file formats.
- **FR-D02**: Documents shall be stored locally in the file system under the relevant profile directory.
- **FR-D03**: Document text shall be extracted and chunked for embedding.
- **FR-D04**: Image-based PDFs and standalone images shall be processed through an OCR pipeline.
- **FR-D05**: Documents shall be associated with either a profile globally or a specific roadmap node.
- **FR-D06**: Re-ingestion of updated documents shall be supported with delta detection.
- **FR-D07**: The system shall maintain document metadata: name, upload date, type, page count, chunk count, embedding status.

### 3.3 Roadmap Engine

- **FR-R01**: The system shall support three roadmap modes: Strict, Adaptive, and Hybrid.
- **FR-R02**: In Strict Mode, the roadmap shall mirror the uploaded syllabus structure exactly.
- **FR-R03**: In Adaptive Mode, the AI shall generate an optimal learning sequence considering prerequisites and learning science.
- **FR-R04**: In Hybrid Mode, the syllabus structure shall be preserved while AI inserts prerequisite nodes and supporting concepts.
- **FR-R05**: Each roadmap node shall have status: not_started, in_progress, completed, skipped, flagged.
- **FR-R06**: Completion of a node shall unlock dependent nodes.
- **FR-R07**: The roadmap shall be regenerable without losing progress data.

### 3.4 Knowledge Graph

- **FR-KG01**: The system shall maintain a persistent knowledge graph stored in a local graph database.
- **FR-KG02**: Nodes shall include: Concept, Chapter, Subject, Document, Note, Quiz.
- **FR-KG03**: Edges shall include: prerequisite_of, related_to, taught_in, referenced_by, learned_from, tested_by.
- **FR-KG04**: The graph shall be visualizable in the UI with interactive pan/zoom/click.
- **FR-KG05**: Graph nodes shall be enriched automatically as topics are encountered in chat or documents.
- **FR-KG06**: The graph shall be queryable: "Show all prerequisites of X", "What topics reference Y?"
- **FR-KG07**: Clicking a node shall display: description, mastery score, related documents, related chats.

### 3.5 Memory System

- **FR-M01**: The system shall maintain a persistent memory store per profile.
- **FR-M02**: Memory shall include: strengths, weaknesses, completed topics, preferences, assessments, interaction patterns.
- **FR-M03**: Memory shall be updated automatically after every chat session and assessment.
- **FR-M04**: The AI shall load relevant memory records at the start of each chat context window.
- **FR-M05**: Users shall be able to view, edit, and delete individual memory entries.
- **FR-M06**: Memory records shall have timestamps, source (chat/assessment/manual), and confidence scores.

### 3.6 Chat System

- **FR-C01**: All chat sessions shall be stored locally in a structured database.
- **FR-C02**: Chat history shall be searchable by keyword, date, topic, and mode.
- **FR-C03**: Each message shall be associated with: session_id, profile_id, timestamp, mode, referenced_documents, referenced_nodes.
- **FR-C04**: Chats shall be exportable as Markdown, PDF, or plain text.
- **FR-C05**: The system shall support streaming responses from the AI model.
- **FR-C06**: Chats shall be organized by session; sessions may be named and tagged by the user.

### 3.7 RAG System

- **FR-RAG01**: All uploaded documents shall be embedded using a configurable embedding model.
- **FR-RAG02**: The retrieval system shall search across: documents, notes, past chat summaries, and knowledge graph entries.
- **FR-RAG03**: Retrieval shall be context-aware: query embedding, profile context, current roadmap node, and mode shall influence ranking.
- **FR-RAG04**: Retrieved chunks shall be injected into the AI prompt with source citation metadata.
- **FR-RAG05**: The user shall see which documents and chunks were used to generate each response.

### 3.8 Assessment & Quiz

- **FR-AQ01**: The system shall generate quizzes in MCQ, short answer, true/false, and fill-in-the-blank formats.
- **FR-AQ02**: Quizzes may be topic-specific or span an entire subject.
- **FR-AQ03**: Assessment results shall update mastery scores in the memory system.
- **FR-AQ04**: Timed assessment mode shall simulate exam conditions with a countdown timer.
- **FR-AQ05**: Wrong answers shall trigger an explanation and optional deep-dive.
- **FR-AQ06**: All quiz attempts shall be persisted locally with full question/answer records.

### 3.9 Learning Modes

- **FR-LM01**: Deep Learning Mode: Comprehensive, step-by-step explanation with examples.
- **FR-LM02**: Revision Mode: Quick summaries of previously learned material.
- **FR-LM03**: Summary Mode: Ultra-concise bullet-point summaries.
- **FR-LM04**: General Knowledge Mode: Free-form conversation without roadmap anchoring.
- **FR-LM05**: Quiz Mode: Interactive Q&A to test understanding.
- **FR-LM06**: Assessment Mode: Formal timed test with scoring.

### 3.10 Analytics

- **FR-AN01**: The system shall track: topic completion dates, time spent per topic, quiz scores, mastery levels.
- **FR-AN02**: Progress dashboards shall show weekly, monthly, and all-time views.
- **FR-AN03**: Learning velocity (topics completed per unit time) shall be computed and displayed.
- **FR-AN04**: Heatmaps of daily activity shall be displayed similar to GitHub contribution graphs.
- **FR-AN05**: Weakness reports shall list topics with lowest mastery and most errors.

---

## 4. Non-Functional Requirements

### 4.1 Performance

- **NFR-P01**: Chat response first token latency must be under 2 seconds (excluding model inference time).
- **NFR-P02**: Document embedding for a 100-page PDF must complete within 5 minutes on average hardware.
- **NFR-P03**: Vector similarity search must return results in under 500ms for a corpus of 100,000 chunks.
- **NFR-P04**: UI interactions must feel instantaneous (under 100ms for local state changes).
- **NFR-P05**: Knowledge graph rendering must handle up to 2,000 nodes smoothly at 60fps.

### 4.2 Reliability

- **NFR-R01**: The system must not lose any data on unexpected shutdown; all writes must be atomic.
- **NFR-R02**: The backend must gracefully degrade if the AI model API is unreachable.
- **NFR-R03**: Database corruption scenarios must be detectable on startup with fallback to last valid backup.
- **NFR-R04**: All background jobs (embedding, OCR) must be resumable after restart.

### 4.3 Usability

- **NFR-U01**: The UI must be operable without technical knowledge.
- **NFR-U02**: The system must be launchable with a single double-click of start.bat.
- **NFR-U03**: First-time setup (profile creation, API key entry) must be completable in under 3 minutes.
- **NFR-U04**: The UI must be responsive and usable at screen resolutions from 1280×720 upward.

### 4.4 Privacy & Security

- **NFR-S01**: No user data shall leave the machine except to the configured AI model inference endpoint.
- **NFR-S02**: API keys must be stored in a local encrypted keystore, never in plaintext files.
- **NFR-S03**: Local database files must be stored in user-space directories, not global system directories.
- **NFR-S04**: The HTTP server must bind to localhost only (127.0.0.1), never 0.0.0.0.

### 4.5 Maintainability

- **NFR-M01**: The codebase must be modular; adding a new learning mode must not require changes to core modules.
- **NFR-M02**: All service boundaries must be defined via internal contracts (interfaces/schemas).
- **NFR-M03**: Configuration (model names, ports, paths) must be centralized in a single config file.
- **NFR-M04**: All database schema migrations must be versioned and applied automatically on startup.

### 4.6 Portability

- **NFR-PT01**: The system must run on Windows 10/11 as the primary target.
- **NFR-PT02**: The backend must be portable to macOS and Linux with no source changes (only installer differences).
- **NFR-PT03**: All file paths must use OS-agnostic path handling libraries.

---

## 5. System Architecture

### 5.1 Architectural Style

LearningOS uses a **local microkernel architecture** with a **service-oriented backend** running on `localhost`. The architecture has the following tiers:

```
[Browser UI] ←→ [Frontend Dev Server / Static Bundle]
      ↕
[FastAPI Backend (REST + WebSocket)]
      ↕
[Service Layer: RAG | Memory | Graph | Roadmap | Analytics | Quiz]
      ↕
[Data Layer: SQLite | ChromaDB | NetworkX/JSON Graph | File System]
      ↕
[AI Inference Layer: Model Abstraction → OpenAI / Anthropic / Ollama]
```

### 5.2 Component Overview

| Component | Responsibility |
|-----------|----------------|
| **Frontend (React/Vite)** | All user interaction, state display, real-time streaming |
| **FastAPI Backend** | Routing, authentication-free local API, WebSocket management |
| **Profile Service** | CRUD for profiles, context switching |
| **Ingestion Service** | Document upload, OCR, chunking, embedding coordination |
| **RAG Service** | Query-time retrieval, reranking, context assembly |
| **Memory Service** | Read/write to persistent memory store |
| **Graph Service** | Knowledge graph CRUD, query, enrichment |
| **Roadmap Service** | Roadmap generation, node state machine |
| **Chat Service** | Session management, message persistence, streaming |
| **Tutor Orchestrator** | Prompt construction, mode switching, multi-source context fusion |
| **Model Abstraction Layer** | Provider-agnostic AI inference |
| **Analytics Service** | Progress computation, metric aggregation |
| **Assessment Service** | Quiz generation, scoring, mastery updates |
| **Vector Store (ChromaDB)** | Embedding storage and similarity search |
| **Relational Store (SQLite)** | Structured data: profiles, chats, progress, memory |
| **Graph Store (JSON/NetworkX)** | Persistent knowledge graph |
| **File System** | Raw documents, exports, backups |

### 5.3 Communication Patterns

- **REST** (HTTP/1.1): All CRUD operations, document upload, settings.
- **WebSocket**: Real-time streaming of AI tutor responses token by token.
- **Internal Python calls**: Direct function calls between services within the same process.
- **Background task queue**: Celery-like in-process task queue for async jobs (embedding, OCR).

### 5.4 Process Model

On startup, exactly **two processes** are launched:
1. **Backend process**: Python FastAPI server (Uvicorn), port 8000.
2. **Frontend process**: Vite dev server (development) or static file server (production), port 5173.

All services run within the backend process. No external service processes required beyond ChromaDB (embedded, not a separate process).

---

## 6. High-Level Design

### 6.1 System Context Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    USER'S MACHINE                        │
│                                                         │
│  ┌───────────┐    HTTP/WS     ┌─────────────────────┐  │
│  │  Browser  │ ◄────────────► │  LearningOS Backend │  │
│  │  (React)  │                │  (FastAPI, Port 8000)│  │
│  └───────────┘                └─────────┬───────────┘  │
│                                         │               │
│              ┌──────────────────────────┼──────────┐   │
│              │          Data Layer       │          │   │
│              │                          │          │   │
│         ┌────▼────┐  ┌──────────┐  ┌───▼──────┐  │   │
│         │ SQLite  │  │ ChromaDB │  │ File Sys │  │   │
│         └─────────┘  └──────────┘  └──────────┘  │   │
│              └─────────────────────────────────────┘   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │            AI Inference (OUTBOUND ONLY)           │  │
│  │  OpenAI API / Anthropic API / Ollama (local)     │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 6.2 Module Dependency Map

```
Frontend
  └── API Client
        └── FastAPI Router
              ├── Profile Service
              ├── Ingestion Service → [OCR Pipeline, Chunker, Embedder → ChromaDB]
              ├── Chat Service → Tutor Orchestrator
              │     └── Tutor Orchestrator
              │           ├── RAG Service → ChromaDB
              │           ├── Memory Service → SQLite
              │           ├── Graph Service → Graph Store
              │           ├── Roadmap Service → SQLite
              │           └── Model Abstraction Layer → AI Provider
              ├── Analytics Service → SQLite
              ├── Assessment Service → Quiz Engine → Model Abstraction
              └── Settings Service → Config File
```

### 6.3 Data Ownership Map

| Data Category | Primary Store | Secondary/Cache |
|--------------|---------------|-----------------|
| Profiles | SQLite | In-memory dict |
| Chat sessions/messages | SQLite | Redis (optional) |
| Documents (raw) | File System | — |
| Document chunks/embeddings | ChromaDB | SQLite metadata |
| Memory records | SQLite | In-memory on load |
| Knowledge graph | JSON flat file + in-memory NetworkX | — |
| Roadmap nodes/edges | SQLite | In-memory state |
| Analytics events | SQLite | Aggregated cache |
| Quiz attempts | SQLite | — |
| Settings/config | TOML file | In-memory |
| API keys | Encrypted JSON | Never in memory beyond use |

---

## 7. Low-Level Design

### 7.1 Request Lifecycle: Chat Message

1. User types message in UI → Frontend fires HTTP POST to `/api/chat/message`.
2. Chat Service creates a new message record in SQLite with status `pending`.
3. Chat Service calls Tutor Orchestrator with: `{message, profile_id, session_id, mode}`.
4. Tutor Orchestrator:
   a. Loads current profile context from Profile Service.
   b. Loads active roadmap node from Roadmap Service.
   c. Loads relevant memory records from Memory Service (top-k by relevance).
   d. Calls RAG Service to retrieve document chunks relevant to the query.
   e. Assembles full prompt (system prompt + memory + roadmap context + RAG context + chat history + user message).
   f. Calls Model Abstraction Layer with assembled prompt.
5. Model Abstraction Layer streams tokens back.
6. Tutor Orchestrator pipes stream through WebSocket to Frontend.
7. On stream completion, final response text is written to SQLite via Chat Service.
8. Memory Service runs async job to extract memory-worthy facts from the exchange.
9. Graph Service runs async job to identify new concept nodes from the exchange.

### 7.2 Request Lifecycle: Document Upload

1. User drops a file on the Upload UI → Frontend fires HTTP POST multipart to `/api/documents/upload`.
2. Ingestion Service receives file bytes, writes to `data/profiles/{profile_id}/documents/raw/`.
3. File type is detected. Routing:
   - PDF, DOCX, TXT → Text Extractor.
   - PNG, JPG, TIFF, image-PDFs → OCR Pipeline.
4. Extracted text is chunked by the Chunker service.
5. Each chunk is assigned metadata: `{doc_id, chunk_index, page_number, source_title, profile_id}`.
6. Chunks are enqueued for embedding via the Embedder.
7. Embedder calls the configured embedding model and stores vectors in ChromaDB.
8. SQLite document metadata record is updated: status → `indexed`, chunk_count, embed_date.
9. Graph Service optionally extracts key concept mentions and creates/links graph nodes.
10. Frontend is notified via a WebSocket event: `{type: "document_indexed", doc_id}`.

### 7.3 Request Lifecycle: Roadmap Generation

1. User triggers "Generate Roadmap" from UI after uploading syllabus.
2. Roadmap Service reads the syllabus document's extracted structure from SQLite.
3. Based on selected mode:
   - **Strict**: Map syllabus chapters/topics directly to roadmap nodes.
   - **Adaptive**: Call AI with topic list and request optimal ordering with prerequisites.
   - **Hybrid**: Strict structure + AI-inserted prerequisites/bridging concepts.
4. AI response is parsed into a structured node/edge graph.
5. Roadmap graph is persisted to SQLite as nodes (id, title, type, status, parent_id, order_index) and edges (from_id, to_id, edge_type).
6. Frontend is notified and renders the roadmap.

### 7.4 Knowledge Graph Update Cycle

After every chat turn and after every document indexing:
1. Graph Enricher extracts entity mentions using the AI model (concepts, terms, named entities).
2. For each entity: check if node exists in graph. If not, create it.
3. Infer edges: if two concepts co-occur and the AI identifies a relationship, create an edge.
4. Update node metadata: `{last_seen, mention_count, mastery_score}`.
5. Persist updated graph to JSON file.
6. Invalidate in-memory graph cache so next query loads fresh data.

---

## 8. Technology Stack

### 8.1 Backend

| Technology | Version | Purpose |
|-----------|---------|---------|
| Python | 3.11+ | Primary backend language |
| FastAPI | 0.110+ | REST API and WebSocket server |
| Uvicorn | 0.29+ | ASGI server |
| SQLite | 3.39+ | Relational data store (via SQLAlchemy) |
| SQLAlchemy | 2.0+ | ORM and migration management |
| Alembic | 1.13+ | Database migrations |
| ChromaDB | 0.5+ | Local vector store (embedded mode) |
| NetworkX | 3.3+ | In-memory graph computation |
| python-docx | 1.1+ | DOCX text extraction |
| PyMuPDF (fitz) | 1.24+ | PDF text extraction and rendering |
| pytesseract | 0.3+ | OCR wrapper |
| Pillow | 10.0+ | Image processing |
| sentence-transformers | 2.7+ | Local embedding model option |
| openai | 1.30+ | OpenAI API client |
| anthropic | 0.26+ | Anthropic API client |
| httpx | 0.27+ | Async HTTP for Ollama calls |
| APScheduler | 3.10+ | Background job scheduling |
| cryptography | 42.0+ | API key encryption |
| python-multipart | 0.0.9 | File upload handling |
| Pydantic | 2.7+ | Schema validation |
| tomllib / tomli-w | stdlib / 1.0+ | Config file reading/writing |
| loguru | 0.7+ | Structured logging |
| pytest | 8.0+ | Testing |

### 8.2 Frontend

| Technology | Version | Purpose |
|-----------|---------|---------|
| React | 18.3+ | UI framework |
| TypeScript | 5.4+ | Type safety |
| Vite | 5.2+ | Build tool and dev server |
| React Router | 6.23+ | Client-side routing |
| Zustand | 4.5+ | Lightweight global state management |
| TanStack Query | 5.40+ | Server state / data fetching |
| Axios | 1.7+ | HTTP client |
| D3.js | 7.9+ | Knowledge graph visualization |
| React Flow | 11.11+ | Roadmap visualization |
| Chart.js / Recharts | 4.4+ | Analytics charts |
| Monaco Editor | 0.49+ | Note editor with markdown |
| React Markdown | 9.0+ | Rendering markdown responses |
| Highlight.js | 11.9+ | Code syntax highlighting |
| KaTeX | 0.16+ | Mathematical formula rendering |
| Lucide React | 0.383+ | Icon library |
| date-fns | 3.6+ | Date formatting |
| React Hot Toast | 2.4+ | Notifications |

### 8.3 OCR & Document Processing

| Technology | Purpose |
|-----------|---------|
| Tesseract OCR | Core OCR engine (system install) |
| pytesseract | Python wrapper |
| PyMuPDF | PDF rendering to image for OCR |
| python-docx | Word document parsing |
| chardet | Encoding detection for TXT files |

### 8.4 AI Model Providers (Configurable)

| Provider | Type | Notes |
|---------|------|-------|
| OpenAI GPT-4o / GPT-4-turbo | Cloud | Primary recommended |
| Anthropic Claude 3.5 Sonnet | Cloud | Alternative |
| Ollama (llama3, mistral, etc.) | Local | Full offline option |
| Google Gemini | Cloud | Alternative |

### 8.5 Embedding Models (Configurable)

| Model | Type | Notes |
|-------|------|-------|
| text-embedding-3-small | Cloud (OpenAI) | Default, cost-effective |
| text-embedding-3-large | Cloud (OpenAI) | Higher quality |
| BAAI/bge-small-en-v1.5 | Local (sentence-transformers) | Offline fallback |
| nomic-embed-text (Ollama) | Local | Fully local option |

### 8.6 Infrastructure Tools

| Tool | Purpose |
|------|---------|
| Node.js 20 LTS | Frontend build/dev server |
| npm / pnpm | Package manager |
| Python 3.11 venv | Backend isolation |
| Tesseract OCR (system) | OCR engine |
| Git | Version control |

---

## 9. Frontend Architecture

### 9.1 Application Structure

The frontend is a single-page React application built with Vite. It communicates exclusively with the local backend API.

### 9.2 Page/Route Map

| Route | Component | Description |
|-------|-----------|-------------|
| `/` | `HomePage` | Landing / profile selector |
| `/setup` | `SetupPage` | First-time configuration |
| `/profile/:id` | `DashboardPage` | Profile-level dashboard |
| `/profile/:id/chat` | `ChatPage` | AI tutor chat interface |
| `/profile/:id/chat/:sessionId` | `ChatPage` | Specific session |
| `/profile/:id/roadmap` | `RoadmapPage` | Roadmap visualization |
| `/profile/:id/documents` | `DocumentsPage` | Document management |
| `/profile/:id/graph` | `GraphPage` | Knowledge graph visualization |
| `/profile/:id/quiz` | `QuizPage` | Quiz/assessment interface |
| `/profile/:id/analytics` | `AnalyticsPage` | Progress and analytics |
| `/profile/:id/memory` | `MemoryPage` | View/edit memory records |
| `/profile/:id/notes` | `NotesPage` | Generated and user notes |
| `/settings` | `SettingsPage` | Global settings, API keys |

### 9.3 Component Hierarchy

```
App
├── GlobalProviders (QueryClient, Router, Zustand)
├── Layout
│   ├── Sidebar
│   │   ├── ProfileSwitcher
│   │   ├── NavigationMenu
│   │   └── StatusIndicator (backend health, model status)
│   ├── TopBar
│   │   ├── BreadcrumbNav
│   │   ├── ModeSelector
│   │   └── SearchBar
│   └── MainContent (outlet)
├── ChatPage
│   ├── ChatSessionList
│   ├── ChatWindow
│   │   ├── MessageList
│   │   │   └── MessageBubble (with source citations)
│   │   ├── StreamingIndicator
│   │   └── ChatInput (with mode, file attach)
│   └── ContextPanel (roadmap node, memory, docs used)
├── RoadmapPage
│   ├── RoadmapControls (mode selector, regenerate)
│   ├── RoadmapTree (ReactFlow)
│   │   └── RoadmapNode (with status, mastery indicator)
│   └── NodeDetailPanel
├── GraphPage
│   ├── GraphControls (filter, zoom)
│   ├── D3GraphCanvas
│   └── NodeDetailSidebar
├── DocumentsPage
│   ├── DropZone
│   ├── DocumentList
│   └── DocumentDetailPanel (chunks, status)
├── QuizPage
│   ├── QuizSetup
│   ├── QuizSession
│   │   ├── QuestionCard
│   │   └── TimerBar
│   └── QuizResults
├── AnalyticsPage
│   ├── ProgressOverview
│   ├── ActivityHeatmap
│   ├── MasteryChart
│   ├── VelocityGraph
│   └── WeaknessReport
└── MemoryPage
    ├── MemoryFilter
    └── MemoryCard (editable)
```

### 9.4 Design System

#### Color Palette (Dark Mode Primary)

```
Background:       #0D0F14
Surface:          #161B22
Surface Elevated: #1C2128
Border:           #30363D
Primary:          #5865F2 (Indigo-Purple)
Primary Light:    #7C88FF
Accent:           #22D3EE (Cyan)
Success:          #3FB950
Warning:          #D29922
Error:            #F85149
Text Primary:     #E6EDF3
Text Secondary:   #8B949E
Text Muted:       #484F58
```

#### Typography

```
Font Primary:    'Inter', sans-serif
Font Mono:       'JetBrains Mono', monospace
Scale: 12/14/16/18/20/24/28/32/40/48px
Weight: 400 / 500 / 600 / 700
```

#### Spacing System

Base unit: 4px. All spacing is multiples of 4.

#### Animation Principles

- All transitions: 150ms ease-out for micro, 300ms ease-out for panels.
- Loading skeletons for all async data.
- Streaming text uses a typewriter effect.
- Graph node hover: 200ms scale + glow.

---

## 10. Backend Architecture

### 10.1 FastAPI Application Structure

The backend is organized as a **service-oriented FastAPI application** in a single Python process. Each logical domain has its own router, service class, and data access layer.

### 10.2 Router Organization

```
/api
├── /profiles       → profiles_router
├── /documents      → documents_router
├── /chat           → chat_router
├── /roadmap        → roadmap_router
├── /graph          → graph_router
├── /memory         → memory_router
├── /quiz           → quiz_router
├── /analytics      → analytics_router
├── /notes          → notes_router
├── /settings       → settings_router
└── /health         → health_router

/ws
└── /chat/{session_id}  → WebSocket endpoint for streaming
```

### 10.3 Service Layer Pattern

Each service follows this contract pattern:

```
RouterLayer  →  ServiceClass  →  RepositoryClass  →  DataLayer
```

- **Router**: HTTP parameter extraction, response serialization.
- **Service**: Business logic, orchestration between repositories.
- **Repository**: All database reads/writes, vector store access.
- **DataLayer**: SQLAlchemy models, ChromaDB collections, file I/O.

### 10.4 Dependency Injection

FastAPI's dependency injection system is used throughout:
- `get_db()` → yields a SQLAlchemy session.
- `get_vector_store()` → yields ChromaDB collection handles.
- `get_profile()` → resolves and validates profile_id from request.
- `get_model_client()` → yields the configured AI model client.

### 10.5 Startup Sequence

On application startup (`lifespan` context manager):
1. Load and validate config from `settings.toml`.
2. Initialize SQLite database and run Alembic migrations.
3. Initialize ChromaDB client (embedded, pointing to data directory).
4. Load Knowledge Graph from JSON file into NetworkX.
5. Initialize background task scheduler.
6. Register shutdown handlers.
7. Log "LearningOS Backend ready" with version and port.

### 10.6 Middleware Stack

Applied in order (outermost to innermost):
1. **CORS Middleware**: Allow `http://localhost:5173` and `http://127.0.0.1:5173`.
2. **Request ID Middleware**: Assign unique UUID to each request for log tracing.
3. **Timing Middleware**: Log request duration.
4. **Error Handler Middleware**: Catch unhandled exceptions, return structured JSON error.
5. **Static Files Mount**: Serve frontend build at `/` in production mode.

---

## 11. Database Architecture

### 11.1 SQLite Design Principles

- Single SQLite database file per LearningOS installation.
- All tables use integer primary keys with UUID stored as TEXT for external references.
- All timestamps stored as ISO 8601 strings in UTC.
- Foreign key constraints enforced (`PRAGMA foreign_keys = ON`).
- WAL mode enabled for concurrent read performance (`PRAGMA journal_mode = WAL`).

### 11.2 Core Table Definitions (Logical)

#### profiles
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT (UUID) | Primary Key |
| name | TEXT | Display name |
| description | TEXT | Optional |
| goal | TEXT | GATE_CSE, JEE, custom |
| mode | TEXT | strict/adaptive/hybrid |
| created_at | TEXT | ISO 8601 |
| updated_at | TEXT | ISO 8601 |
| is_active | BOOLEAN | Last used profile |
| settings_json | TEXT | JSON blob for preferences |
| color | TEXT | UI color tag |
| icon | TEXT | Icon identifier |

#### documents
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT (UUID) | Primary Key |
| profile_id | TEXT | FK → profiles |
| filename | TEXT | Original filename |
| file_path | TEXT | Relative path in data dir |
| file_type | TEXT | pdf/docx/txt/image |
| status | TEXT | pending/extracting/chunking/indexing/indexed/error |
| page_count | INTEGER | |
| chunk_count | INTEGER | |
| word_count | INTEGER | |
| uploaded_at | TEXT | |
| indexed_at | TEXT | |
| error_message | TEXT | If status=error |
| is_syllabus | BOOLEAN | Marks the primary syllabus doc |
| roadmap_node_id | TEXT | Optional FK to roadmap_nodes |

#### chat_sessions
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT (UUID) | Primary Key |
| profile_id | TEXT | FK → profiles |
| title | TEXT | Auto-generated or user-named |
| mode | TEXT | deep/revision/summary/general/quiz/assessment |
| created_at | TEXT | |
| updated_at | TEXT | |
| roadmap_node_id | TEXT | Optional: anchored topic |
| tags | TEXT | JSON array |
| message_count | INTEGER | Denormalized count |
| is_archived | BOOLEAN | |

#### chat_messages
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT (UUID) | Primary Key |
| session_id | TEXT | FK → chat_sessions |
| profile_id | TEXT | FK → profiles |
| role | TEXT | user/assistant/system |
| content | TEXT | Full message text |
| created_at | TEXT | |
| token_count | INTEGER | |
| retrieved_chunks | TEXT | JSON: list of {doc_id, chunk_id, score} |
| memory_ids_used | TEXT | JSON: list of memory record IDs |
| graph_nodes_mentioned | TEXT | JSON: list of node IDs |
| model_used | TEXT | e.g. gpt-4o |
| latency_ms | INTEGER | Time to generate |

#### roadmap_nodes
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT (UUID) | Primary Key |
| profile_id | TEXT | FK → profiles |
| roadmap_id | TEXT | FK → roadmaps |
| title | TEXT | |
| description | TEXT | |
| node_type | TEXT | subject/chapter/topic/prerequisite/bridge |
| status | TEXT | not_started/in_progress/completed/skipped/flagged |
| order_index | REAL | For sorting |
| parent_id | TEXT | FK → roadmap_nodes (nullable) |
| mastery_score | REAL | 0.0 - 1.0 |
| time_spent_minutes | INTEGER | |
| completed_at | TEXT | |
| ai_generated | BOOLEAN | True if AI inserted |
| metadata_json | TEXT | JSON for extra data |

#### roadmap_edges
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT (UUID) | Primary Key |
| roadmap_id | TEXT | FK → roadmaps |
| from_node_id | TEXT | FK → roadmap_nodes |
| to_node_id | TEXT | FK → roadmap_nodes |
| edge_type | TEXT | prerequisite/sequential/optional |

#### roadmaps
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT (UUID) | Primary Key |
| profile_id | TEXT | FK → profiles |
| name | TEXT | |
| mode | TEXT | strict/adaptive/hybrid |
| created_at | TEXT | |
| version | INTEGER | Increments on regeneration |
| is_active | BOOLEAN | Only one active per profile |
| source_document_id | TEXT | FK → documents (syllabus) |

#### memory_records
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT (UUID) | Primary Key |
| profile_id | TEXT | FK → profiles |
| category | TEXT | strength/weakness/preference/completed/assessment/fact |
| subject | TEXT | Topic or domain this relates to |
| content | TEXT | The actual memory text |
| confidence | REAL | 0.0 - 1.0 |
| source | TEXT | chat/assessment/manual |
| source_id | TEXT | FK to source (session_id etc.) |
| created_at | TEXT | |
| updated_at | TEXT | |
| is_active | BOOLEAN | False = soft deleted |
| embedding_id | TEXT | Reference to vector in ChromaDB |

#### quiz_attempts
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT (UUID) | Primary Key |
| profile_id | TEXT | FK → profiles |
| roadmap_node_id | TEXT | FK → roadmap_nodes (optional) |
| mode | TEXT | practice/timed_assessment |
| started_at | TEXT | |
| completed_at | TEXT | |
| score | REAL | 0.0 - 1.0 |
| total_questions | INTEGER | |
| correct_count | INTEGER | |
| time_limit_seconds | INTEGER | |
| questions_json | TEXT | Full JSON of questions and answers |

#### analytics_events
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT (UUID) | Primary Key |
| profile_id | TEXT | FK → profiles |
| event_type | TEXT | topic_started/topic_completed/quiz_taken/time_logged |
| entity_type | TEXT | roadmap_node/document/session |
| entity_id | TEXT | |
| value | REAL | Numeric value (minutes, score) |
| metadata_json | TEXT | |
| occurred_at | TEXT | |

#### notes
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT (UUID) | Primary Key |
| profile_id | TEXT | FK → profiles |
| roadmap_node_id | TEXT | Optional FK |
| title | TEXT | |
| content | TEXT | Markdown |
| source | TEXT | ai_generated/user_written |
| created_at | TEXT | |
| updated_at | TEXT | |
| tags | TEXT | JSON array |

### 11.3 Index Strategy

Indexes on: `profile_id` on all profile-scoped tables, `created_at` on time-series tables, `status` on documents/roadmap_nodes, `category` on memory_records, `session_id` on chat_messages.

Full-text search (FTS5) virtual tables on: `chat_messages.content`, `memory_records.content`, `notes.content`.

---

## 12. Local Storage Strategy

### 12.1 Storage Layers

| Layer | Technology | Data |
|-------|-----------|------|
| Structured | SQLite (WAL mode) | All relational data |
| Vector | ChromaDB (embedded) | Embeddings and similarity search |
| Graph | JSON file + NetworkX | Knowledge graph |
| Blob | File System | Raw documents, exports |
| Config | TOML file | Application settings |
| Secrets | Encrypted JSON (Fernet) | API keys |

### 12.2 Data Directory Structure

All application data is stored in `~/.learningos/data/` (or `%USERPROFILE%\.learningos\data\` on Windows).

This location is configurable in `settings.toml`.

### 12.3 Backup Strategy

- SQLite database is backed up automatically every 24 hours using SQLite's online backup API.
- Backups are stored in `~/.learningos/backups/` with rotation (keep last 7 backups).
- ChromaDB data directory is included in backups via file copy.
- Knowledge graph JSON is included in backups.
- Documents directory is NOT backed up automatically (user manages their own files).

### 12.4 Storage Estimates

Per 100-page PDF:
- Raw file: ~5 MB
- Extracted text: ~200 KB
- Chunks (500-token): ~800 chunks
- Embeddings (1536-dim float32): ~4.7 MB in ChromaDB

A profile with 20 documents, 1,000 chat messages, 200 memory records:
- SQLite DB: ~15 MB
- ChromaDB: ~100 MB
- Raw documents: ~100 MB
- Total: ~215 MB

---

## 13. File System Layout

```
~/.learningos/
├── data/
│   ├── learningos.db              # Main SQLite database
│   ├── vector_store/              # ChromaDB directory
│   │   ├── chroma.sqlite3
│   │   └── {collection_uuid}/
│   ├── graph/
│   │   └── knowledge_graph.json   # Serialized graph
│   ├── profiles/
│   │   └── {profile_id}/
│   │       ├── documents/
│   │       │   ├── raw/           # Original uploaded files
│   │       │   └── extracted/     # Extracted text per document
│   │       ├── exports/           # User-exported data
│   │       └── notes/             # Generated note files (md)
│   └── cache/
│       └── {profile_id}/
│           └── roadmap_cache.json
├── backups/
│   ├── 2026-06-13T00-00-00/
│   │   ├── learningos.db
│   │   ├── vector_store/
│   │   └── knowledge_graph.json
│   └── ...
├── logs/
│   ├── backend.log
│   ├── ingestion.log
│   └── errors.log
├── config/
│   ├── settings.toml              # Main config
│   └── secrets.enc                # Encrypted API keys
└── temp/
    └── uploads/                   # Staging area for incoming files
```

---

## 14. Repository Structure

```
learningos/
├── README.md
├── start.bat                      # Windows launcher
├── start.sh                       # Unix launcher
├── setup.bat                      # One-time setup script
├── setup.sh
├── .env.example                   # Environment variable template
├── .gitignore
├── backend/
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── app/
│   │   ├── main.py               # FastAPI app factory
│   │   ├── config.py             # Settings loader
│   │   ├── dependencies.py       # DI functions
│   │   ├── lifespan.py           # Startup/shutdown
│   │   ├── routers/
│   │   │   ├── profiles.py
│   │   │   ├── documents.py
│   │   │   ├── chat.py
│   │   │   ├── roadmap.py
│   │   │   ├── graph.py
│   │   │   ├── memory.py
│   │   │   ├── quiz.py
│   │   │   ├── analytics.py
│   │   │   ├── notes.py
│   │   │   ├── settings.py
│   │   │   └── health.py
│   │   ├── services/
│   │   │   ├── profile_service.py
│   │   │   ├── ingestion_service.py
│   │   │   ├── chat_service.py
│   │   │   ├── roadmap_service.py
│   │   │   ├── graph_service.py
│   │   │   ├── memory_service.py
│   │   │   ├── quiz_service.py
│   │   │   ├── analytics_service.py
│   │   │   ├── notes_service.py
│   │   │   └── tutor_orchestrator.py
│   │   ├── pipelines/
│   │   │   ├── ocr_pipeline.py
│   │   │   ├── document_extractor.py
│   │   │   ├── chunker.py
│   │   │   ├── embedder.py
│   │   │   └── syllabus_parser.py
│   │   ├── rag/
│   │   │   ├── retriever.py
│   │   │   ├── reranker.py
│   │   │   ├── context_assembler.py
│   │   │   └── citation_tracker.py
│   │   ├── models/
│   │   │   ├── abstraction.py    # Model Abstraction Layer
│   │   │   ├── openai_client.py
│   │   │   ├── anthropic_client.py
│   │   │   └── ollama_client.py
│   │   ├── graph/
│   │   │   ├── graph_store.py
│   │   │   ├── graph_enricher.py
│   │   │   └── graph_query.py
│   │   ├── db/
│   │   │   ├── database.py       # SQLAlchemy setup
│   │   │   ├── models.py         # ORM models
│   │   │   └── repositories/
│   │   │       ├── profile_repo.py
│   │   │       ├── document_repo.py
│   │   │       ├── chat_repo.py
│   │   │       ├── roadmap_repo.py
│   │   │       ├── memory_repo.py
│   │   │       ├── quiz_repo.py
│   │   │       └── analytics_repo.py
│   │   ├── schemas/
│   │   │   ├── profile_schemas.py
│   │   │   ├── document_schemas.py
│   │   │   ├── chat_schemas.py
│   │   │   ├── roadmap_schemas.py
│   │   │   ├── memory_schemas.py
│   │   │   ├── quiz_schemas.py
│   │   │   └── analytics_schemas.py
│   │   ├── tasks/
│   │   │   ├── scheduler.py
│   │   │   ├── embedding_task.py
│   │   │   ├── memory_extraction_task.py
│   │   │   ├── graph_enrichment_task.py
│   │   │   └── backup_task.py
│   │   ├── security/
│   │   │   └── keystore.py
│   │   └── utils/
│   │       ├── file_utils.py
│   │       ├── text_utils.py
│   │       ├── date_utils.py
│   │       └── id_utils.py
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── fixtures/
└── frontend/
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── index.html
    ├── public/
    │   └── favicon.ico
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── router.tsx
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
        │   └── settings.ts
        ├── stores/
        │   ├── profileStore.ts
        │   ├── chatStore.ts
        │   ├── uiStore.ts
        │   └── settingsStore.ts
        ├── hooks/
        │   ├── useChat.ts
        │   ├── useProfile.ts
        │   ├── useRoadmap.ts
        │   ├── useGraph.ts
        │   └── useStreaming.ts
        ├── components/
        │   ├── layout/
        │   ├── chat/
        │   ├── roadmap/
        │   ├── graph/
        │   ├── quiz/
        │   ├── analytics/
        │   ├── memory/
        │   ├── documents/
        │   └── shared/
        ├── pages/
        │   ├── HomePage.tsx
        │   ├── SetupPage.tsx
        │   ├── DashboardPage.tsx
        │   ├── ChatPage.tsx
        │   ├── RoadmapPage.tsx
        │   ├── DocumentsPage.tsx
        │   ├── GraphPage.tsx
        │   ├── QuizPage.tsx
        │   ├── AnalyticsPage.tsx
        │   ├── MemoryPage.tsx
        │   ├── NotesPage.tsx
        │   └── SettingsPage.tsx
        ├── types/
        │   └── index.ts
        └── styles/
            ├── globals.css
            ├── tokens.css
            └── animations.css
```

---

## 15. Directory Tree

The above section (14) contains the complete directory tree. Key notes:

- `backend/app/` is the Python package root.
- `backend/app/routers/` — thin HTTP layer only.
- `backend/app/services/` — all business logic.
- `backend/app/db/repositories/` — all data access.
- `backend/app/pipelines/` — document processing steps.
- `backend/app/rag/` — retrieval-augmented generation components.
- `backend/app/models/` — AI model provider abstraction.
- `backend/app/graph/` — knowledge graph management.
- `backend/app/tasks/` — background async tasks.
- `frontend/src/api/` — typed API call functions.
- `frontend/src/stores/` — Zustand state slices.
- `frontend/src/hooks/` — React hooks wrapping business logic.

---

## 16. Profile System

### 16.1 Profile Data Model

A Profile is the top-level organizational unit. Every piece of data in LearningOS belongs to a profile. Profiles are completely isolated from each other.

### 16.2 Profile Attributes

- **id**: UUID, immutable.
- **name**: User-defined display name (e.g., "GATE CSE 2027").
- **goal**: Enum or free text (GATE_CSE / JEE / ML / Custom).
- **description**: Optional multi-line text.
- **roadmap_mode**: Default mode (strict/adaptive/hybrid).
- **color**: Hex color for UI differentiation.
- **icon**: Name from icon set (book, brain, code, math, etc.).
- **created_at**: Timestamp.
- **settings_json**: Per-profile overrides for AI settings (model, temperature, etc.).

### 16.3 Profile Context Object

When the backend handles any profile-scoped request, it assembles a `ProfileContext` object containing:
- Profile metadata.
- Current active roadmap node.
- Active learning mode.
- Recent memory summary (top 10 relevant records).
- Session continuity token.

This context is passed through the orchestration layer.

### 16.4 Profile Switching

- Frontend stores `activeProfileId` in Zustand.
- Persisted to localStorage for browser refresh survival.
- On profile switch, frontend clears all profile-scoped query caches.
- Backend does not maintain session affinity; all requests include `profile_id`.

### 16.5 Profile Export/Import

Export: Creates a ZIP containing:
- Profile metadata JSON.
- SQLite dump filtered to the profile's rows.
- Raw documents directory.
- Extracted text and notes.
- Knowledge graph subgraph for the profile.

Import: Reverse of above. Detects ID conflicts and resolves via re-mapping.

---

## 17. Memory System

### 17.1 Memory Philosophy

Memory is the core differentiator of LearningOS. The system must remember not just facts, but the learner's behavioral patterns, emotional relationship with topics, historical performance, and evolving understanding.

### 17.2 Memory Categories

| Category | Description | Example |
|----------|-------------|---------|
| `strength` | Topics the user understands well | "Strong in dynamic programming" |
| `weakness` | Topics needing more attention | "Struggles with pointer arithmetic" |
| `completed` | Completed roadmap nodes | "Finished OS: Memory Management" |
| `preference` | Learning style preferences | "Prefers examples over theory" |
| `assessment` | Quiz/test performance records | "Scored 40% on Graphs quiz" |
| `fact` | Factual things the user stated | "Uses Python 3.12" |
| `context` | Situational learning context | "Preparing for exam in 2 months" |

### 17.3 Memory Extraction Pipeline

After every chat session turn:
1. Memory Extractor receives the last N message pairs.
2. Constructs an extraction prompt: "Extract any learning-relevant facts, strengths, weaknesses, or preferences from this conversation."
3. AI returns a JSON array of `{category, subject, content, confidence}` objects.
4. Memory Service deduplicates against existing records (embedding similarity check).
5. New records are inserted; existing records' confidence is updated.
6. All new memory records are also embedded and stored in ChromaDB for semantic retrieval.

### 17.4 Memory Retrieval at Chat Time

Before constructing a tutor prompt:
1. Query ChromaDB memory collection with: embedding of user's current message.
2. Retrieve top-5 most semantically similar memory records.
3. Also fetch all `weakness` records for the current roadmap node's subject.
4. Combine into a "Memory Context" block appended to the system prompt.

### 17.5 Memory Confidence Decay

Memory records have a `confidence` score. Over time:
- Records not reinforced by new sessions slowly decay in confidence.
- Records contradicted by new evidence are updated or soft-deleted.
- APScheduler runs a weekly decay job.

### 17.6 Memory UI

The Memory Page displays all records grouped by category. Users can:
- View confidence scores and source.
- Edit content of any record.
- Delete records.
- Add manual memory entries.
- Filter by subject/category.

---

## 18. Knowledge Graph System

### 18.1 Graph Data Model

The knowledge graph is an undirected/directed multigraph stored as a JSON file and loaded into memory as a NetworkX graph at startup.

#### Node Schema
```json
{
  "id": "uuid",
  "label": "Dynamic Programming",
  "type": "concept | chapter | subject | document | note | quiz",
  "profile_id": "uuid",
  "description": "...",
  "mastery_score": 0.75,
  "mention_count": 12,
  "first_seen": "2026-01-01T00:00:00",
  "last_seen": "2026-06-13T00:00:00",
  "roadmap_node_id": "uuid | null",
  "document_ids": ["uuid", "uuid"],
  "chat_session_ids": ["uuid"]
}
```

#### Edge Schema
```json
{
  "id": "uuid",
  "source": "node_id",
  "target": "node_id",
  "type": "prerequisite_of | related_to | taught_in | referenced_by | learned_from | tested_by",
  "weight": 0.8,
  "created_at": "..."
}
```

### 18.2 Graph Enrichment Process

Three triggers for graph enrichment:
1. **Document indexed**: NLP extraction of key concepts. Create nodes for each. Link to document node.
2. **Chat turn completed**: Extract mentioned concepts. Link to session node and roadmap node.
3. **Quiz completed**: Link quiz node to tested concepts. Update mastery_score on concept nodes.

### 18.3 Graph Persistence

- Primary store: `knowledge_graph.json` (node-link format).
- Loaded into NetworkX at startup.
- Written back to file after every enrichment batch.
- In-memory graph is the authoritative source during runtime.
- Serialization uses NetworkX's `node_link_data()` / `node_link_graph()`.

### 18.4 Graph Queries

Implemented in `graph_query.py`:
- `get_prerequisites(node_id)` → BFS ancestors via prerequisite edges.
- `get_related(node_id, depth=2)` → Neighborhood subgraph.
- `get_concept_path(from_id, to_id)` → Shortest path.
- `find_nodes_by_label(query)` → Fuzzy string match on labels.
- `get_weak_concepts(profile_id)` → Nodes where mastery_score < 0.5.
- `get_subgraph(node_ids)` → Extract subgraph for visualization.

---

## 19. Roadmap Engine

### 19.1 Roadmap Modes

#### Strict Mode
- Input: Syllabus document with extracted structure.
- Output: Roadmap nodes that directly mirror the syllabus hierarchy.
- Node types: Subject → Chapter → Topic.
- No AI modification of structure.
- AI may add descriptions to nodes but not add/remove them.

#### Adaptive Mode
- Input: List of topics extracted from syllabus (or user-provided goal string).
- Process:
  1. Prompt AI with topic list and user's profile (goal, time available, current knowledge).
  2. AI returns an ordered sequence with prerequisites identified.
  3. System builds a DAG from the AI response.
  4. Nodes inserted by AI are marked `ai_generated = True`.
- Output: Optimal learning sequence as a DAG.

#### Hybrid Mode
- Input: Syllabus structure + Adaptive Mode overlay.
- Process:
  1. Start with Strict Mode structure.
  2. For each chapter, AI identifies prerequisite concepts not covered in the syllabus.
  3. These prerequisite nodes are inserted as `bridge` nodes before the chapter.
  4. Bridge nodes link back to the chapter they unlock.
- Output: Enhanced syllabus graph with prerequisite scaffolding.

### 19.2 Roadmap Node State Machine

```
not_started → in_progress → completed
     ↓              ↓
  skipped        flagged (for revisit)
```

State transitions are triggered by:
- User action (mark complete, skip, flag).
- Quiz score update (high score → completed if not already).
- AI tutor completion signal (when topic is exhaustively covered in chat).

### 19.3 Roadmap Version Control

When a roadmap is regenerated:
- New version number assigned.
- Old roadmap is archived (not deleted).
- Progress data is migrated to new nodes via title matching heuristic.
- User is shown a diff of the changes and must confirm.

### 19.4 Roadmap Progress Computation

For each node:
- `completion`: Boolean (status == completed).
- `mastery_score`: Average of quiz scores for this topic (0.0–1.0).
- `time_spent`: Sum of analytics time events for this node.

For each parent node:
- `completion %`: `(completed_children / total_children) * 100`.
- `mastery_score`: Weighted average of child mastery scores.

---

## 20. Syllabus Processing Pipeline

### 20.1 Pipeline Stages

```
Upload → File Storage → Type Detection → Text Extraction → Structure Detection → Topic Extraction → Roadmap Scaffold
```

### 20.2 Structure Detection

After text extraction, a specialized prompt is sent to the AI:

> "Given the following document text, identify and return the hierarchical structure as JSON: subjects, chapters, and subtopics. If the document is a syllabus or curriculum, extract the curriculum structure. If it is a textbook table of contents, extract that. Return a nested JSON object."

Expected response schema:
```json
{
  "document_type": "syllabus | toc | unstructured",
  "structure": [
    {
      "id": 1,
      "title": "Subject Name",
      "type": "subject",
      "children": [
        {
          "id": 2,
          "title": "Chapter Name",
          "type": "chapter",
          "children": [
            {"id": 3, "title": "Topic Name", "type": "topic"}
          ]
        }
      ]
    }
  ]
}
```

### 20.3 Fallback Strategy

If structure detection fails or produces low-confidence results:
1. Attempt regex-based heading detection (numbered lists, capitalized headers).
2. Attempt line-length-based heuristic (short lines are likely headings).
3. Show raw extracted text in UI and ask user to confirm/correct structure manually.

---

## 21. Document Processing Pipeline

### 21.1 Text Extraction by Type

| File Type | Library | Strategy |
|-----------|---------|---------|
| PDF (text-based) | PyMuPDF | Direct text extraction per page |
| PDF (image-based) | PyMuPDF + Tesseract | Render page to image → OCR |
| DOCX | python-docx | Paragraph and table extraction |
| TXT | stdlib | Direct read with chardet encoding |
| Image (PNG/JPG/etc.) | Pillow + Tesseract | Direct OCR |

### 21.2 Chunking Strategy

The Chunker splits extracted text into fixed-size overlapping windows:
- **Chunk size**: 512 tokens (configurable).
- **Overlap**: 64 tokens (configurable).
- **Splitting**: Token boundary aware (no mid-word splits).
- **Metadata preservation**: Each chunk retains `{page_number, section_title, char_offset_start, char_offset_end}`.

Chunking algorithm:
1. Tokenize text using tiktoken (for OpenAI) or a compatible tokenizer.
2. Slide window of 512 tokens with 64-token overlap.
3. At each boundary, try to snap to sentence boundary (period + space).
4. Assign metadata from the source page/section.

### 21.3 Embedding Queue

After chunking:
1. Chunks are inserted into an embedding queue in SQLite (`chunk_embedding_queue` table).
2. Background task `embedding_task.py` processes the queue in batches of 100.
3. Calls the configured embedding model with batch API call.
4. Stores vectors in ChromaDB with metadata.
5. Marks chunks as embedded in the queue.
6. Updates document status in `documents` table.

### 21.4 Document Update Handling

When the same file is re-uploaded:
1. Compute SHA-256 hash of new file.
2. Compare with stored hash for existing document.
3. If changed: delete old ChromaDB vectors for this document, reprocess.
4. If unchanged: skip, return existing document record.

---

## 22. OCR Pipeline

### 22.1 OCR Trigger Conditions

OCR is invoked when:
- File type is an image (PNG, JPG, TIFF, WEBP).
- PDF is flagged as image-based (PyMuPDF returns empty text for a page).

### 22.2 OCR Processing Steps

1. **Pre-processing** (Pillow):
   - Convert to grayscale.
   - Apply adaptive thresholding (Otsu's method).
   - Deskew if rotation > 2 degrees.
   - Scale to 300 DPI minimum.

2. **OCR** (Tesseract):
   - Language: English (configurable, supports multi-language).
   - PSM mode: 3 (auto page segmentation).
   - OEM mode: 3 (LSTM neural nets + legacy).
   - Extract text with bounding box metadata (`pytesseract.image_to_data`).

3. **Post-processing**:
   - Remove hyphenation across line breaks.
   - Join orphaned single characters.
   - Apply confidence threshold: discard words with confidence < 40%.

4. **Output**: Plain text string written to `documents/extracted/{doc_id}.txt`.

### 22.3 OCR Quality Indicator

Each OCR result includes an average confidence score. Documents with confidence < 60% are flagged in the UI with a warning: "Low OCR quality — document may not be searchable accurately."

### 22.4 Tesseract Setup

- Tesseract is a system-level dependency. `setup.bat` checks for its presence and provides download link if missing.
- Path to Tesseract executable is stored in `settings.toml`.
- Windows default: `C:\Program Files\Tesseract-OCR\tesseract.exe`.

---

## 23. RAG Architecture

### 23.1 RAG Overview

LearningOS uses a **multi-source RAG** approach where retrieval draws from:
1. Document chunks (primary corpus).
2. Memory records (personalization context).
3. Past chat summaries (conversation history).
4. Knowledge graph node descriptions (structured knowledge).
5. Notes (synthesized knowledge).

### 23.2 RAG Components

#### Retriever (`retriever.py`)
Executes similarity search across ChromaDB collections:
- `documents_collection`: All document chunks.
- `memory_collection`: Memory record embeddings.
- `notes_collection`: Note content embeddings.
- `chat_summaries_collection`: Summarized past sessions.

#### Reranker (`reranker.py`)
After retrieval, applies cross-attention reranking:
- Uses a small cross-encoder model locally (e.g., `ms-marco-MiniLM-L-6-v2`) or a BM25 reranker.
- Scores retrieved chunks against the original query.
- Sorts by reranked score.
- Returns top-K (default: 6) chunks.

#### Context Assembler (`context_assembler.py`)
Formats retrieved chunks into a structured context block:
```
[DOCUMENT: Introduction to Algorithms, Chapter 5, p. 127]
Content: ...chunk text...

[MEMORY: User struggles with recursive algorithms]

[PAST SESSION: 2026-05-20 — Discussed merge sort complexity]
```

#### Citation Tracker (`citation_tracker.py`)
Maintains a mapping of which source produced which content, so the UI can display citations per response.

### 23.3 RAG Prompt Template

```
SYSTEM:
You are a personal AI tutor for {profile_name}.
Current learning mode: {mode}.
Current roadmap topic: {current_node_title}.

LEARNER MEMORY:
{memory_context}

RELEVANT DOCUMENTS:
{rag_context}

ROADMAP CONTEXT:
{roadmap_summary}

CONVERSATION HISTORY:
{last_N_messages}

USER:
{user_message}
```

### 23.4 Context Window Management

The total context assembled must fit within the model's context limit minus response budget.

Budget allocation (for 128K context model):
- System prompt: 1,000 tokens.
- Memory context: 2,000 tokens.
- RAG context: 8,000 tokens.
- Chat history: 6,000 tokens (sliding window of last N messages).
- Response budget: 4,000 tokens.

If combined exceeds limit, truncation priority (lowest first):
1. Chat history (reduce oldest messages first).
2. RAG context (reduce to fewer chunks).
3. Memory context (reduce to top-3 records).
4. System prompt (never truncated).

---

## 24. Embedding Strategy

### 24.1 Embedding Model Selection

The embedding model is configurable and chosen based on the AI provider setting:
- **OpenAI**: `text-embedding-3-small` (1536 dimensions).
- **Anthropic**: Not natively supported; fallback to OpenAI or local.
- **Ollama**: `nomic-embed-text` (768 dimensions).
- **Local fallback**: `BAAI/bge-small-en-v1.5` via sentence-transformers (384 dimensions).

### 24.2 Embedding Batch Processing

- Documents are embedded in batches of 100 chunks per API call (OpenAI limit).
- Batching is handled by `embedder.py` with retry logic and exponential backoff.
- Failed batches are re-queued with error logging.

### 24.3 Embedding Storage Schema in ChromaDB

Each ChromaDB collection uses:
```
collection_name: "{profile_id}_documents"
document: chunk text
embedding: [float, ...]
metadata: {
  "doc_id": str,
  "chunk_index": int,
  "page_number": int,
  "source_title": str,
  "profile_id": str,
  "node_id": str | null,
  "chunk_hash": str
}
```

### 24.4 Embedding Versioning

If the embedding model changes:
- All existing embeddings are marked stale.
- A re-embedding job is queued.
- Stale embeddings remain searchable until re-embedded.
- User is notified of re-embedding progress in the UI.

---

## 25. Vector Database Design

### 25.1 ChromaDB Embedded Mode

ChromaDB runs in embedded (in-process) mode, writing to disk at `~/.learningos/data/vector_store/`. No external ChromaDB server process is needed.

### 25.2 Collections Structure

Per profile:
- `{profile_id}_documents` — Document chunks.
- `{profile_id}_memory` — Memory record embeddings.
- `{profile_id}_notes` — Note content embeddings.
- `{profile_id}_chat_summaries` — Summarized past sessions.

Global:
- `graph_nodes` — Knowledge graph node descriptions (all profiles).

### 25.3 ChromaDB Client Initialization

```python
# Pseudocode representation of intent
client = chromadb.PersistentClient(path="/path/to/vector_store")
collection = client.get_or_create_collection(
    name=collection_name,
    embedding_function=configured_embedding_function,
    metadata={"hnsw:space": "cosine"}
)
```

### 25.4 HNSW Parameters

For collections with large corpora (>10,000 vectors), tune:
- `hnsw:M = 32` (construction connections, default 16).
- `hnsw:ef_construction = 200` (build quality).
- `hnsw:ef = 100` (search quality).

These are set as collection metadata.

### 25.5 Deletion Strategy

When a document is deleted:
- All its chunk embeddings are deleted from ChromaDB by filtering on `doc_id` metadata.
- ChromaDB's `collection.delete(where={"doc_id": target_id})` is used.

---

## 26. Retrieval Strategy

### 26.1 Query Construction

Before querying ChromaDB, the raw user message is augmented:
1. **HyDE (Hypothetical Document Embedding)**: Generate a hypothetical document that would answer the query. Embed the hypothetical. Use its embedding for retrieval. This improves recall significantly.
2. **Query expansion**: Append current roadmap node title to the query string for context anchoring.

### 26.2 Multi-Collection Retrieval

Query is run against all 4 collections simultaneously (async parallel calls):
- Documents: top-10 candidates.
- Memory: top-5 candidates.
- Notes: top-5 candidates.
- Chat summaries: top-3 candidates.

Results are merged into a single list of 23 candidates.

### 26.3 Reranking

Cross-encoder reranker scores all 23 candidates against the original query.
Top-8 are selected for the final context.

### 26.4 Metadata Filtering

Before retrieval, filters applied:
- `profile_id = current_profile_id` (mandatory on all queries).
- Optional: `node_id = current_roadmap_node_id` (to bias toward current topic).
- Optional: `doc_id IN (user_selected_doc_ids)` (when user pins documents).

### 26.5 Diversity Penalty

To prevent the same document chunk appearing multiple times:
- After ranking, apply Maximal Marginal Relevance (MMR) to diversify results.
- Lambda parameter: 0.7 (balance relevance vs. diversity).

---

## 27. Chat System Design

### 27.1 Session Management

- Each chat is a "session" with a unique ID.
- Sessions are created on: first message sent, or user clicks "New Chat".
- Sessions are auto-titled using AI summary of first exchange (async, post-creation).
- Sessions can be renamed, tagged, and archived by the user.

### 27.2 Message Storage

Every message (user and assistant) is stored immediately:
- User message stored on send (before AI response).
- Assistant message stored on stream completion.
- Partial responses are NOT stored; only complete responses.
- If streaming is interrupted, the message is marked `status: incomplete`.

### 27.3 Chat History for Context

When constructing the prompt, the last N messages are included:
- Default: last 20 messages.
- If token budget is exceeded, reduce to last 10, then 5.
- Always include at minimum the last 2 messages (1 exchange).

### 27.4 WebSocket Streaming Protocol

Frontend connects to `ws://localhost:8000/ws/chat/{session_id}`.

Server sends events:
```json
{"type": "token", "data": "word"}
{"type": "done", "data": {"message_id": "uuid", "total_tokens": 1234}}
{"type": "citations", "data": [{"doc_title": "...", "chunk_id": "...", "page": 5}]}
{"type": "error", "data": {"message": "Model unavailable"}}
```

Frontend reconnects automatically on disconnect (exponential backoff, max 5 retries).

### 27.5 Chat Search

Full-text search on `chat_messages.content` using SQLite FTS5:
- Search box in sidebar filters sessions by matched messages.
- Results show session title + matching excerpt.
- Search is scoped to the active profile.

### 27.6 Chat Export

Export formats:
- **Markdown**: Each message as `## User` / `## Assistant` with timestamps.
- **PDF**: Rendered markdown (via `reportlab` or `weasyprint`).
- **Plain text**: Clean text without markup.

---

## 28. AI Tutor Orchestration Layer

### 28.1 Orchestrator Responsibilities

`tutor_orchestrator.py` is the brain of the system. It:
1. Assembles the full prompt for every AI request.
2. Dispatches to the Model Abstraction Layer.
3. Handles mode-specific behavior.
4. Triggers post-turn async jobs (memory extraction, graph enrichment).
5. Manages context window budget.

### 28.2 Mode-Specific Prompt Templates

Each learning mode has a different system prompt injection:

**Deep Learning Mode**:
> "Teach this concept comprehensively. Start with intuition, then formal definition, worked examples, edge cases, and common misconceptions. Do not skip steps."

**Revision Mode**:
> "The user has studied this before. Give a concise, dense review covering key points, formulas, and important distinctions. Assume prior knowledge."

**Summary Mode**:
> "Provide a structured bullet-point summary. Maximum 300 words. Cover only the most essential points."

**General Knowledge Mode**:
> "Answer freely. No topic constraints. Be conversational and curious."

**Quiz Mode**:
> "Ask the user one question at a time. Wait for their answer. Provide feedback. Then ask the next question. Do not answer for the user."

**Assessment Mode**:
> "Conduct a formal assessment. Present {N} questions. No hints. Evaluate answers strictly. Provide a final score and breakdown."

### 28.3 Tutor Persona

The AI tutor maintains a consistent persona defined in the base system prompt:
- Name: Optional (user-configurable, default: "Tutor").
- Tone: Encouraging, patient, rigorous.
- Style: Socratic when appropriate, direct when requested.
- Always acknowledges prior context explicitly: "Last time we discussed X, now let's continue with Y."

### 28.4 Topic Transition Logic

When the user moves to a new roadmap node:
1. Orchestrator detects node change from roadmap state.
2. Injects a transition message in the system prompt: "The learner just started the topic: {new_node}. Previous topic was: {prev_node}. Check if prerequisite knowledge is solid before proceeding."
3. Optionally triggers a "prerequisite check" question automatically.

---

## 29. Model Abstraction Layer

### 29.1 Provider Interface

All AI providers implement a common interface defined in `abstraction.py`:

```
class BaseModelClient:
    async def chat_complete(messages, stream, temperature, max_tokens) → AsyncGenerator[str] | str
    async def embed(texts: list[str]) → list[list[float]]
    def count_tokens(text: str) → int
    def get_model_info() → dict
```

### 29.2 Provider Implementations

**OpenAI** (`openai_client.py`):
- Uses `openai.AsyncOpenAI`.
- Supports streaming via async generator.
- Token counting via `tiktoken`.
- Supports: gpt-4o, gpt-4-turbo, gpt-3.5-turbo.

**Anthropic** (`anthropic_client.py`):
- Uses `anthropic.AsyncAnthropic`.
- Message format conversion (system prompt handling differs).
- Streaming via `stream` context manager.
- Supports: claude-3-5-sonnet, claude-3-opus.

**Ollama** (`ollama_client.py`):
- Uses `httpx.AsyncClient` to call Ollama REST API.
- Local endpoint: `http://localhost:11434`.
- Supports any installed Ollama model.
- Token counting via model-specific tokenizer or approximation (chars/4).

### 29.3 Model Configuration

In `settings.toml`:
```toml
[model]
provider = "openai"          # openai | anthropic | ollama
chat_model = "gpt-4o"
embedding_model = "text-embedding-3-small"
temperature = 0.7
max_tokens = 4096
context_window = 128000

[ollama]
base_url = "http://localhost:11434"
```

### 29.4 Fallback Chain

If primary provider fails:
1. Retry 3 times with exponential backoff.
2. If all retries fail, attempt fallback provider if configured.
3. If no fallback: return structured error to frontend with user-friendly message.

### 29.5 Cost Tracking

For cloud providers, track:
- Tokens sent (prompt tokens).
- Tokens received (completion tokens).
- Estimated cost based on published rates.
- Store in `analytics_events` table.
- Display in Settings > Usage page.

---

## 30. Analytics System

### 30.1 Event Collection

Every significant learner action generates an analytics event stored in `analytics_events`:
- `topic_started`: User opens a roadmap node.
- `topic_completed`: User marks a node complete.
- `time_logged`: Session closed or node changed (duration recorded).
- `quiz_taken`: Quiz attempt completed.
- `document_uploaded`: New document added.
- `chat_turn`: Each AI exchange.

### 30.2 Derived Metrics

Computed on-demand (not pre-aggregated):

**Completion %**:
```
(completed_nodes / total_nodes) * 100
```

**Mastery Score per topic**:
```
average(quiz_scores_for_topic)  or  0.0 if no quizzes taken
```

**Learning Velocity**:
```
topics_completed_in_last_7_days / 7  (topics/day)
```

**Time Spent (per topic, per week)**:
```
SUM(time_logged events) GROUP BY entity_id / time_period
```

**Streak**:
```
consecutive days with at least one topic_started or chat_turn event
```

### 30.3 Dashboard Widgets

| Widget | Description | Data Source |
|--------|-------------|-------------|
| Progress Ring | Overall % complete | roadmap_nodes |
| Weekly Heatmap | Daily activity (GitHub-style) | analytics_events |
| Mastery Bar Chart | Per-subject mastery scores | quiz_attempts |
| Velocity Line Chart | Topics/day over time | analytics_events |
| Weakness Table | Topics with score < 0.5 | memory_records + quiz_attempts |
| Time Distribution | Time per subject (pie chart) | analytics_events |
| Streak Counter | Current and longest streak | analytics_events |

### 30.4 Analytics Query Patterns

All analytics queries are run against SQLite with indexed columns. Complex aggregations use SQLite window functions. Query results are cached in-memory for 5 minutes to prevent re-computation on rapid page switches.

---

## 31. Assessment System

### 31.1 Assessment Types

| Type | Description | Scope |
|------|-------------|-------|
| Topic Quiz | Short practice quiz on one topic | Single roadmap node |
| Chapter Test | Medium assessment on a chapter | All nodes under a chapter |
| Full Mock Exam | Simulates complete exam | All nodes in roadmap |
| Weakness Drill | Focuses on low-mastery topics | AI-selected weak nodes |

### 31.2 Question Generation

Questions are generated by the AI using a structured prompt:

```
Generate {N} {format} questions on the topic: {topic_title}.
Use difficulty level: {difficulty}.
Reference this context: {rag_context}.
Return as JSON array:
[{
  "question": "...",
  "type": "mcq | short_answer | true_false | fill_blank",
  "options": ["A", "B", "C", "D"],  // MCQ only
  "correct_answer": "...",
  "explanation": "...",
  "difficulty": "easy | medium | hard",
  "concept_tags": ["tag1", "tag2"]
}]
```

### 31.3 Scoring System

**MCQ**: Binary (correct/incorrect).  
**Short Answer**: AI-evaluated against model answer with 0–1 score.  
**True/False**: Binary.  
**Fill in the Blank**: Normalized string comparison + AI check.

### 31.4 Mastery Update

After assessment completion:
1. Compute score per concept tag.
2. Update `roadmap_nodes.mastery_score` for each relevant node.
3. Update memory records for demonstrated strengths/weaknesses.
4. If mastery_score ≥ 0.8 and was `in_progress` → suggest marking as `completed`.

### 31.5 Assessment UI Flow

1. User selects assessment type and scope.
2. System generates questions (shown as loading state).
3. For timed mode: countdown timer visible, auto-submit on expiry.
4. Answer entry per question type.
5. On submit: immediate AI evaluation (streaming).
6. Results page: score, per-question breakdown, explanations.
7. Option to deep-dive on any wrong answer.

---

## 32. Quiz Engine

### 32.1 Quiz vs. Assessment Distinction

- **Quiz**: Casual, unscored practice. No timer. Instant feedback per question.
- **Assessment**: Formal, timed, scored. Full feedback at end only.

### 32.2 Adaptive Quiz Mode

The quiz engine can select questions adaptively:
1. Start with a medium-difficulty question.
2. If correct → increase difficulty.
3. If incorrect → decrease difficulty.
4. Track estimated ability using a simplified IRT (Item Response Theory) 1-PL model.
5. Stop after N questions or when ability estimate converges.

### 32.3 Spaced Repetition Integration

Questions from past quizzes are tagged with the `next_review_date` using SM-2 algorithm:
```
new_interval = old_interval * ease_factor
ease_factor adjusted based on quality of recall (0–5 scale)
next_review_date = today + new_interval
```

A daily "Review" session is surfaced in the dashboard showing due flashcard/quiz items.

### 32.4 Question Bank

All generated questions are stored in `quiz_attempts.questions_json` and can be recalled:
- User can "save" specific questions to a personal question bank.
- Question bank is stored in a separate `question_bank` table.
- User can manually edit questions or add their own.

---

## 33. Knowledge Graph Visualization

### 33.1 Visualization Library

D3.js with a force-directed graph layout is used for the knowledge graph visualization. This provides:
- Physics-based node positioning.
- Smooth animation of new node additions.
- Pan and zoom.
- Node drag-to-reposition.

### 33.2 Rendering Strategy

The graph can have thousands of nodes. Rendering strategy:
- **Initial load**: Show only nodes with `mention_count > 1` (filter noise).
- **Progressive loading**: Load full graph incrementally using a WebWorker for layout computation.
- **Level-of-detail**: At zoom < 0.3x, hide node labels; show only colored dots.
- **Clustering**: At zoom < 0.15x, cluster nodes by subject into supernodes.

### 33.3 Node Visual Encoding

| Attribute | Visual Encoding |
|-----------|----------------|
| Node type | Color (concept=blue, chapter=purple, doc=orange, quiz=green) |
| Mastery score | Node border thickness (0 = thin red, 1 = thick green) |
| Mention count | Node radius (log scale) |
| Current topic | Pulsing gold highlight |
| Weakness | Red glow |

### 33.4 Edge Visual Encoding

| Edge type | Style |
|-----------|-------|
| prerequisite_of | Solid directed arrow, dark grey |
| related_to | Dashed, light grey |
| taught_in | Dotted, blue |
| tested_by | Solid, green |

### 33.5 Interaction

- **Click node**: Opens side panel with node detail.
- **Double-click node**: Focus mode — dims all unconnected nodes.
- **Right-click node**: Context menu (go to topic, start quiz, view documents).
- **Hover edge**: Shows edge type tooltip.
- **Search bar**: Types in node label → highlights matching nodes.
- **Filter controls**: Toggle node types, edge types, mastery range.

---

## 34. UI Architecture

### 34.1 Layout System

Three-panel layout:
```
┌────────────┬────────────────────────────────┬──────────────┐
│  Sidebar   │        Main Content            │ Context Panel │
│  (240px)   │    (flex-1, scrollable)        │  (320px)     │
│            │                                │  (optional)  │
└────────────┴────────────────────────────────┴──────────────┘
```

Context Panel is page-specific:
- Chat: Shows active roadmap node, docs used, memory invoked.
- Roadmap: Shows selected node detail.
- Graph: Shows selected node detail.

### 34.2 Responsive Behavior

- < 1024px: Context panel hidden, accessible via drawer.
- < 768px: Sidebar collapsed to icon rail.
- < 480px: Not officially supported (desktop-first design).

### 34.3 Theme System

```css
/* Root CSS variables define all tokens */
:root {
  --color-bg-base: #0D0F14;
  --color-surface-1: #161B22;
  --color-surface-2: #1C2128;
  --color-border: #30363D;
  --color-primary: #5865F2;
  --color-primary-hover: #7C88FF;
  --color-accent: #22D3EE;
  --color-text-1: #E6EDF3;
  --color-text-2: #8B949E;
  --color-success: #3FB950;
  --color-warning: #D29922;
  --color-error: #F85149;
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;
}
```

Light mode is a stretch goal (Phase 3). All variables are in `:root` to make it switchable.

### 34.4 Loading States

Every async data fetch shows a skeleton loader matching the shape of the content. No spinner-only states.

### 34.5 Error States

Errors are shown inline in the component that triggered them, not as modal dialogs (except for critical errors requiring user action).

### 34.6 Empty States

Every list/grid view has a designed empty state with:
- Illustrative icon.
- Descriptive heading.
- Call-to-action button ("Upload your first document", "Start a chat", etc.).

---

## 35. State Management Architecture

### 35.1 State Categories

| Category | Tool | Reason |
|----------|------|--------|
| Server state (API data) | TanStack Query | Caching, refetch, loading states |
| Global app state | Zustand | Profile, settings, UI state |
| Local component state | React useState | Form values, toggles |
| URL state | React Router | Current page, selected IDs |

### 35.2 Zustand Stores

**profileStore**:
```
state: { activeProfileId, profiles[], loading }
actions: { setActiveProfile, loadProfiles, createProfile, deleteProfile }
```

**chatStore**:
```
state: { activeModeId, streamingMessage, isStreaming }
actions: { setMode, appendToken, clearStream }
```

**uiStore**:
```
state: { sidebarOpen, contextPanelOpen, theme, globalSearch }
actions: { toggleSidebar, setTheme, openSearch }
```

**settingsStore**:
```
state: { modelProvider, chatModel, embeddingModel, apiKeySet, ocrPath }
actions: { updateSettings, validateApiKey }
```

### 35.3 TanStack Query Key Strategy

All query keys follow the pattern: `[entity, scope, id, filters]`:
```
['profiles']
['profile', profileId]
['roadmap', profileId]
['roadmap', 'node', nodeId]
['chat', 'sessions', profileId]
['chat', 'messages', sessionId]
['graph', profileId]
['analytics', profileId, 'weekly']
['memory', profileId, { category: 'weakness' }]
```

### 35.4 Optimistic Updates

Used for:
- Marking a roadmap node as complete.
- Archiving a chat session.
- Deleting a memory record.

Pattern: Update Zustand/query cache immediately, rollback on API error.

---

## 36. API Design

### 36.1 API Conventions

- All routes prefixed with `/api/v1/`.
- Response envelope: `{ "data": ..., "error": null, "meta": {...} }`.
- Error response: `{ "data": null, "error": { "code": "...", "message": "...", "details": {} } }`.
- Pagination: `{ "data": [...], "meta": { "total": N, "page": 1, "per_page": 20 } }`.
- All IDs are UUIDs as strings.
- Dates are ISO 8601 strings.

### 36.2 Core API Endpoints

#### Profiles
```
GET    /api/v1/profiles                → List all profiles
POST   /api/v1/profiles                → Create profile
GET    /api/v1/profiles/{id}           → Get profile detail
PATCH  /api/v1/profiles/{id}           → Update profile
DELETE /api/v1/profiles/{id}           → Delete profile + cascade
POST   /api/v1/profiles/{id}/export    → Export profile ZIP
POST   /api/v1/profiles/import         → Import profile ZIP
```

#### Documents
```
POST   /api/v1/profiles/{pid}/documents          → Upload document
GET    /api/v1/profiles/{pid}/documents          → List documents
GET    /api/v1/profiles/{pid}/documents/{id}     → Document detail
DELETE /api/v1/profiles/{pid}/documents/{id}     → Delete document
GET    /api/v1/profiles/{pid}/documents/{id}/status → Embedding status
POST   /api/v1/profiles/{pid}/documents/{id}/reprocess → Re-embed
```

#### Chat
```
GET    /api/v1/profiles/{pid}/sessions           → List sessions
POST   /api/v1/profiles/{pid}/sessions           → New session
GET    /api/v1/profiles/{pid}/sessions/{id}      → Session + messages
PATCH  /api/v1/profiles/{pid}/sessions/{id}      → Rename/tag/archive
DELETE /api/v1/profiles/{pid}/sessions/{id}      → Delete session
POST   /api/v1/profiles/{pid}/sessions/{id}/messages → Send message (non-streaming)
GET    /api/v1/profiles/{pid}/sessions/search?q=...  → Full-text search
POST   /api/v1/profiles/{pid}/sessions/{id}/export   → Export chat

WS     /ws/chat/{session_id}?profile_id={pid}    → Streaming chat
```

#### Roadmap
```
GET    /api/v1/profiles/{pid}/roadmaps           → List roadmaps
POST   /api/v1/profiles/{pid}/roadmaps           → Generate roadmap
GET    /api/v1/profiles/{pid}/roadmaps/{id}      → Roadmap with nodes
PATCH  /api/v1/profiles/{pid}/roadmaps/{id}/nodes/{nid} → Update node status
POST   /api/v1/profiles/{pid}/roadmaps/{id}/regenerate → Regenerate
```

#### Knowledge Graph
```
GET    /api/v1/profiles/{pid}/graph              → Full graph (nodes + edges)
GET    /api/v1/profiles/{pid}/graph/nodes/{id}   → Node detail
PATCH  /api/v1/profiles/{pid}/graph/nodes/{id}   → Update node
GET    /api/v1/profiles/{pid}/graph/subgraph?center={id}&depth=2 → Subgraph
GET    /api/v1/profiles/{pid}/graph/search?q=... → Fuzzy node search
```

#### Memory
```
GET    /api/v1/profiles/{pid}/memory             → List memory records
POST   /api/v1/profiles/{pid}/memory             → Add manual record
PATCH  /api/v1/profiles/{pid}/memory/{id}        → Edit record
DELETE /api/v1/profiles/{pid}/memory/{id}        → Delete record
```

#### Quiz & Assessment
```
POST   /api/v1/profiles/{pid}/quiz/generate      → Generate quiz
POST   /api/v1/profiles/{pid}/quiz/{id}/submit   → Submit answers
GET    /api/v1/profiles/{pid}/quiz/history       → Past attempts
GET    /api/v1/profiles/{pid}/quiz/{id}/results  → Detailed results
```

#### Analytics
```
GET    /api/v1/profiles/{pid}/analytics/overview     → Dashboard summary
GET    /api/v1/profiles/{pid}/analytics/heatmap      → Activity heatmap data
GET    /api/v1/profiles/{pid}/analytics/mastery      → Mastery per topic
GET    /api/v1/profiles/{pid}/analytics/velocity     → Learning velocity
GET    /api/v1/profiles/{pid}/analytics/weaknesses   → Weakness report
```

#### Settings
```
GET    /api/v1/settings              → Get all settings
PATCH  /api/v1/settings              → Update settings
POST   /api/v1/settings/apikey       → Set encrypted API key
DELETE /api/v1/settings/apikey       → Remove API key
GET    /api/v1/settings/models       → List available models
POST   /api/v1/settings/test-connection → Test AI provider
```

#### Health
```
GET    /api/v1/health                → System health and version
GET    /api/v1/health/storage        → Storage usage stats
```

---

## 37. Internal Service Boundaries

### 37.1 Service Contracts

Each service exposes a typed Python interface. Services never access another service's repository directly — only through the service class.

| Caller | Calls | Prohibition |
|--------|-------|-------------|
| Tutor Orchestrator | RAGService, MemoryService, GraphService, RoadmapService, ChatService | May NOT call any repository directly |
| ChatService | ChatRepository, TutorOrchestrator | May NOT call VectorStore directly |
| IngestionService | DocumentRepository, Chunker, Embedder, GraphService | May NOT call ChatRepository |
| GraphService | GraphStore, DocumentRepository (read-only) | May NOT call ChromaDB directly |
| MemoryService | MemoryRepository, VectorStore (memory collection) | May NOT call DocumentRepository |
| AnalyticsService | AnalyticsRepository, RoadmapService (read-only) | May NOT write to non-analytics tables |
| QuizService | QuizRepository, ModelAbstraction, MemoryService | May NOT call ChatRepository |

### 37.2 Cross-Cutting Concerns

Handled outside service boundaries via middleware or injected utilities:
- **Logging**: Every service receives a logger instance via DI.
- **Error handling**: Services throw typed exceptions; routers convert to HTTP responses.
- **Metrics**: Timing decorators on service methods.
- **Async safety**: All services are async-safe; no blocking calls in async contexts.

---

## 38. Event Flow Diagrams

### 38.1 Chat Message Flow

```
User types message
       ↓
Frontend: POST /api/v1/.../messages  OR  WS send
       ↓
ChatService: create pending message record
       ↓
TutorOrchestrator: assemble context
  ├── ProfileService: load profile context
  ├── RoadmapService: get active node
  ├── MemoryService: retrieve relevant memories
  └── RAGService: retrieve relevant chunks
       ↓
ContextAssembler: build prompt
       ↓
ModelAbstractionLayer: stream → AI Provider
       ↓
WebSocket: stream tokens → Frontend
       ↓
ChatService: store complete message
       ↓
[Async background]
  ├── MemoryService: extract_memories(turn)
  └── GraphService: enrich_graph(turn)
```

### 38.2 Document Upload Flow

```
User drops file
       ↓
Frontend: POST multipart
       ↓
IngestionService: save to file system, create DB record (status: pending)
       ↓
TypeDetector: determine file type
       ↓
[If image/image-PDF] → OCRPipeline → extracted text
[If text-PDF]        → PyMuPDF extractor → extracted text
[If DOCX]            → python-docx extractor → extracted text
[If TXT]             → direct read → extracted text
       ↓
Chunker: split text into chunks (512 tokens, 64 overlap)
       ↓
EmbeddingQueue: enqueue chunks (status: queued)
       ↓
BackgroundTask: Embedder → batch embed → ChromaDB insert
       ↓
DocumentRepository: update status = indexed
       ↓
WebSocket event → Frontend: document_indexed
       ↓
[Optional] GraphService: extract concepts from document
```

### 38.3 Quiz Completion Flow

```
User submits quiz answers
       ↓
QuizService: evaluate answers
  ├── MCQ/T-F: direct comparison
  └── Short answer: AI evaluation call
       ↓
QuizRepository: store attempt with full Q&A JSON
       ↓
Scoring: compute per-concept scores
       ↓
RoadmapService: update mastery_score on relevant nodes
       ↓
MemoryService: create/update strength/weakness records
       ↓
AnalyticsService: record quiz_taken event
       ↓
GraphService: update mastery_score on graph nodes
       ↓
Frontend: render results page (streamed explanations)
```

---

## 39. Data Flow Diagrams

### 39.1 RAG Query Data Flow

```
User Query (text)
       ↓
QueryExpander: append roadmap node title
       ↓
HyDE: generate hypothetical doc → embed
       ↓
VectorStore (4 collections): similarity search (parallel)
       ↓
CandidateMerger: combine results (23 candidates)
       ↓
Reranker: score against original query
       ↓
MMR Diversifier: reduce redundancy
       ↓
Top-8 chunks selected
       ↓
ContextAssembler: format with source metadata
       ↓
TutorOrchestrator: inject into prompt
       ↓
AI Model: generate response
       ↓
CitationTracker: map response to sources
       ↓
Frontend: render response + citation footnotes
```

### 39.2 Memory Data Flow

```
Post-Chat Turn:
  Last N messages
       ↓
MemoryExtractor (AI prompt): extract {category, content, confidence}
       ↓
MemoryService: deduplicate via embedding similarity check
  ├── [New] Insert record + embed → memory ChromaDB collection
  └── [Existing] Update confidence score
       ↓
SQLite: persist memory record

Pre-Chat Turn:
  User message embedding
       ↓
ChromaDB memory collection: top-5 similar records
       ↓
SQLite: fetch all weakness records for current subject
       ↓
Merge → Memory Context Block → Prompt
```

### 39.3 Progress Data Flow

```
User completes topic (marks node = completed)
       ↓
RoadmapService: update node.status
       ↓
AnalyticsService: record topic_completed event
       ↓
RoadmapService: check if parent chapter is now 100% complete → cascade if so
       ↓
AnalyticsService: recompute progress percentages (cached)
       ↓
GraphService: update node.mastery_score from latest quiz data
       ↓
Frontend: real-time progress update via TanStack Query invalidation
```

---

## 40. Persistence Layer

### 40.1 Write Guarantees

- All SQLite writes are wrapped in transactions.
- On application shutdown, all pending writes are flushed.
- ChromaDB flushes are synchronous (embedded mode default).
- Knowledge graph JSON is written atomically (write to temp file, rename).

### 40.2 SQLAlchemy Session Management

- Async SQLAlchemy sessions using `AsyncSession`.
- Session-per-request pattern: each API request gets its own session.
- Sessions are closed in `finally` blocks via `contextmanager`.
- Background tasks use separate session scope.

### 40.3 Migration Strategy

Alembic manages schema migrations:
- `alembic revision --autogenerate` generates migration scripts.
- Migrations run automatically on startup before any request is served.
- Migration history is tracked in `alembic_version` table.
- On migration failure: log error, notify user, refuse to start (fail-safe).

### 40.4 Graph Persistence

```
NetworkX in-memory graph
       ↓ (on every write, async)
node_link_data() → JSON
       ↓
Atomic file write: write to .tmp → fsync → rename to knowledge_graph.json
```

Reads load from JSON on startup only. All runtime reads use the in-memory graph.

---

## 41. Caching Layer

### 41.1 In-Memory Caches

| Cache | What | TTL | Invalidation |
|-------|------|-----|-------------|
| Profile cache | Loaded profiles | Session lifetime | On profile update |
| Roadmap cache | Active roadmap structure | 10 minutes | On node update |
| Analytics cache | Aggregated metrics | 5 minutes | On new analytics event |
| Graph cache | NetworkX graph object | Until write | On enrichment |
| Settings cache | Config values | Session lifetime | On settings update |

### 41.2 TanStack Query Cache (Frontend)

- `staleTime`: 30 seconds for most queries.
- `cacheTime`: 5 minutes.
- Explicit invalidation on mutations (using `queryClient.invalidateQueries`).
- Optimistic updates for UX-critical mutations.

### 41.3 Embedding Cache

To avoid re-embedding the same text:
- Before calling the embedding model, compute SHA-256 of the text.
- Check `chunk_embedding_cache` table for hash → embedding_id match.
- If found: skip embedding, reuse existing vector.
- If not found: embed and store hash.

### 41.4 No Redis Dependency

The caching layer uses Python `functools.lru_cache` and `cachetools.TTLCache` for in-process caching. No external cache server is required.

---

## 42. Logging Strategy

### 42.1 Logging Framework

`loguru` is used throughout the backend. It provides:
- Structured JSON output for file logs.
- Pretty colored output for console during development.
- Automatic exception trace formatting.
- Zero-dependency rotation.

### 42.2 Log Levels

| Level | Usage |
|-------|-------|
| TRACE | Per-token streaming (disabled by default) |
| DEBUG | Detailed internals, query plans, chunk selections |
| INFO | Request received, service started, document indexed |
| WARNING | Slow query, low OCR confidence, model retry |
| ERROR | API failure, DB write error, file not found |
| CRITICAL | DB corruption, migration failure, startup failure |

### 42.3 Log Files

```
~/.learningos/logs/
├── backend.log          # All INFO+ logs, rotating 10MB, 5 files
├── ingestion.log        # Document processing pipeline logs
├── errors.log           # ERROR+ only, for quick error review
└── access.log           # HTTP access log (Uvicorn)
```

### 42.4 Structured Log Fields

Every log entry includes:
```json
{
  "timestamp": "...",
  "level": "INFO",
  "module": "chat_service",
  "request_id": "uuid",
  "profile_id": "uuid",
  "message": "...",
  "extra": {}
}
```

### 42.5 Frontend Logging

- Frontend errors are logged to browser console only (no file logging).
- Unhandled React errors are caught by an ErrorBoundary and displayed inline.
- API errors are shown via toast notifications.
- Critical errors (backend unreachable) show a full-screen error overlay.

---

## 43. Error Handling

### 43.1 Backend Error Hierarchy

```
LearningOSError (base)
├── ValidationError     (400) — Invalid input
├── NotFoundError       (404) — Resource not found
├── ConflictError       (409) — Duplicate, state conflict
├── StorageError        (500) — DB or FS failure
├── ModelError          (502) — AI provider failure
└── ConfigurationError  (503) — Missing API key, bad config
```

### 43.2 Error Response Format

```json
{
  "data": null,
  "error": {
    "code": "MODEL_UNAVAILABLE",
    "message": "The AI model could not be reached. Check your API key and internet connection.",
    "details": {
      "provider": "openai",
      "model": "gpt-4o",
      "http_status": 503
    }
  }
}
```

### 43.3 Frontend Error Handling

- All API calls wrapped in try/catch with TanStack Query.
- Error states render inline, not modal.
- Streaming errors show partial response + error banner.
- Network offline detected and shown in StatusIndicator.

### 43.4 Background Task Error Handling

- Failed embedding tasks are logged and re-queued (up to 3 retries).
- Failed OCR tasks mark document status as `error` with `error_message`.
- Failed memory extraction does NOT block chat flow (silent failure with log).
- Backup failures trigger WARNING log and UI notification badge.

---

## 44. Security Model

### 44.1 Threat Model

Since the application is local-only, the primary threats are:
1. Another application on the same machine reading local data files.
2. API keys exposed in plaintext.
3. Accidental network exposure if binding settings are misconfigured.

LearningOS is NOT designed to be multi-user or networked. Security measures reflect this scope.

### 44.2 API Key Storage

API keys are stored using Fernet symmetric encryption (`cryptography` library):
- Encryption key is derived from a machine-specific secret (machine UUID + app salt).
- Encrypted blob stored in `config/secrets.enc`.
- Keys are decrypted in-memory only when needed and not retained in Python objects between calls.
- Keys are never written to logs.

### 44.3 Network Binding

The backend binds exclusively to `127.0.0.1` (localhost):
```
uvicorn app.main:app --host 127.0.0.1 --port 8000
```
This prevents other machines on the network from accessing the instance.

### 44.4 File Permissions

On startup, the data directory permissions are set:
- Windows: ACL restricts to current user only.
- Linux/macOS: `chmod 700` on data directory.

### 44.5 Input Sanitization

- All user inputs validated via Pydantic schemas before processing.
- File uploads: MIME type validation, file size limits (default 100 MB per file).
- File paths: normalized and validated to prevent directory traversal attacks.
- No `eval()` or `exec()` anywhere in the codebase.

### 44.6 Dependency Vulnerability Management

- `pip-audit` runs in CI to detect known vulnerabilities in Python dependencies.
- `npm audit` for frontend dependencies.
- Dependencies pinned in `requirements.txt` and `package.json` with exact versions.

---

## 45. Privacy Model

### 45.1 Data Residency

All data — chats, documents, memory, knowledge graph, analytics — is stored exclusively on the user's machine. No telemetry, no analytics, no data is transmitted to LearningOS servers (there are none).

### 45.2 AI Provider Data Policy

When using cloud AI providers (OpenAI, Anthropic):
- Message content is sent to the provider's API for inference.
- Users are shown a clear notice: "Your messages are sent to {provider} for AI processing. Review {provider}'s privacy policy."
- A "Use Local Model (Ollama)" option is prominently displayed for full local operation.

### 45.3 Data Minimization

Metadata included in AI prompts is limited to:
- Relevant memory records (not ALL memory).
- Relevant document chunks (not entire documents).
- Recent chat history (not full history).

No personal identifiers beyond the message content itself are sent to AI APIs.

### 45.4 Data Deletion

Deleting a profile performs:
1. Cascade delete all SQLite rows for that profile.
2. Delete all ChromaDB embeddings with `profile_id` filter.
3. Remove NetworkX graph nodes with `profile_id` attribute.
4. Delete `~/.learningos/data/profiles/{profile_id}/` directory.
5. Write a deletion log entry (no profile content, just the ID and timestamp).

---

## 46. Testing Strategy

### 46.1 Backend Testing

**Unit Tests** (`backend/tests/unit/`):
- Test individual service methods in isolation.
- Mock all dependencies (repositories, model clients, vector store).
- Target: all service methods and pipeline stages.
- Framework: `pytest` + `pytest-asyncio` for async tests.

**Integration Tests** (`backend/tests/integration/`):
- Test service interactions with real SQLite (in-memory) and ChromaDB (in-memory).
- Mock only external AI model calls (using `respx` for HTTP mocking).
- Key flows to test:
  - Full document ingestion pipeline.
  - RAG retrieval pipeline.
  - Chat session create → message → memory extraction.
  - Roadmap generation (Strict mode, no AI needed).

**Contract Tests**:
- Pydantic schemas tested for serialization/deserialization correctness.
- API response shapes validated against schema definitions.

**Test Fixtures**:
- Factory functions for creating test profiles, documents, chats.
- Sample documents included in `tests/fixtures/`.

### 46.2 Frontend Testing

**Component Tests** (`Vitest` + `React Testing Library`):
- Test each component renders correctly with mocked data.
- Test user interactions (click, type, submit).
- Test loading and error states.

**E2E Tests** (`Playwright`):
- Key user journeys tested end-to-end with real backend (test mode).
- Journeys: profile creation, document upload, chat session, quiz completion.

### 46.3 Test Coverage Targets

| Layer | Target Coverage |
|-------|----------------|
| Backend services | 80% |
| Backend routers | 70% |
| Backend pipelines | 75% |
| Frontend components | 60% |
| E2E critical journeys | 100% |

### 46.4 Test Execution

```bash
# Backend
cd backend && pytest --cov=app --cov-report=html

# Frontend
cd frontend && npm test

# E2E
cd frontend && npm run test:e2e
```

---

## 47. CI/CD Strategy

### 47.1 CI Pipeline (GitHub Actions)

Triggered on: every push to `main`, every pull request.

```yaml
stages:
  1. lint (ruff for Python, ESLint for TypeScript)
  2. type-check (mypy for Python, tsc for TypeScript)
  3. unit-tests (pytest, vitest)
  4. integration-tests (pytest integration suite)
  5. build (frontend vite build, backend pyinstaller test)
  6. security-scan (pip-audit, npm audit)
```

### 47.2 Release Workflow

Triggered on: git tag push (`v*`).

```yaml
stages:
  1. full-test-suite
  2. build-windows (PyInstaller + npm build)
  3. build-macos (conditional)
  4. build-linux (conditional)
  5. create-github-release (upload installers)
  6. generate-changelog
```

### 47.3 Branch Strategy

- `main`: Production-ready code only.
- `dev`: Integration branch for feature work.
- `feature/*`: Individual feature branches.
- `hotfix/*`: Critical fixes merged directly to main.

---

## 48. Packaging Strategy

### 48.1 Windows Distribution

**Option A: Self-contained ZIP**
- Include Python runtime (embed distribution).
- Include pre-built frontend static files.
- Include batch scripts for startup.
- User unzips and runs `setup.bat` once, then `start.bat`.
- Size estimate: ~150 MB (before user data).

**Option B: NSIS Installer**
- Professional Windows installer.
- Installs to `%LOCALAPPDATA%\LearningOS\`.
- Creates Start Menu shortcut and Desktop icon.
- Handles Tesseract dependency installation.
- Size estimate: ~200 MB installer.

**Recommended**: Option A for MVP (simpler, no admin rights required). Option B for Phase 2.

### 48.2 Frontend Build

```
cd frontend && npm run build
```
Output in `frontend/dist/`. FastAPI mounts this as static files in production mode.

### 48.3 Backend Packaging

Python virtual environment bundled:
```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

The `start.bat` activates this venv.

**Alternative**: PyInstaller to create a single executable `learningos-backend.exe`. This eliminates Python dependency. Used for Option B installer.

### 48.4 Node.js Dependency

For Option A: Node.js must be installed (detected in `setup.bat`, link provided if missing).
For production static serving: Node.js not required (FastAPI serves the built static files).

---

## 49. Local Deployment Strategy

### 49.1 First-Time Setup (`setup.bat`)

1. Check Python ≥ 3.11 is installed. If not: display download URL and exit.
2. Check Node.js ≥ 20 is installed. If not: display download URL and exit.
3. Check Tesseract is installed. If not: display download URL, offer to continue without OCR.
4. Create Python virtual environment at `backend/.venv`.
5. Install Python dependencies from `requirements.txt`.
6. Install Node.js dependencies: `npm install` in `frontend/`.
7. Build frontend: `npm run build` in `frontend/`.
8. Run database migrations: `alembic upgrade head`.
9. Create default `settings.toml` if not exists.
10. Display "Setup complete. Run start.bat to launch LearningOS."

### 49.2 Standard Launch (`start.bat`)

1. Check if already running (port 8000 check). If so: just open browser.
2. Activate Python venv.
3. Start backend: `uvicorn app.main:app --host 127.0.0.1 --port 8000` (in background).
4. Wait for backend health check to pass (poll `/api/v1/health` every 500ms, timeout 30s).
5. Open browser: `start http://localhost:5173` (or 8000 for production static serving).
6. Display startup log in terminal window.

### 49.3 Update Process

A future `update.bat` script:
1. `git pull` (or download release ZIP).
2. Run `pip install -r requirements.txt` (installs new/updated packages).
3. Run `npm install && npm run build`.
4. Run `alembic upgrade head` (apply new migrations).
5. Start application.

---

## 50. start.bat Behaviour

### 50.1 Complete start.bat Specification

```
File: start.bat
Location: learningos/ (root of repository)
```

**Execution steps in order**:

1. **Title**: Sets terminal window title to "LearningOS".

2. **Admin check**: NOT required. All paths are user-space.

3. **Environment check**: Verify `.venv/` exists. If not: print "Please run setup.bat first." and exit with code 1.

4. **Port conflict check**: Use `netstat -an` to check if port 8000 is occupied. If occupied by another process: print warning and ask user to confirm or abort.

5. **Activate venv**: Call `backend\.venv\Scripts\activate.bat`.

6. **Set environment variables**:
   - `LEARNINGOS_ENV=production`
   - `LEARNINGOS_DATA_DIR=%USERPROFILE%\.learningos`
   - `PYTHONPATH=backend`

7. **Start backend**: Launch `uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level warning` in a new minimized terminal window (`start /min cmd /k`).

8. **Health poll**: Loop calling `curl -s http://127.0.0.1:8000/api/v1/health` every 500ms. Continue when 200 received or after 30s timeout (print error if timeout).

9. **Open browser**: Execute `start http://localhost:8000` (in production mode, FastAPI serves static frontend files on same port).

10. **Status message**: Print "LearningOS is running at http://localhost:8000 — Press Ctrl+C to stop."

11. **Wait**: Keep the main terminal window open. On Ctrl+C: send SIGTERM to backend process and exit cleanly.

### 50.2 Development Mode (`start-dev.bat`)

For developers:
1. Start backend with `--reload` flag.
2. Start frontend Vite dev server: `npm run dev` in `frontend/`.
3. Open browser to `http://localhost:5173`.
4. Both processes run with live-reload.

---

## 51. Future Extension Points

### 51.1 Designed Extension Seams

The following seams are designed into the architecture to allow future extension without major refactoring:

| Extension Point | Mechanism |
|----------------|-----------|
| New AI provider | Implement `BaseModelClient`, register in provider registry |
| New document type | Implement `BaseExtractor`, register in type router |
| New learning mode | Add mode entry to mode registry, implement system prompt variant |
| New roadmap mode | Implement `BaseRoadmapStrategy`, register in strategy factory |
| New node type (graph) | Add to node type enum and visualization color map |
| New quiz question type | Implement `BaseQuestionType`, register in quiz engine |
| New analytics metric | Add computation function, register in analytics dashboard config |
| New export format | Implement `BaseExporter`, register in export service |

### 51.2 Plugin Hook Points

Six plugin hook points are exposed (see Section 52):
1. Pre-prompt hook (modify assembled prompt before sending to AI).
2. Post-response hook (process AI response before storing).
3. Post-ingestion hook (trigger actions after document indexed).
4. Pre-quiz hook (modify generated questions).
5. Post-assessment hook (trigger after quiz scored).
6. Dashboard widget hook (add custom analytics widgets).

---

## 52. Plugin System

### 52.1 Plugin Architecture

Plugins are Python packages placed in `~/.learningos/plugins/`. On startup, the plugin loader:
1. Scans the plugins directory.
2. For each directory with a valid `plugin.toml` manifest, attempts to import.
3. Failed plugin imports are logged and skipped (never crash the main app).
4. Successful plugins are registered in the plugin registry.

### 52.2 Plugin Manifest (`plugin.toml`)

```toml
[plugin]
name = "my-plugin"
version = "1.0.0"
author = "Developer Name"
description = "What this plugin does"
min_learningos_version = "1.0.0"
entry_point = "my_plugin.main:register"
hooks = ["pre_prompt", "post_ingestion"]
```

### 52.3 Hook Interface

```
# Pre-prompt hook
def pre_prompt(context: PromptContext) -> PromptContext:
    # Modify context before AI call
    return modified_context

# Post-response hook
def post_response(response: str, context: PromptContext) -> str:
    # Process response before storing
    return modified_response

# Post-ingestion hook
def post_ingestion(document: DocumentRecord) -> None:
    # Called after a document is fully indexed
    pass
```

### 52.4 Plugin UI Extension

Plugins can register:
- Custom sidebar nav items (pointing to plugin-served HTML pages on a plugin sub-port).
- Custom dashboard widgets (returning JSON data conforming to a widget schema).

---

## 53. Scalability Considerations

### 53.1 Local-First Scalability Limits

This is a single-user local application. Scalability concerns are about handling large personal corpora, not multi-user load:

| Scenario | Expected Limit | Mitigation |
|----------|---------------|-----------|
| Documents | ~500 documents | Pagination in UI, lazy loading |
| Chunks in ChromaDB | ~200,000 | HNSW tuning, profile-scoped collections |
| Chat messages | ~100,000 | FTS5 index, pagination, session archiving |
| Graph nodes | ~5,000 | Level-of-detail rendering, clustering |
| Analytics events | ~1,000,000 | Aggregation tables, time-window queries |

### 53.2 Performance Scaling Strategies

**Document scaling**:
- Embedding is entirely async and background — adding 1,000 documents doesn't block the UI.
- ChromaDB HNSW lookup scales sub-linearly: 100K vectors still < 50ms search.

**Chat scaling**:
- FTS5 full-text index scales to millions of records efficiently.
- Chat history for context uses a sliding window — not affected by total message count.

**Graph scaling**:
- NetworkX in-memory: comfortable with 10,000 nodes, 50,000 edges on modern hardware.
- Beyond that: migrate to a proper local graph DB (see Phase 3: Neo4j Desktop or Kuzu).

### 53.3 Multi-Profile Isolation

All ChromaDB collections are profile-scoped. Profile switching involves no data mixing. Profiles with large corpora don't impact query performance of other profiles.

---

## 54. MVP Scope

### 54.1 MVP Definition

The MVP delivers a usable, complete learning system that demonstrates the core value proposition. It prioritizes correctness and completeness over polish.

### 54.2 MVP Feature Set

✅ **Included**:
- Profile creation and switching (up to 5 profiles).
- Document upload: PDF (text-only), TXT, DOCX.
- Syllabus parsing (AI-based, Strict Mode only).
- Roadmap generation (Strict Mode only).
- Roadmap visualization (list view, not graph).
- AI tutor chat (streaming, all 6 modes).
- RAG with document chunks (document collection only).
- Memory system (extraction + retrieval, no UI editor).
- MCQ quiz generation and scoring.
- Basic analytics: completion %, mastery per topic.
- Settings: API key, model selection (OpenAI only).
- start.bat and setup.bat.
- Dark mode UI.
- Knowledge graph (data model and enrichment, no visualization).

❌ **Deferred to Phase 2**:
- OCR pipeline.
- Adaptive and Hybrid roadmap modes.
- Knowledge graph visualization.
- Assessment (timed exam) mode.
- Memory UI editor.
- Activity heatmap and full analytics dashboard.
- Spaced repetition.
- Export features.
- Plugin system.
- Ollama / Anthropic support.

### 54.3 MVP Success Criteria

A user can:
1. Create a profile.
2. Upload a PDF syllabus.
3. Generate a roadmap.
4. Have a multi-turn tutoring conversation that demonstrates memory of prior exchanges.
5. Take a quiz on a topic.
6. See basic progress statistics.

---

## 55. Phase 2 Scope

Delivered over 6–8 weeks after MVP:

### 55.1 Feature Additions

- **OCR Pipeline**: Full image and image-PDF support with Tesseract.
- **Adaptive and Hybrid Roadmap Modes**: AI-driven roadmap generation.
- **Knowledge Graph Visualization**: Interactive D3.js graph.
- **Memory UI**: Full editor for memory records.
- **Full Analytics Dashboard**: Heatmap, velocity, weakness report, time distribution.
- **Assessment Mode**: Timed exams with formal scoring.
- **Spaced Repetition**: SM-2 algorithm integrated with quiz engine.
- **Ollama Support**: Fully local, offline AI option.
- **Anthropic Support**: Claude models as alternative.
- **Export Features**: Chat export (MD/PDF), profile export (ZIP).
- **Note Generation**: AI-generated notes per topic, editor UI.
- **Multi-format Search**: Search across documents, chats, notes, memory.
- **Roadmap Graph View**: Visualize roadmap as DAG (ReactFlow).
- **Context Panel**: Show retrieved sources per AI response.

### 55.2 Infrastructure Improvements

- Alembic migration for all new tables.
- Reranker integration for RAG quality.
- HyDE retrieval implementation.
- Backup UI and restore functionality.
- Settings: Port configuration, data directory override.

---

## 56. Phase 3 Scope

Delivered over 3–6 months after Phase 2:

### 56.1 Advanced Features

- **Plugin System**: Full plugin loader, manifest system, hook points, UI extension.
- **Light Mode**: Full light/dark theme toggle.
- **Mobile-Responsive UI**: Tablet and mobile viewport support.
- **Windows Installer (NSIS)**: Professional installer with Start Menu integration.
- **macOS and Linux Support**: `.sh` launchers, macOS `.app` bundle.
- **Advanced Knowledge Graph**: Migrate to Kuzu (embedded graph DB) for complex queries.
- **Voice Input**: Speech-to-text for hands-free tutoring.
- **Flashcard System**: Dedicated spaced repetition card UI.
- **Study Planner**: Calendar integration with AI-recommended study schedule.
- **Collaboration Lite**: Read-only profile sharing via exported bundles.
- **Custom Embedding Models**: UI for adding any HuggingFace model.
- **Multi-Language OCR**: Tesseract language pack management.
- **Advanced Assessment**: Adaptive difficulty, full mock exam simulation.
- **API Integration Expand**: Google Gemini, Groq, Cohere support.

### 56.2 Technical Debt

- Replace JSON graph store with Kuzu (embedded graph database).
- Introduce proper task queue (asyncio Queue with priority support).
- Consider SQLite → DuckDB for analytics tables (columnar performance).
- Full test coverage to 85%+.
- Performance profiling and optimization pass.

---

## 57. Development Roadmap

### 57.1 Timeline Overview

```
Week 1–2:   Foundation (repo, config, DB, FastAPI skeleton, start.bat)
Week 3–4:   Profile + Document system + basic ingestion
Week 5–6:   Embedding + ChromaDB + basic RAG
Week 7–8:   Chat system + Tutor Orchestrator (no memory yet)
Week 9–10:  Memory System + Knowledge Graph (data layer)
Week 11–12: Roadmap Engine (Strict Mode) + Quiz Engine (MCQ)
Week 13–14: Analytics (basic) + Frontend foundation
Week 15–16: Frontend: Chat, Roadmap, Documents pages
Week 17–18: Frontend: Quiz, Analytics, Settings pages
Week 19–20: Integration, testing, bug fixes → MVP Release

Phase 2: Weeks 21–36
Phase 3: Months 10–18
```

### 57.2 Team Structure (Reference)

| Role | Responsibilities |
|------|----------------|
| Backend Engineer 1 | Core services, DB schema, migrations |
| Backend Engineer 2 | RAG, embedding, ingestion pipeline |
| Backend Engineer 3 | AI orchestration, model abstraction |
| Frontend Engineer 1 | Chat, roadmap, settings pages |
| Frontend Engineer 2 | Graph, analytics, quiz pages |
| Full-Stack/QA | E2E tests, CI/CD, integration |

---

## 58. Recommended Build Order

The system must be built in dependency order. Each phase below can begin after the previous is verified working.

### Phase A: Foundation

1. Repository structure setup (all directories, git, `.gitignore`).
2. Backend: FastAPI app factory, health endpoint, config loading.
3. Backend: SQLAlchemy setup, Alembic init, first migration (empty schema).
4. Backend: Logging initialization.
5. `start.bat` and `setup.bat` with health check.
6. Frontend: Vite + React + TypeScript init, router, layout skeleton.
7. Frontend: API client, basic health check display.

### Phase B: Profile System

8. DB: `profiles` table migration.
9. Backend: Profile repository, service, router.
10. Frontend: HomePage (profile list), profile creation form.
11. Frontend: Zustand profileStore.

### Phase C: Document System

12. DB: `documents`, `chunk_embedding_queue` tables.
13. Backend: File system utility, file storage strategy.
14. Backend: Text extractors (PDF/DOCX/TXT).
15. Backend: Chunker.
16. Backend: Embedder + ChromaDB init.
17. Backend: IngestionService, document router.
18. Frontend: Documents page, upload dropzone.

### Phase D: RAG + Basic Chat

19. DB: `chat_sessions`, `chat_messages` tables.
20. Backend: RAG Retriever (single-collection).
21. Backend: ContextAssembler (basic, no memory).
22. Backend: Model Abstraction (OpenAI only).
23. Backend: TutorOrchestrator (basic, no memory/graph).
24. Backend: ChatService, WebSocket streaming.
25. Frontend: ChatPage, streaming display, session list.

### Phase E: Memory System

26. DB: `memory_records` table.
27. Backend: ChromaDB memory collection.
28. Backend: MemoryService (extraction + retrieval).
29. Backend: Integrate memory into TutorOrchestrator.

### Phase F: Roadmap Engine

30. DB: `roadmaps`, `roadmap_nodes`, `roadmap_edges` tables.
31. Backend: SyllabusParser.
32. Backend: RoadmapService (Strict Mode).
33. Frontend: RoadmapPage (list view), node status updates.

### Phase G: Knowledge Graph

34. Backend: GraphStore (JSON + NetworkX).
35. Backend: GraphEnricher (async, post-chat).
36. Backend: GraphService, graph router.

### Phase H: Quiz Engine

37. DB: `quiz_attempts` table.
38. Backend: QuizService (MCQ generation, scoring).
39. Backend: Integrate quiz results into memory/mastery.
40. Frontend: QuizPage.

### Phase I: Analytics

41. DB: `analytics_events` table.
42. Backend: AnalyticsService (basic metrics).
43. Frontend: AnalyticsPage (completion %, mastery chart).

### Phase J: Settings + Polish

44. Backend: Settings service, API key encryption.
45. Frontend: SettingsPage.
46. Frontend: Empty states, loading skeletons, error handling.
47. Integration testing, bug fixes.

---

## 59. Risks and Mitigations

### 59.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| Tesseract not installed / wrong path | High | Medium | Auto-detect common paths, provide setup guidance, graceful degradation |
| AI API rate limits during heavy use | Medium | Medium | Exponential backoff, user-visible error messages, queue system |
| ChromaDB version incompatibility | Low | High | Pin exact ChromaDB version, test on multiple Python versions |
| SQLite WAL corruption on force-quit | Low | High | Use SQLite's built-in integrity check on startup |
| Large PDF (500+ pages) causing OOM | Medium | Medium | Stream-based extraction, configurable chunk batch size |
| Context window overflow in large sessions | Medium | Low | Implemented sliding window + token budget management |
| Knowledge graph growing too large for NetworkX | Low | Medium | Monitor node count, alert user at 3,000 nodes, plan Kuzu migration |
| PyInstaller build failures on Windows | Medium | High | Test PyInstaller in CI on every commit, maintain fallback ZIP distribution |

### 59.2 Product Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| Users confused by three roadmap modes | Medium | Medium | Mode selector with clear descriptions and tooltips |
| Memory extraction extracting incorrect facts | Medium | Medium | Confidence scores, user review UI, easy deletion |
| Quiz questions too easy or irrelevant | Medium | High | Allow user to rate/flag questions, refine extraction prompt |
| First-time setup too complex | High | High | Detailed setup guide, `setup.bat` handles all steps, validation messages |
| AI responses not using uploaded documents | Low | High | Citation tracker shows which docs used; debug mode shows retrieved chunks |

### 59.3 Dependency Risks

| Dependency | Risk | Mitigation |
|-----------|------|-----------|
| OpenAI API pricing changes | High | Ollama local fallback supported |
| ChromaDB API changes | Low | Abstracted behind repository layer |
| PyMuPDF license changes | Low | Monitor; can switch to `pypdf2` as fallback |
| NetworkX performance at scale | Medium | Plan migration path to Kuzu in Phase 3 |

---

## 60. Exact Implementation Sequence

This is the precise ordered list of implementation tasks for coding agents. Each task is atomic and independently verifiable.

### 60.1 Task List (Ordered)

**TASK-001**: Create repository root structure. Initialize git. Create `.gitignore` for Python + Node + OS files. Create `README.md` with project description.

**TASK-002**: Create `backend/` Python project structure. Create `pyproject.toml` with project metadata. Create `requirements.txt` and `requirements-dev.txt` with all pinned dependencies.

**TASK-003**: Create `backend/app/main.py` — FastAPI app factory with lifespan manager, CORS middleware, and request ID middleware.

**TASK-004**: Create `backend/app/config.py` — Load `settings.toml` from data directory. Define `Settings` Pydantic model. Implement singleton pattern.

**TASK-005**: Create `backend/app/routers/health.py` — GET `/api/v1/health` returning version, status, data directory size. Mount on app.

**TASK-006**: Create `backend/app/db/database.py` — Async SQLAlchemy engine, session factory, `get_db()` dependency.

**TASK-007**: Initialize Alembic. Create `alembic.ini` and `alembic/env.py`. Configure to use async SQLAlchemy.

**TASK-008**: Create `backend/app/db/models.py` — Define all SQLAlchemy ORM models for: Profile, Document, ChatSession, ChatMessage, RoadmapNode, RoadmapEdge, Roadmap, MemoryRecord, QuizAttempt, AnalyticsEvent, Note. Each model maps exactly to the table schema in Section 11.

**TASK-009**: Create Alembic migration `001_initial_schema.py` — Creates all tables from TASK-008.

**TASK-010**: Create `backend/app/utils/id_utils.py` — UUID generation utility. Create `backend/app/utils/date_utils.py` — UTC datetime utilities. Create `backend/app/utils/file_utils.py` — Path handling, safe file write, hash computation.

**TASK-011**: Create `backend/app/security/keystore.py` — Fernet-based API key encryption/decryption. Key derivation from machine UUID.

**TASK-012**: Create `backend/app/db/repositories/profile_repo.py` — CRUD for Profile ORM model. Create `backend/app/services/profile_service.py` — Business logic wrapping repo. Create `backend/app/routers/profiles.py` — All profile endpoints.

**TASK-013**: Create `backend/app/db/repositories/document_repo.py`. Create `backend/app/utils/text_utils.py` — Text cleaning utilities. Create `backend/app/pipelines/document_extractor.py` — PDF, DOCX, TXT extractors.

**TASK-014**: Create `backend/app/pipelines/ocr_pipeline.py` — Tesseract-based OCR with pre-processing steps. Create Tesseract path detection utility.

**TASK-015**: Create `backend/app/pipelines/chunker.py` — Sliding window chunker with overlap, sentence-boundary snapping, metadata attachment.

**TASK-016**: Create `backend/app/pipelines/embedder.py` — Batch embedding with retry. Write to ChromaDB. Create `backend/app/db/repositories/embedding_repo.py` — Chunk embedding queue management.

**TASK-017**: Create `backend/app/services/ingestion_service.py` — Orchestrates document upload: save file, extract text, chunk, queue embeddings. Create `backend/app/routers/documents.py`.

**TASK-018**: Create `backend/app/tasks/scheduler.py` — APScheduler setup. Register embedding task. Create `backend/app/tasks/embedding_task.py` — Process embedding queue in batches.

**TASK-019**: Create `backend/app/models/abstraction.py` — `BaseModelClient` abstract class. Create `backend/app/models/openai_client.py` — OpenAI implementation. Register in provider factory.

**TASK-020**: Create `backend/app/rag/retriever.py` — ChromaDB similarity search, multi-collection parallel query. Create `backend/app/rag/context_assembler.py` — Format retrieved chunks.

**TASK-021**: Create `backend/app/rag/reranker.py` — Cross-encoder reranking. Implement MMR diversification.

**TASK-022**: Create `backend/app/rag/citation_tracker.py` — Map response text to source chunks.

**TASK-023**: Create `backend/app/db/repositories/chat_repo.py`. Create `backend/app/services/chat_service.py` — Session management, message persistence. Create `backend/app/routers/chat.py` — REST endpoints + WebSocket endpoint.

**TASK-024**: Create `backend/app/services/tutor_orchestrator.py` — Full context assembly: profile, roadmap, memory (stubbed for now), RAG, chat history. Mode-specific system prompts. Token budget management.

**TASK-025**: Create `backend/app/graph/graph_store.py` — NetworkX load/save. Create `backend/app/graph/graph_query.py` — All graph query functions. Create `backend/app/graph/graph_enricher.py` — Concept extraction from AI.

**TASK-026**: Create `backend/app/services/graph_service.py`. Create `backend/app/routers/graph.py`.

**TASK-027**: Create `backend/app/db/repositories/memory_repo.py`. Create `backend/app/services/memory_service.py` — Extraction, deduplication, retrieval. Integrate memory retrieval into TutorOrchestrator. Create `backend/app/tasks/memory_extraction_task.py`.

**TASK-028**: Create `backend/app/pipelines/syllabus_parser.py` — AI-based structure extraction. Create `backend/app/db/repositories/roadmap_repo.py`. Create `backend/app/services/roadmap_service.py` — Strict mode generation, node state machine. Create `backend/app/routers/roadmap.py`.

**TASK-029**: Create `backend/app/db/repositories/quiz_repo.py`. Create `backend/app/services/quiz_service.py` — Question generation, answer evaluation, mastery update. Create `backend/app/routers/quiz.py`.

**TASK-030**: Create `backend/app/db/repositories/analytics_repo.py`. Create `backend/app/services/analytics_service.py` — All metric computations. Create `backend/app/routers/analytics.py`.

**TASK-031**: Create `backend/app/models/ollama_client.py`. Create `backend/app/models/anthropic_client.py`. Register both in provider factory.

**TASK-032**: Create `backend/app/routers/settings.py`. Create `backend/app/services/settings_service.py` — Config read/write, API key management.

**TASK-033**: Create `backend/app/tasks/backup_task.py` — Daily SQLite backup, rotation. Register in scheduler.

**TASK-034**: Create `backend/app/lifespan.py` — Full startup sequence: config load, DB migration, ChromaDB init, graph load, scheduler start.

**TASK-035**: Create `frontend/` project. Initialize Vite + React + TypeScript. Install all frontend dependencies.

**TASK-036**: Create `frontend/src/styles/tokens.css` — All CSS custom properties (colors, spacing, typography, radii). Create `frontend/src/styles/globals.css` — Reset, base styles, font imports.

**TASK-037**: Create `frontend/src/api/client.ts` — Axios instance with base URL, error handling, response envelope unwrapping. Create all `frontend/src/api/*.ts` files for each service.

**TASK-038**: Create `frontend/src/stores/` — All Zustand stores as specified in Section 35.

**TASK-039**: Create `frontend/src/components/layout/` — Sidebar, TopBar, Layout wrapper, NavigationMenu, ProfileSwitcher, StatusIndicator.

**TASK-040**: Create `frontend/src/pages/HomePage.tsx` — Profile grid, create profile form.

**TASK-041**: Create `frontend/src/pages/SetupPage.tsx` — API key entry, model selection, first-time flow.

**TASK-042**: Create `frontend/src/hooks/useStreaming.ts` — WebSocket management hook. Create `frontend/src/pages/ChatPage.tsx` — Full chat interface with streaming.

**TASK-043**: Create `frontend/src/pages/DashboardPage.tsx` — Profile overview, quick stats.

**TASK-044**: Create `frontend/src/pages/DocumentsPage.tsx` — Dropzone, document list, status indicators.

**TASK-045**: Create `frontend/src/pages/RoadmapPage.tsx` — List view initially. Node cards with status.

**TASK-046**: Create `frontend/src/pages/QuizPage.tsx` — Quiz setup, question card, results.

**TASK-047**: Create `frontend/src/pages/AnalyticsPage.tsx` — Progress ring, mastery chart, weakness list.

**TASK-048**: Create `frontend/src/pages/MemoryPage.tsx` — Memory record list, category filter.

**TASK-049**: Create `frontend/src/pages/SettingsPage.tsx` — Full settings form, API key management, model selection.

**TASK-050**: Create `frontend/src/pages/GraphPage.tsx` — D3.js force-directed graph canvas, filter panel, node detail sidebar.

**TASK-051**: Implement ReactFlow roadmap visualization in `RoadmapPage.tsx` — DAG view as alternative to list view.

**TASK-052**: Add FTS5 virtual tables migration for `chat_messages`, `memory_records`, `notes`. Implement search endpoints and frontend search UI.

**TASK-053**: Implement Hybrid and Adaptive roadmap generation in `roadmap_service.py`.

**TASK-054**: Implement full timed Assessment Mode in `quiz_service.py` and `QuizPage.tsx`.

**TASK-055**: Implement spaced repetition scheduler (SM-2) in `quiz_service.py`.

**TASK-056**: Implement all export features: chat export (MD/PDF), profile export (ZIP).

**TASK-057**: Write all unit tests for backend services. Write integration tests for key flows.

**TASK-058**: Write Playwright E2E tests for: profile creation, document upload, chat, quiz.

**TASK-059**: Set up GitHub Actions CI pipeline per Section 47.

**TASK-060**: Create `setup.bat`, `start.bat`, `start-dev.bat`, `start.sh`, `setup.sh` with all behavior specified in Section 50.

**TASK-061**: Create `setup.bat` validation: Python version check, Node.js check, Tesseract check, venv creation, dependency installation, DB migration execution.

**TASK-062**: Final integration test: run full system from `start.bat`, verify all MVP features work end-to-end.

**TASK-063**: Performance profiling: measure RAG latency, DB query times, graph rendering fps. Document results and apply optimizations.

**TASK-064**: Security review: verify API keys not in logs, backend bound to localhost only, file upload MIME validation, path traversal prevention.

**TASK-065**: Create release package: build frontend, package backend venv, create distribution ZIP, test on clean Windows 10 machine.

---

## Appendix A: Configuration File Reference

### settings.toml Default Values

```toml
[app]
name = "LearningOS"
version = "1.0.0"
environment = "production"  # development | production
data_dir = ""  # Empty = default (~/.learningos)

[server]
host = "127.0.0.1"
port = 8000
log_level = "warning"  # trace | debug | info | warning | error

[model]
provider = "openai"  # openai | anthropic | ollama
chat_model = "gpt-4o"
embedding_model = "text-embedding-3-small"
temperature = 0.7
max_tokens = 4096
context_window = 128000

[ollama]
base_url = "http://localhost:11434"
chat_model = "llama3"
embedding_model = "nomic-embed-text"

[ingestion]
chunk_size = 512
chunk_overlap = 64
embedding_batch_size = 100
max_file_size_mb = 100
ocr_language = "eng"
ocr_confidence_threshold = 40

[rag]
top_k_documents = 10
top_k_memory = 5
top_k_reranked = 8
use_hyde = true
mmr_lambda = 0.7

[memory]
max_memory_in_prompt = 5
confidence_decay_rate = 0.05
decay_interval_days = 7

[backup]
enabled = true
interval_hours = 24
max_backups = 7

[quiz]
default_question_count = 10
spaced_repetition_enabled = true
```

---

## Appendix B: Data Flow Abbreviation Key

| Abbreviation | Meaning |
|-------------|---------|
| PID | Profile ID |
| SID | Session ID |
| NID | Node ID |
| DID | Document ID |
| MID | Memory Record ID |
| QID | Quiz Attempt ID |
| HyDE | Hypothetical Document Embedding |
| MMR | Maximal Marginal Relevance |
| FTS5 | SQLite Full-Text Search version 5 |
| WAL | Write-Ahead Logging (SQLite mode) |
| SM-2 | SuperMemo 2 spaced repetition algorithm |
| IRT | Item Response Theory |
| ACL | Access Control List |
| HNSW | Hierarchical Navigable Small World (ANN index) |

---

## Appendix C: Glossary

| Term | Definition |
|------|-----------|
| **Profile** | An isolated learning context representing one subject, exam goal, or learning domain |
| **Roadmap** | A structured sequence of topics derived from a syllabus or AI generation |
| **Roadmap Node** | A single topic, chapter, or concept in the roadmap |
| **Memory Record** | A persistent fact, observation, or assessment result stored about the learner |
| **Chunk** | A fixed-size segment of document text prepared for embedding |
| **Embedding** | A high-dimensional vector representation of text used for semantic search |
| **RAG** | Retrieval-Augmented Generation: the technique of injecting retrieved document content into AI prompts |
| **Knowledge Graph** | A network of concepts and their relationships, maintained automatically as the user learns |
| **Mastery Score** | A 0.0–1.0 score representing the learner's demonstrated understanding of a topic |
| **Learning Mode** | A behavioral configuration for the AI tutor (Deep, Revision, Summary, Quiz, Assessment, General) |
| **HyDE** | Hypothetical Document Embedding: generating a hypothetical answer to improve retrieval |
| **Orchestrator** | The system component that assembles context and coordinates all services to produce an AI response |

---

*End of LearningOS Implementation Specification v1.0.0*

*This document is the single source of truth for the LearningOS system. All implementation decisions must align with this specification. Deviations must be documented as amendments with rationale.*
