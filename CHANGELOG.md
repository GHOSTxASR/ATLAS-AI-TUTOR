# Changelog

Notable changes to Atlas. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Everything below is the work leading up to the first tagged release. Atlas has
not been released yet, so there is no upgrade path to describe: entries are
grouped by what changed rather than by version.

### Added

- **Landing page** at `/` with the profile chooser: every profile as a card,
  inline creation, and a canvas particle field that pauses in a background tab
  and renders a single static frame under `prefers-reduced-motion`.
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

[Unreleased]: https://github.com/OWNER/atlas/commits/master
