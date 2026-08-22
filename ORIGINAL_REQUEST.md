# Original User Request

## Initial Request — 2026-08-19T15:42:20Z

Fix all identified bugs and add targeted improvements to the AI TUTOR (LearningOS) application — a full-stack learning platform with a Python/FastAPI backend and React/TypeScript/Vite frontend. The application has several critical bugs that make AI model configuration, document upload, and chat messaging non-functional. There are also secondary bugs and missing features that degrade the user experience.

Working directory: d:\AI TUTOR\LearningOS
Integrity mode: demo

## Codebase Overview

- **Backend**: Python 3 / FastAPI, SQLite (via SQLAlchemy + Alembic), ChromaDB for vector storage, raw `httpx.AsyncClient` for AI provider calls (no vendor SDKs). Entry point: `backend/app/main.py`.
- **Frontend**: React 18 / TypeScript / Vite, Zustand stores, React Query, Tailwind CSS. Entry point: `frontend/src/main.tsx`.
- **Config**: `.env` at repo root for env vars. Encrypted keystore at `~/.learningos/config/secrets.enc`. Settings cached via `@lru_cache` in `backend/app/config.py`.

## Requirements

### R1. Fix the stale `@lru_cache` settings cache — the root cause of most failures

`backend/app/config.py` line ~175 defines `get_settings()` with `@lru_cache(maxsize=1)`. When `SettingsService.set_provider()` (in `backend/app/services/settings_service.py`) updates `os.environ` and `.env`, it never calls `get_settings.cache_clear()`. This causes:
- The frontend settings page to revert to the old provider after saving (because `GET /api/v1/settings/providers` returns cached stale data).
- All backend services to keep using the old provider/model until server restart.
- `SettingsService.delete_api_key()` also needs cache clearing.

### R2. Fix `AssembledContext.context_text` AttributeError — RAG context silently dropped

In `backend/app/routers/ws_chat.py` (line ~113) and `backend/app/services/unified_context_service.py` (line ~185), code accesses `assembled.context_text`. But `backend/app/rag/context_assembler.py` defines `AssembledContext` with `context_block`, not `context_text`. The `AttributeError` is caught by a broad `try...except`, logged as a warning, and `rag_text` defaults to `""` — meaning all RAG document context is silently skipped in chat. Fix all references to use `context_block`.

### R3. Fix embeddings hardcoded to OpenAI — document processing fails for non-OpenAI providers

`backend/app/pipelines/embedder.py` (lines ~195-213) always resolves `OPENAI_API_KEY` and calls `https://api.openai.com/v1/embeddings` regardless of the configured provider. When a user configures Gemini or Groq, this either sends the wrong API key to OpenAI (401 error) or falls back to pseudo-random deterministic vectors. The embedder should resolve the correct embedding endpoint and API key for the active provider, or at minimum use a provider-appropriate embedding API.

### R4. Fix `test_connection` endpoint ignoring the provider parameter

`backend/app/services/settings_service.py` `test_connection(provider)` receives a `provider` argument but calls `get_model_client(self.settings)` which uses `self.settings.model.provider` (the cached/default one) instead of the passed provider. It should test the specified provider. Additionally, it calls `client.get_model_info()` which no client implements.

### R5. Fix `SyllabusService` attribute and method signature mismatches

In `backend/app/services/syllabus_service.py` (lines ~63-68):
- Accesses `document.storage_path`, but the ORM model `Document` defines `file_path`.
- Calls `self.extractor.extract(raw_bytes, document.filename)`, but `DocumentExtractor.extract` expects `(file_path: Path, file_type: str)`.

### R6. Fix frontend WebSocket handler dropping citations

`frontend/src/stores/chatStore.ts` `ws.onmessage` does not handle `type === "citations"` messages sent by the backend (`backend/app/routers/ws_chat.py`). Add handling for citation messages so they are stored and can be displayed in the chat UI.

### R7. Fix inconsistent axios base URL handling

`frontend/src/api/chat.ts`, `documents.ts`, `profiles.ts`, `analytics.ts`, `graph.ts`, `memory.ts`, `notes.ts`, `quiz.ts`, `roadmap.ts`, and `frontend/src/pages/SettingsPage.tsx` all create separate `axios.create({ baseURL: "/api/v1" })` instances instead of using the shared client from `frontend/src/api/client.ts` (which respects `VITE_API_BASE_URL`). Consolidate to use the shared client.

### R8. Add model catalog dropdown to Settings UI

The backend already provides `GET /api/v1/settings/models?provider=...` with a full `PROVIDER_MODEL_CATALOG` for all providers, but `frontend/src/pages/SettingsPage.tsx` only shows a plain text input for model name. Replace it with a dropdown/select that fetches available models for the selected provider, while still allowing custom model name input.

### R9. Add syllabus toggle to document upload and fix minor UI issues

- `frontend/src/pages/DocumentsPage.tsx` hardcodes `is_syllabus: "false"` during upload. Add a checkbox/toggle to let users mark a document as syllabus.
- Several `EmptyState` action handlers use `window.location.href` instead of React Router's `useNavigate()`, causing full page reloads. Fix these.
- `frontend/src/pages/ChatPage.tsx` doesn't read the `:sessionId` URL parameter or `?topic` query param defined in the router. Fix to support deep-linking.

## Acceptance Criteria

### Critical Fixes (R1-R3)
- [ ] After configuring a new provider and API key in Settings, `GET /api/v1/settings/providers` returns the newly configured provider as `active_provider` without requiring a server restart.
- [ ] The Settings UI shows the newly selected provider as active immediately after saving, with the green "Configured" badge.
- [ ] When using a non-OpenAI provider (e.g., Gemini), sending a chat message does NOT produce an OpenAI API key error.
- [ ] RAG context from uploaded documents appears in chat responses (not silently dropped). Verify by uploading a document with known content, asking a question about it, and confirming the response references that content.
- [ ] Document embedding uses the correct provider's embedding endpoint, or gracefully handles providers without embedding APIs (e.g., by using a configured embedding model or clearly informing the user).

### Secondary Fixes (R4-R7)
- [ ] `POST /api/v1/settings/test-connection` with a specific provider tests that provider (not the cached default), and returns a meaningful success/failure result.
- [ ] Syllabus service can access document file paths and call the extractor without `AttributeError` or `TypeError`.
- [ ] WebSocket chat citations from the backend are received and stored on the frontend (not silently dropped).
- [ ] All frontend API modules use the shared axios client from `api/client.ts`, respecting `VITE_API_BASE_URL`.

### Improvements (R8-R9)
- [ ] The Settings page shows a dropdown of available models for the selected provider (fetched from the backend catalog endpoint), with an option to enter a custom model name.
- [ ] Document upload UI includes a toggle to mark a document as a syllabus.
- [ ] Navigation from EmptyState components uses React Router (no full-page reloads).
- [ ] ChatPage reads `:sessionId` from URL params and opens the corresponding session on mount.

### General
- [ ] No new TypeScript or Python type errors introduced.
- [ ] Existing functionality (profile management, chat sessions, document listing) continues to work correctly.
- [ ] All changes pass any existing tests (`pytest` for backend, if tests exist).

## Verification Plan

For each critical fix, run this sequence:
1. Start the backend server (`uvicorn app.main:app`).
2. Open the frontend.
3. Go to Settings → select a provider (e.g., Gemini) → enter an API key → click Save.
4. Verify the UI shows Gemini as the active configured provider without reverting.
5. Reload the page — verify Gemini is still shown as active.
6. Upload a document (PDF or TXT) → verify it processes without OpenAI errors.
7. Open Chat → send a message → verify response comes back from the correct provider without errors.
8. Ask about content from the uploaded document → verify RAG context is included in the response.

For secondary fixes, verify each acceptance criterion individually by exercising the relevant endpoint or UI flow.
