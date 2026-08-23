# 15. Implementation Coverage Audit

## 1. Purpose
This file records the coverage check between `00_IMPLEMENTATION_PLAN.md` and the split build documents. It also captures cross-cutting implementation details that were present in the master plan but did not have a dedicated specialist file.

Use this file as the checklist before assigning work to coding agents.

## 2. Source-of-Truth Rule
*   `00_IMPLEMENTATION_PLAN.md` is the full source of truth.
*   `01_*` through `15_*` are build-facing working references.
*   If a split document and the master plan disagree, follow the master plan first, then update the split document.
*   A feature is not complete until code, tests, and the relevant split document all agree.

## 3. Coverage Matrix
| Master Plan Sections | Primary Split Doc | Coverage Status |
| :--- | :--- | :--- |
| Product vision, user stories, functional requirements | `00_IMPLEMENTATION_PLAN.md`, this file | Keep master as canonical; no separate PRD file yet. |
| Architecture, high-level design, lifecycles | `01_ARCHITECTURE.md` | Expanded with build contracts. |
| Repository structure, file layout | `02_REPOSITORY_STRUCTURE.md` | Expanded with required files. |
| Database, persistence, migrations | `03_DATABASE_DESIGN.md` | Expanded with missing tables/fields. |
| API design, WebSocket protocol | `04_API_SPECIFICATION.md` | Expanded with payload schemas and error mapping. |
| Frontend architecture and state management | `05_FRONTEND_ARCHITECTURE.md` | Expanded with state ownership and page criteria. |
| UI/UX behavior, visual system, page acceptance | `15_UI_UX_SPEC.md` | Dedicated specialist doc added. |
| Backend, services, errors, tasks | `06_BACKEND_ARCHITECTURE.md` | Expanded with service method minimums and transactions. |
| RAG, retrieval | `07_RAG_ARCHITECTURE.md` | Expanded with result shape and fallbacks. |
| Memory | `08_MEMORY_SYSTEM.md` | Expanded with full field set and retrieval rules. |
| Knowledge graph | `09_KNOWLEDGE_GRAPH.md` | Expanded with merge/persistence rules. |
| Document and syllabus processing | `10_DOCUMENT_PROCESSING.md`, `11_ROADMAP_ENGINE.md` | Expanded with parser/output/status contracts. |
| Roadmaps | `11_ROADMAP_ENGINE.md` | Expanded with mode-specific rules. |
| AI tutor and chat orchestration | `12_AI_TUTOR_ENGINE.md` | Expanded with orchestration and streaming persistence. |
| Model provider integration | `18_MODEL_INTEGRATION.md` | Dedicated specialist doc added. |
| Vector database design | `19_VECTOR_DATABASE_DESIGN.md` | Dedicated specialist doc added. |
| Deployment, packaging, scripts | `13_DEPLOYMENT.md` | Expanded with config and script checks. |
| Build order, phases, risks | `14_DEVELOPMENT_ROADMAP.md` | Expanded with tasks 016-065 and phase gates. |
| Testing strategy | `16_TESTING_STRATEGY.md` | Dedicated specialist doc added. |
| Security and privacy | `17_SECURITY_AND_PRIVACY.md` | Dedicated specialist doc added. |
| Analytics, profile details, quiz, notes, plugin hooks | This file | Captured below until dedicated docs exist. |

## 4. Profile System Contract

### Profile Responsibilities
Profiles isolate all learning data. Every profile-scoped record must carry `profile_id` directly or indirectly.

Profile-owned domains:
*   Documents and extracted text.
*   ChromaDB document, memory, note, and chat-summary collections.
*   Chat sessions and messages.
*   Roadmaps, nodes, and edges.
*   Memory records.
*   Notes.
*   Quiz attempts.
*   Analytics events.
*   Knowledge graph nodes/edges, if using a shared graph file.

### Profile Create Flow
1. Validate `name` and `profile_type`.
2. Create SQLite `profiles` row.
3. Create profile directory under `~/.atlas/profiles/{profile_id}/`.
4. Ensure document subdirectories exist.
5. Initialize profile-scoped ChromaDB collections lazily on first use.
6. Return `ProfileResponse`.

> **As implemented.** The `profiles` table holds `name` and `profile_type`
> only. There is no `is_active`, `goal` or `mode` column, and no server-side
> notion of a "current" profile — earlier drafts of this document described
> those as if they existed. Adding them is optional future work, not a
> regression.

### Profile Switch Flow
Switching is entirely client-side: the frontend stores `activeProfileId` in
`profileStore` (persisted to localStorage) and passes it as a path parameter on
every profile-scoped request. The server holds no active-profile state, so
there is nothing to toggle and no cross-client synchronisation.

### Profile Delete Flow
Deletion is destructive and must require explicit user confirmation in the UI.
1. Stop or ignore queued background jobs for the profile.
2. Drop profile-scoped ChromaDB collections.
3. Remove profile nodes/edges from graph storage.
4. Delete profile files from `~/.atlas/profiles/{profile_id}/`.
5. Delete SQLite rows through cascades or explicit repository calls.
6. If deleted profile was active, set another profile active or return to setup.

### Profile Export Contents
Profile export ZIP must include:
*   `profile.json`
*   `documents/raw/`
*   `documents/extracted/`
*   `chats.json`
*   `roadmaps.json`
*   `memories.json`
*   `notes.json`
*   `quiz_attempts.json`
*   `analytics_events.json`
*   `knowledge_graph.json` filtered to the profile

Do not export encrypted API keys inside profile ZIPs.

## 5. Analytics System Contract

### Event Collection
All important user and system actions should write an append-only `analytics_events` row.

Required event types:
*   `profile_created`
*   `document_uploaded`
*   `document_indexed`
*   `chat_message_sent`
*   `model_call_completed`
*   `topic_started`
*   `topic_completed`
*   `topic_skipped`
*   `quiz_generated`
*   `quiz_submitted`
*   `memory_created`
*   `graph_enriched`
*   `backup_completed`

### Derived Metrics
`AnalyticsService.overview()` should compute:
*   Total active profiles.
*   Active roadmap completion percentage.
*   Documents indexed and documents in error.
*   Total chat sessions/messages.
*   Total study time.
*   Current learning streak.
*   Average mastery by subject.
*   Top weak concepts.
*   Model tokens/cost estimate.

### Dashboard Widgets
MVP dashboard should show:
1. Active profile summary.
2. Active roadmap progress.
3. Recent chat sessions.
4. Document indexing status.
5. Weak concepts.
6. Quick actions: upload document, continue chat, generate roadmap.

### Analytics Query Rules
*   Queries must filter by `profile_id` unless explicitly global.
*   Use SQLite aggregation/window functions where practical.
*   Cache expensive dashboard results briefly in memory.
*   Never block chat or ingestion on analytics write failure; log and continue.

## 6. Quiz and Assessment Contract

### Quiz Generation
Quiz generation input must include:
*   `profile_id`
*   `roadmap_node_id` or topic string
*   `mode`: `practice` or `timed_assessment`
*   `question_count`
*   optional `difficulty`
*   optional `time_limit_seconds`

The model must return strict JSON questions. Validate before saving.

### Question Types
Supported MVP types:
*   `multiple_choice`
*   `short_answer`
*   `explanation`
*   `code` where applicable

### Scoring
*   Multiple choice can be scored deterministically.
*   Short answer/explanation/code uses model rubric scoring.
*   Store both raw user answers and evaluation feedback in `questions_json`.
*   Update `roadmap_nodes.mastery_score` using the last three attempts for that node.
*   Write memory records for strong/weak outcomes as defined in `08_MEMORY_SYSTEM.md`.

### Assessment Mode
Assessment mode is formal:
1. Generate multi-part prompt and rubric.
2. Wait for a complete user answer.
3. Score once.
4. Return score, feedback, and recommended next actions.
5. Update roadmap, graph, memory, and analytics.

## 7. Notes Contract
Notes are local markdown artifacts tied to a profile and optionally a roadmap node.

Required features:
*   Create/edit/delete markdown notes.
*   Link notes to roadmap nodes.
*   Embed note content into `{profile_id}_notes`.
*   Include notes in RAG retrieval.
*   Include notes in profile export/import.
*   Add FTS5 search over title/content/tags.

## 8. Security and Privacy Contract

### Local-First Guarantees
*   All user data lives under `~/.atlas/` and the repository workspace.
*   No cloud database or telemetry.
*   AI provider calls are outbound only and contain only the context required for the requested answer.
*   The backend binds to `127.0.0.1`.

### API Key Handling
*   API keys are accepted through Settings UI/API.
*   Keys are encrypted with Fernet before disk write.
*   Raw keys never appear in logs, analytics, exports, or frontend state after submission.
*   Settings UI may show provider status and masked key suffix only.

### Upload Safety
*   Sanitize filenames.
*   Verify file type server-side.
*   Enforce max size.
*   Store files outside web-served directories.
*   Never execute uploaded content.

### Deletion Guarantees
Profile deletion must remove:
*   SQLite profile-owned rows.
*   ChromaDB profile collections.
*   Raw/extracted document files.
*   Profile graph data.
*   Memory and note embeddings.

## 9. Error Handling and Logging Contract

### Error Envelope
All HTTP errors:
```json
{
  "data": null,
  "error": {
    "code": "NOT_FOUND",
    "message": "Profile not found.",
    "details": {
      "profile_id": "uuid"
    }
  },
  "meta": null
}
```

### Log Files
*   `backend.log`: normal startup, request summaries, service events.
*   `errors.log`: stack traces and unexpected failures.
*   `ingestion.log`: extraction/OCR/chunk/embed details.
*   Optional `model.log`: provider latency, model names, token counts, no raw prompts by default.

### Request Logging Fields
Include:
*   `request_id`
*   `profile_id` when available
*   HTTP method/path
*   status code
*   duration
*   error code when present

Never log raw API keys, full memory content, or full uploaded document text.

## 10. Testing Strategy Contract

### Backend Unit Tests
Required areas:
*   Settings loading.
*   Path sanitization.
*   File hashing.
*   Chunker boundaries and overlap.
*   Token budget trimming.
*   Citation parsing.
*   Memory dedupe.
*   Roadmap unlock logic.
*   Graph merge logic.

### Backend Integration Tests
Required flows:
*   Create profile -> upload document -> extract/chunk/embed -> query RAG.
*   Chat turn -> persist messages -> extract memory.
*   Generate roadmap -> update node -> analytics event.
*   Quiz submit -> mastery update -> memory update.
*   Profile export/import.

### Frontend Tests
Required flows:
*   Setup route when no profile exists.
*   Profile switching invalidates queries.
*   Document upload status updates.
*   WebSocket streaming updates message draft and persists final message after `done`.
*   Roadmap node status optimistic update rolls back on failure.

### E2E Tests
MVP E2E path:
1. Start app.
2. Complete setup.
3. Create profile.
4. Upload a small text PDF.
5. Wait until indexed.
6. Ask a chat question.
7. Verify streamed answer and citation.
8. Restart app.
9. Verify persisted profile/document/chat.

## 11. CI/CD Contract
GitHub Actions should run:
1. Python lint (`ruff`).
2. Python type check (`mypy`) where feasible.
3. Python tests (`pytest`).
4. Frontend lint.
5. TypeScript type check (`tsc --noEmit`).
6. Frontend build.
7. Optional Playwright E2E for release branches.

Release tags should build the frontend, package the app, and attach a ZIP artifact.

## 12. Plugin and Extension Contract
Plugins are future-facing and should not block MVP.

Designed hook points:
*   Document extractors by MIME type.
*   Tutor prompt pre-processing.
*   Tutor response post-processing.
*   Graph enrichment strategies.
*   Quiz question generators.
*   Dashboard widgets.

Plugin manifest draft:
```toml
[plugin]
name = "example"
version = "0.1.0"
entrypoint = "plugin.py"

[hooks]
pre_prompt = true
post_response = true
post_ingestion = false
```

Until a plugin loader exists, keep extension points as clean internal interfaces and document them in the relevant specialist docs.

## 13. Remaining Documentation Gaps to Watch
These are not blockers, but they should become dedicated docs if the project grows:
*   A standalone product requirements document for user stories and acceptance criteria.
*   A dedicated analytics document once dashboard work starts.
*   A dedicated quiz/assessment document once formal assessment work starts.
*   A plugin developer guide in Phase 3.

## 14. Final Build Readiness Checklist
Before implementation starts, confirm:
*   Database schema in `03_DATABASE_DESIGN.md` matches ORM models planned for TASK-008.
*   API payloads in `04_API_SPECIFICATION.md` match Pydantic schemas.
*   Frontend types mirror API payloads.
*   Background tasks have idempotency rules.
*   Setup scripts have exact failure behavior.
*   Every MVP phase has a test target.
*   The master plan and split docs have no known contradictions.
