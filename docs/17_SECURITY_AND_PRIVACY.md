# 17. Security and Privacy

## 1. Purpose
This document defines the security and privacy requirements for Atlas. The application is local-first, but local applications still need careful handling of secrets, files, logs, deletion, and outbound AI-provider calls.

Related documents:
* The code is the source of truth; this file records the intent behind it.
* `04_API_SPECIFICATION.md`: API errors and endpoint behavior.
* `06_BACKEND_ARCHITECTURE.md`: middleware, exception handling, and services.
* `13_DEPLOYMENT.md`: local setup, packaging, and script behavior.
* `16_TESTING_STRATEGY.md`: security test requirements.

## 2. Security Goals
* Keep user learning data local by default.
* Prevent accidental LAN exposure.
* Protect API keys at rest and in logs.
* Prevent uploaded files from escaping the intended data directory.
* Make deletion and export behavior predictable.
* Avoid silent telemetry or hidden cloud sync.
* Fail safely when configuration is missing.

## 3. Trust Model
Atlas assumes:
* The local OS user is authorized to use the app.
* There is no multi-user authentication server.
* Browser and backend run on the same machine.
* AI provider calls are outbound and user-configured.
* The local filesystem may contain sensitive educational, personal, or exam-prep data.

Atlas does not assume:
* Uploaded files are safe.
* Browser-provided MIME types are truthful.
* Model providers are always available.
* Logs are private enough to contain secrets or full personal memory.

## 4. Threat Model

### In Scope
| Threat | Mitigation |
| :--- | :--- |
| LAN access to local backend | Bind Uvicorn to `127.0.0.1`; CORS local origins only. |
| API key leakage | Fernet encryption at rest; log redaction; clear frontend state. |
| Path traversal upload | Sanitize names; UUID storage names; safe path join. |
| Malicious file content | Treat as data only; never execute uploaded files. |
| Accidental data loss | Confirm destructive actions; backup task; export. |
| Cross-profile leakage | Enforce `profile_id` filtering in every query/collection. |
| Prompt/context over-sharing | Send only required context to provider; user controls documents/memory. |
| Log exposure | Redact secrets and avoid raw document/memory text by default. |
| Corrupt local data | Atomic writes and backups. |

### Out of Scope for MVP
* Multi-user authentication.
* Remote access over LAN/internet.
* Enterprise SSO.
* Hardware-backed key storage.
* Full malware scanning of uploaded documents.
* End-to-end encrypted cloud sync.

## 5. Local-First Privacy Guarantees
The app must not use a cloud database or telemetry endpoint.

Local data includes:
* SQLite database.
* ChromaDB vectors.
* Knowledge graph JSON.
* Raw uploaded files.
* Extracted document text.
* Chat history.
* Memory records.
* Notes.
* Quiz attempts.
* Analytics events.
* Logs.

Data directory:
```text
~/.atlas/
├── data/
├── profiles/
├── config/
├── logs/
└── backups/
```

## 6. Network Security

### Backend Binding
Production and development backend must bind to:
```text
127.0.0.1
```

Do not bind to:
```text
0.0.0.0
```

unless a future LAN-sharing mode is explicitly designed with authentication, warnings, and documentation.

### CORS
Allowed origins:
* `http://localhost:5173`
* `http://127.0.0.1:5173`
* same-origin production frontend served by FastAPI

Reject other origins by default.

### WebSocket
WebSocket endpoint must validate:
* `profile_id` exists.
* `session_id` exists.
* Session belongs to profile.

Invalid profile/session should close gracefully or emit a structured error.

## 7. API Key Handling

### Storage
API keys must be stored only in:
```text
~/.atlas/config/secrets.enc
```

Rules:
* Never store raw API keys in `settings.toml`.
* Never store raw API keys in SQLite.
* Never include raw API keys in exports.
* Never return raw API keys from API responses.

### Encryption
Use `cryptography.Fernet`.

Key derivation:
* MVP may derive from a machine/user-specific stable secret.
* Store only encrypted payload on disk.
* If key derivation changes, provide migration or clear error.

### Frontend Behavior
* API key field is write-only after save.
* Frontend clears raw key state after request completes.
* UI shows provider status and masked suffix only, such as `sk-...Ab12`.

### Logging Redaction
Redact:
* OpenAI keys.
* Anthropic keys.
* Bearer tokens.
* Any field named `api_key`, `authorization`, `secret`, `token`.

## 8. File Upload Security

### Validation
For each upload:
1. Enforce max size.
2. Verify extension and magic bytes.
3. Treat browser MIME type as advisory.
4. Reject unsupported types.
5. Compute SHA-256 hash.
6. Store with UUID-prefixed safe filename.

### Path Safety
All file writes must use safe path join:
* Resolve final path.
* Verify it stays inside intended profile directory.
* Reject `..`, absolute paths, drive letters in display filename, and control characters.

### Storage
Raw uploads:
```text
~/.atlas/profiles/{profile_id}/documents/raw/
```

Extracted text:
```text
~/.atlas/profiles/{profile_id}/documents/extracted/
```

Never serve raw uploaded files directly as static files without a controlled API route.

### Execution
Uploaded files are data only:
* Do not execute macros.
* Do not execute scripts.
* Do not shell out with user-controlled paths.

## 9. Database and Vector Isolation

### SQLite
Every profile-owned table must include or join through `profile_id`.

Repository methods must require profile context for profile-owned reads:
* Documents.
* Sessions/messages.
* Roadmaps.
* Memory.
* Notes.
* Quiz.
* Analytics.

### ChromaDB
Use profile-scoped collections:
* `{profile_id}_documents`
* `{profile_id}_memory`
* `{profile_id}_notes`
* `{profile_id}_chat_summaries`

Metadata should include `profile_id` even in profile-scoped collections as a defense-in-depth check.

### Knowledge Graph
If using a shared graph file, every node must include `profile_id`. Graph APIs must filter by profile.

## 10. AI Provider Privacy

### Outbound Data
AI calls may include:
* User message.
* Relevant chat history.
* Relevant document snippets.
* Relevant memory records.
* Roadmap context.
* Prompt instructions.

AI calls must not include:
* Full database dumps.
* Full documents unless explicitly required.
* API keys.
* Unrelated profiles.
* Inactive/deleted memories.

### User Control
Users must be able to:
* Delete documents.
* Delete memories.
* Delete chat sessions.
* Delete profiles.
* Choose local Ollama provider where available.

### Provider Disclosure
Settings should make clear which provider is active:
* OpenAI.
* Anthropic.
* Ollama/local.

## 11. Logging Privacy

### Safe to Log
* Request path and status.
* Request ID.
* Profile ID.
* Document ID.
* Session ID.
* Model name.
* Token counts.
* Latency.
* Error code.

### Not Safe to Log by Default
* Raw API keys.
* Full prompts.
* Full model responses.
* Full document text.
* Full memory content.
* Quiz answers.
* Personal notes.

Debug logging may include additional detail only when explicitly enabled by a developer and should still redact secrets.

## 12. Destructive Actions

Require confirmation for:
* Delete profile.
* Delete document.
* Delete chat session.
* Delete memory.
* Delete note.
* Drop/rebuild embeddings.
* Regenerate roadmap when archiving previous roadmap.

Confirmation copy should name the affected resource.

Profile deletion must remove:
* SQLite rows.
* ChromaDB collections.
* Profile files.
* Profile graph nodes/edges.
* Memory/note vectors.

## 13. Export and Import Privacy

### Export
Profile export may include:
* Profile metadata.
* Documents.
* Extracted text.
* Chats.
* Roadmaps.
* Memories.
* Notes.
* Quiz attempts.
* Analytics.
* Profile graph data.

Profile export must not include:
* API keys.
* `secrets.enc`.
* Global app logs.
* Other profiles.

### Import
Import must:
* Validate ZIP structure.
* Reject path traversal entries.
* Create new IDs if collisions occur.
* Rebuild ChromaDB embeddings if vector dimensions/model mismatch.
* Never overwrite another profile without explicit confirmation.

## 14. Dependency Security
Required practices:
* Pin backend dependencies.
* Use `package-lock.json`.
* Run dependency vulnerability checks before release.
* Keep Tesseract optional unless packaged.
* Avoid installing global packages in setup scripts.

Suggested checks:
```bash
pip-audit
npm audit
```

If a vulnerability exists in a non-exposed local-only dependency, document the risk and mitigation before release.

## 15. Windows Permission Requirements
On first run:
* Create `~/.atlas`.
* Restrict directory access to current OS user where practical.
* Avoid requiring administrator privileges.
* Install into user-writable locations for packaged builds.

On Unix:
* Apply `chmod 700` to `~/.atlas`.
* Avoid writing outside the user home directory unless configured.

## 16. Security Test Checklist
Automated or manual checks:
* Backend host is `127.0.0.1`.
* CORS rejects unknown origins.
* WebSocket rejects wrong profile/session combination.
* API key saved encrypted.
* API key absent from logs.
* Path traversal upload is rejected.
* Oversized upload is rejected.
* Unsupported file type is rejected.
* Deleting profile removes files and vectors.
* Export excludes secrets.
* Cross-profile document access returns 404.
* Cross-profile ChromaDB retrieval returns no results.
* Corrupt graph file is quarantined safely.

## 17. Incident Recovery
If data corruption occurs:
1. Stop server.
2. Preserve current `~/.atlas` by copying it.
3. Restore latest backup.
4. Restart server.
5. Run health/storage checks.

If API key encryption fails:
1. Do not start model calls.
2. Show `CONFIGURATION_ERROR`.
3. Let user re-enter API key.
4. Do not log raw key during retry.

## 18. Release Security Gate
Before release:
* Security checklist passes.
* No secrets in repository.
* No secrets in logs after E2E test.
* Dependency audit reviewed.
* Clean-machine setup does not need admin privileges.
* Export/import tested for path traversal.
* Profile deletion tested end to end.

