# LearningOS

LearningOS is a local-first AI tutoring and learning workspace.

## Implementation Status

Milestones 01-08 (see `docs/14_DEVELOPMENT_ROADMAP.md`) are implemented:

* **01-03**: Repository skeleton, config/env system, async SQLite + Alembic migrations, repository pattern.
* **04**: Profile system (create/rename/delete/switch; JEE, GATE, Semester Study, Custom Learning).
* **05-07**: Chat sessions/messages, a multi-provider AI abstraction (OpenAI-compatible, Anthropic, Gemini, Ollama), and streaming AI chat over WebSocket with persisted history.
* **08**: Document upload (PDF/DOCX/TXT/image) with local storage, per-profile deduplication, and text extraction.
* **09**: OCR pipeline (Tesseract) for images and scanned/image PDFs with pre/post-processing and confidence scoring, degrading gracefully to `pending_ocr` when Tesseract is missing.

Everything from Milestone 10 onward (embeddings/RAG, memory, roadmap, knowledge graph, quiz, analytics, notes) is still scaffolded as placeholder modules, matching `docs/02_REPOSITORY_STRUCTURE.md`, but not yet implemented.

## Quick Start

### Windows
```bat
setup.bat
start-dev.bat
```

### macOS / Linux
```bash
./setup.sh
./start.sh
```

## Local URLs

* Frontend dev server: `http://127.0.0.1:5173`
* Backend API: `http://127.0.0.1:8000/api/v1`
* Backend health: `http://127.0.0.1:8000/api/v1/health`

## Data Directory

Runtime data is stored outside this repository by default:

```text
~/.learningos/
```

The in-repository `profiles/` folder is only a placeholder required by the project structure and must not contain real user data.

## Documentation

The complete implementation documentation lives in `docs/`. Coding agents should read `docs/20_AGENT_GUIDE.md` first.
