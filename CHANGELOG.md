# Changelog

Notable changes to Atlas. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security

- **Upgraded FastAPI/Starlette/python-multipart, fixing a real Windows CVE.**
  The pinned Starlette (0.37.2) did not confine a resolved path in
  `StaticFiles`, so a UNC path (`\\host\share`) could make the server open an
  outbound SMB connection — a known technique for leaking a Windows machine's
  NTLM hash to an attacker-controlled listener. Atlas's own SPA route has its
  own containment check and was never affected, but the `/assets` mount used
  Starlette's `StaticFiles` directly. `python-multipart` (0.0.9) also carried
  several denial-of-service parsing bugs, fixed upstream since.
- **Uploads no longer buffer the entire body before checking the size limit.**
  Both the document-upload and profile-import endpoints read the whole
  request into memory before their size cap was applied, so an oversized POST
  paid the memory cost the cap exists to avoid before being rejected. Both
  now read in bounded chunks and abort as soon as the limit is crossed.
  Profile import gets its own cap (`ATLAS_MAX_IMPORT_SIZE_MB`, default 500MB)
  instead of reusing the per-document limit or being unbounded, since an
  export bundles every document a profile has.
- **A warning when Atlas is reachable beyond this machine.** Atlas has no
  login — its only access control is binding to loopback. Setting `--host` or
  `ATLAS_HOST` to anything else now prints a clear warning naming what that
  exposes (documents, memory, any configured provider key) rather than
  silently doing it.
- **The chat WebSocket now checks `Origin`.** CORS does not apply to
  WebSockets, so any page you visited could previously open a socket to the
  tutor — spending your provider credits and reading back answers built from
  your own documents. The handshake is now refused before `accept()` unless
  the origin is loopback. (Exploiting it needed a profile and session UUID,
  which CORS keeps out of a foreign page's reach, so this was hard to use in
  practice — but it should never have been reachable.)
- **Cross-origin writes are blocked.** CORS stops another site *reading* a
  response but not *causing* the request; a form on any page could POST to
  `127.0.0.1` as a simple request. JSON endpoints were already protected by
  the preflight this forces, but the two `multipart/form-data` endpoints
  (document upload, profile import) were the exact shape a cross-origin form
  can produce. Requests whose `Origin` is not loopback are now rejected with
  403. A missing `Origin` is still allowed, so curl and native clients work.
- **Security response headers**, verified against the running app rather than
  just set: a Content Security Policy (`script-src 'self'`, `object-src
  'none'`, `frame-ancestors 'none'`, no `unsafe-eval`) plus `nosniff`,
  `X-Frame-Options`, `Referrer-Policy: no-referrer` and a `Permissions-Policy`
  denying camera/microphone/geolocation/payment. `Strict-Transport-Security`
  is deliberately not sent — Atlas is plain HTTP on loopback, and pinning a
  browser to HTTPS for `localhost` would break every local app on that origin.
- **Dropped the `python-dotenv` pin.** It is imported nowhere (Atlas reads
  `.env` with its own loader); the pin only held it at a version with a
  symlink-following bug in `set_key`/`unset_key`.

### Changed

- **One installer and one launcher, instead of eleven scripts.** The repo root
  held `install.bat`, `install.ps1`, `setup.bat`, `setup.sh`, `start.bat`,
  `start.ps1`, `start.sh`, `start-dev.bat`, `stop.bat`, `stop.ps1` and
  `update.bat` — of which four did real work, three were unreferenced
  PowerShell reimplementations, one was a nine-line forwarder, and one
  duplicated the installer.

  The logic now lives in **`install.py`** and **`start.py`**, with `install.bat`
  / `install.sh` / `start.bat` / `start.sh` as one-line shims so double-clicking
  still works. Python is already a hard prerequisite, so a Python installer
  costs nothing and cannot drift from itself — the batch and shell versions had
  already diverged, with only the shell one explaining how to install Tesseract.

  `stop.bat` is gone: `start.py` runs in the foreground, so Ctrl+C stops it and
  the logs are visible. `start-dev.bat` is now `start.py --dev`, which runs the
  backend with `--reload` and the Vite dev server together and stops both at
  once.

- **A clean repository root.** Only `install.py`, `start.py` and the standard
  project files (README, LICENSE, CHANGELOG, CONTRIBUTING, SECURITY) remain at
  the top level; the double-click shims moved to `scripts/`.

- **Planning and coding-agent documents are no longer distributed.** The
  implementation plan, its coverage audit and the agent guide described how
  Atlas was going to be built rather than how it works, and had drifted from
  the code — the plan still specified scripts that no longer exist. They stay
  on the machine that made them, along with the usual assistant files
  (`CLAUDE.md`, `AGENTS.md`, `.cursor/`, and so on). The reference docs in
  `docs/` that describe the running system are unaffected, and `docs/README.md`
  is now an index for people rather than a handoff note for agents.

- **The installer is now tested by CI, on Windows as well as Linux.** It runs
  `install.py`, boots what that produced, exercises the database, and checks
  that `start.py` refuses clearly when run before installing. `install.bat`
  once shipped exiting 255 for every user, and `setup.sh` shipped with CRLF
  shebangs — both on a repo whose CI was Linux-only and never ran either file.

### Fixed

- **A dead setting in the first file a user opens.** The installer wrote
  `AI_PROVIDER=offline` into `.env`; nothing has ever read `AI_PROVIDER`.
- **A fresh install reported `development`** on its health endpoint, because
  the `.env` it created was copied verbatim from the contributor template.
- An OCR error told users to run `setup.bat/setup.sh`, which no longer exist.

## [0.1.0] - 2026-08-27

First tagged release. Everything below is the work leading up to it, so there
is no upgrade path to describe: entries are grouped by what changed rather
than by version.

### Added

- **Landing page** at `/` with the profile chooser: every profile as a card,
  inline creation, and a canvas particle field that pauses in a background tab
  and renders a single static frame under `prefers-reduced-motion`.
- **Local embeddings, used by default.** Atlas embeds on your own machine with
  a small ONNX model, so a fresh clone can upload, index and search documents
  before any API key exists. It is also the fallback whenever the configured
  provider cannot embed — no key, or no embeddings API at all — so search stops
  being something that can be switched off by a chat-provider choice. An
  explicitly chosen embedding provider is never silently replaced.
- **Separate providers for chat and embeddings.** Choosing a chat provider with
  no embeddings API — OpenRouter, Groq, Anthropic, DeepSeek — no longer takes
  document search down with it.
- **Live model discovery.** Chat and embedding model lists are fetched from the
  configured provider rather than hardcoded, with a free-tier filter and an
  offline fallback. Any model id can still be typed by hand.
- **AI-named chat threads.** Sessions are titled from their opening message
  instead of all reading "Chat (Teaching)"; a title you set by hand is never
  overwritten.
- **Roadmap-linked chat threads.** Opening the tutor from a topic returns to
  that topic's thread instead of starting another, and a tutoring turn moves the
  topic from not started to in progress.
- **Profile switcher and a collapsible desktop rail**, replacing a transparent
  `<select>` stretched over the sidebar footer.
- **Pointer overlay** — a dot that tracks exactly with a ring that trails it,
  declining to take over on coarse pointers, in forced-colors mode, and over
  text fields.
- **Evals** for the AI parts — retrieval scored with precision/recall/MRR/NDCG
  over a golden set of student-phrased questions, and syllabus parsing scored
  on structural recall *and* precision. Both run through the real pipeline,
  embed locally so they need no API key, and gate CI on every push. The
  syllabus suite immediately found a live bug (below).
- **ESLint** with `react-hooks/exhaustive-deps` as an error, wired into CI.
- **CI**: backend suite on Python 3.11/3.12/3.13, frontend lint/typecheck/test/
  build, a secrets scan, and a fresh-install job that boots the app from
  `requirements.txt` alone.
- **LICENSE (MIT), CONTRIBUTING, SECURITY** and a `.gitattributes` line-ending
  policy.

### Changed

- **Renamed from LearningOS to Atlas.** Pre-rename names are kept where they are
  load-bearing: an existing `~/.learningos` data directory and `learningos.db`
  are reused when present, `ATLAS_*` environment variables fall back to
  `LEARNINGOS_*`, and browser storage keys migrate with one-time carryover.
- **Whole-app visual system**: flat rectangular surfaces, opaque panels, mono
  bracket labels, outline-on-hover feedback, and a black/grey/red palette with
  measured contrast (`#E11D48` fills at 4.70:1 with white, `#FF4D5E` accent text
  at 5.07:1 on surfaces).
- Retrieved document chunks are labelled untrusted in the RAG prompt, with an
  explicit instruction to treat them as data rather than instructions.

### Fixed

- **Provider calls failed after one use.** Transient 503s from free tiers were
  not retried; requests now retry with exponential backoff and jitter and honour
  `Retry-After`.
- **API keys leaked into error messages and logs.** Keys moved out of request
  URLs into headers, behind a redaction layer that also covers tracebacks.
- **Path traversal** through the SPA static route.
- **`greenlet` missing from requirements.** SQLAlchemy only pulls it in for
  Python < 3.13, so a clean install on 3.13 produced an app where every database
  call raised. `sqlalchemy[asyncio]` is now declared.
- **`install.bat` exited 255 for every user** — an unescaped `)` inside an
  `else` block ended it early, so the installer never reported success.
- **`setup.sh` and `start.sh` were stored with CRLF**, including the shebang, so
  the documented macOS/Linux path failed with `bad interpreter`.
- **`keystore.key` kept inherited ACLs.** The permission fix ran only when
  creating the key, so any install predating it left the key that decrypts the
  keystore readable by every administrator.
- **`start.bat` set `ATLAS_ENV` to `"production "`** — in cmd, `set VAR=value &&`
  captures the space before the `&&`, so any comparison against `"production"`
  would silently fail.
- **Memory extraction produced nothing.** A reasoning model can spend its whole
  budget thinking and return a null content field; that null reached
  `json.loads` as an empty string, and the budgets were too small besides.
  Extraction also only ran on the WebSocket path.
- **Page furniture became syllabus topics.** The deterministic parser absorbed
  any unrecognised line as content, so PDF page footers, "Prescribed Textbooks"
  lists and exam-pattern boilerplate were promoted into the structure — and
  roadmaps asked learners to study "Page 4 of 4". Found by the new syllabus
  eval, which scores precision precisely because recall cannot see this.
- **Short answers were graded on keyword overlap, not meaning.** The evaluator
  was given a 350-token budget, which a reasoning model spends before writing
  any JSON, so every short answer quietly fell through to the terminology
  fallback and scored on vocabulary rather than understanding.
- **Syllabus parsing silently fell back to a heuristic** that turned page
  headers into topics, because the JSON reply was truncated and nothing could
  tell truncation from malformed output. `finish_reason` is now exposed.
- **Knowledge graph collapsed into the centre.** Centre gravity grew linearly
  with distance while repulsion fell off with its square, so gravity won
  everywhere that mattered. Overlaps are now separated directly, and a trackpad
  pinch zooms the graph rather than the whole page.
- **Chat and roadmap panels grew without bound.** Both now bound their height
  and scroll internally, with the composer pinned to the bottom of the card.
- **Stale-closure bugs** found by ESLint: a category filter that never
  refetched, a URL node id read stale, and two "select the first item" guards
  that tied a fetch to the selection.

### Security

- API keys are encrypted at rest with Fernet (AES-128-CBC + HMAC-SHA256); the
  key file is restricted to the current user, re-asserted on load rather than
  only at creation.
- CORS is scoped to localhost origins; no wildcard-with-credentials.
- Uploads are validated by magic bytes rather than extension, size-capped, and
  stored under generated names so a filename cannot traverse.

[Unreleased]: https://github.com/OWNER/atlas/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/OWNER/atlas/releases/tag/v0.1.0
