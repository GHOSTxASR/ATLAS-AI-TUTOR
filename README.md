# Atlas

**A personal AI learning platform that runs entirely on your machine.**

Atlas turns your own study material into a tutor. Upload your notes and
textbooks, and it builds a searchable knowledge base, generates a roadmap,
quizzes you on weak spots, and remembers what you struggle with — all stored
locally. Your documents, notes, progress and API keys never leave your machine.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Screenshots

|  |  |
| --- | --- |
| ![Landing page — choose a profile](docs/screenshots/landing.png)<br>**Landing** — pick a profile or create one | ![Dashboard](docs/screenshots/dashboard.png)<br>**Dashboard** — progress, streaks and weak spots |
| ![AI tutor with citations](docs/screenshots/tutor.png)<br>**AI Tutor** — answers grounded in your own material | ![Curriculum roadmap](docs/screenshots/roadmap.png)<br>**Roadmap** — a topic DAG built from your syllabus |
| ![Knowledge graph](docs/screenshots/graph.png)<br>**Knowledge graph** — concepts and how they connect | ![Settings](docs/screenshots/settings.png)<br>**Settings** — providers, keys, and appearance |

---

## Features

| Area | What it does |
| --- | --- |
| **AI Tutor** | Streaming chat with Socratic, Teaching, Revision and Summary modes, grounded in your own material. |
| **Library** | Upload PDF / DOCX / TXT / images. Text extraction with optional Tesseract OCR for scans. |
| **Retrieval (RAG)** | Documents are chunked and embedded into a local ChromaDB index and cited in answers. |
| **Roadmap** | Generates a topic DAG from an uploaded syllabus and tracks unlock/progress state. |
| **Knowledge Graph** | Concepts and their relationships, extracted as you study. |
| **Quizzes** | Auto-generated questions with scoring, feeding back into mastery tracking. |
| **Notes** | AI-generated and hand-written notes, with full markdown, GFM and LaTeX rendering. |
| **Memory** | Long-term learner memory with decay, so the tutor adapts to you over time. |
| **Analytics** | Study time, streaks, mastery and weak-spot detection. |
| **Profiles** | Multiple learners or tracks (JEE, GATE, Semester Study, Custom), each with isolated vectors and memory. |

### Supported model providers

Chat works with **Gemini, OpenAI, Anthropic, Groq, DeepSeek, Mistral,
OpenRouter, Together** and **Ollama** (fully local, no key required).

Model lists are fetched **live** from whichever provider you configure, so new
and free models show up as soon as the provider publishes them — nothing is
hardcoded. Any model id can also be typed in by hand.

**Chat and embeddings are configured separately.** Not every chat provider
offers an embeddings API — Anthropic, Groq, DeepSeek and OpenRouter do not — but
that no longer constrains your chat model. Pick any provider for chat, and one
of OpenAI, Gemini, Mistral, Together or a local Ollama model for embeddings.

**Embeddings need no API key at all.** By default Atlas embeds on your own
machine with a small ONNX model (`BAAI/bge-small-en-v1.5`, ~130 MB, fetched
once on first use). So document upload, semantic search and the knowledge graph
work on a fresh clone before you have configured anything — and they keep
working if you pick a chat provider that has no embeddings API of its own. Set
an embedding provider explicitly in Settings to override it.

---

## Requirements

* **Python 3.11+**
* **Node.js 18+**
* *(optional)* [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) — only for scanned documents
* *(optional)* [Ollama](https://ollama.com) — to run models locally with no API key

## Quick Start

### Windows

```bat
install.bat
```

Then launch it:

```bat
start.bat
```

### macOS / Linux

```bash
./setup.sh
./start.sh
```

Atlas is then available at **<http://127.0.0.1:8000>**.

On first run you will be asked to create a learner profile. Document upload and
search work immediately — embeddings run locally and need no key. For the AI
tutor, quizzes and roadmap generation you need a chat model: open **Settings**
and paste an API key (encrypted at rest before being written to disk), or point
Atlas at a local Ollama model, which needs no key either.

## Local URLs

| | |
| --- | --- |
| App (production build) | `http://127.0.0.1:8000` |
| Backend API | `http://127.0.0.1:8000/api/v1` |
| Health check | `http://127.0.0.1:8000/api/v1/health` |
| Frontend dev server | `http://127.0.0.1:5173` |

## Data & Privacy

Everything lives outside this repository, under:

```text
~/.atlas/
├── config/       settings.toml
├── data/         sqlite database, chroma vectors, graph, uploaded files
├── logs/
└── backups/
```

API keys are encrypted with Fernet (AES-128-CBC + HMAC-SHA256) into
`config/secrets.enc`, with the key file permission-restricted to your user
account. Keys are redacted from logs and error messages, and are never included
in request URLs.

The only network calls Atlas makes are to the model provider you configure.

> The in-repository `profiles/` folder is a structural placeholder and must not
> contain real user data.

---

## Development

```bash
# Backend
cd backend
python -m venv .venv
.venv/Scripts/activate          # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r requirements-dev.txt   # includes runtime deps + test tooling

pytest                          # 206 tests
ruff check app/ evals/ alembic/
python -m evals.run             # retrieval + syllabus scorecards (no API key)

# Frontend
cd frontend
npm install
npm test                        # vitest
npm run typecheck               # tsc --noEmit
npm run dev                     # vite dev server on :5173
```

### Evals

Tests prove the AI parts *run*. Evals measure whether they *work* — the failures
that mattered here never raised. The memory extractor returned nothing for
weeks; syllabus parsing silently degraded to a heuristic that turned page
footers into topics; short answers were graded on keyword overlap. Each one
looked healthy from the outside.

```bash
python -m evals.run             # scorecards
pytest app/tests/evals          # the same numbers, as pass/fail thresholds
```

Retrieval is measured through the real vector store and retriever with
precision/recall/MRR/NDCG over a golden set of student-phrased questions;
syllabus parsing is scored on structure recall *and* precision, the latter
because page furniture reaching the roadmap is invisible to recall. Both embed
locally, so neither needs an API key and both run in CI on every push.

See [backend/evals/README.md](backend/evals/README.md).

`requirements.txt` holds runtime dependencies only. Use
**`requirements-dev.txt`** (which includes it) when working on the project —
`pytest` and `ruff` are not installed by `install.bat`.

Configuration is read from `~/.atlas/config/settings.toml`, overridable with
`ATLAS_*` environment variables — see [.env.example](.env.example). Copy it to
`.env` for local overrides.

See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request, and
[SECURITY.md](SECURITY.md) to report a vulnerability.

## Documentation

Design and implementation notes live in [`docs/`](docs/).

## License

[MIT](LICENSE) © Atlas contributors
