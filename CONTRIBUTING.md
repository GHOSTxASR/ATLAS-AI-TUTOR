# Contributing to Atlas

Thanks for taking the time to contribute.

## Getting set up

```bash
git clone <your-fork-url>
cd Atlas

# Backend
cd backend
python -m venv .venv
.venv/Scripts/activate            # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r requirements-dev.txt
pytest

# Frontend
cd ../frontend
npm install
npm test
```

Use **`requirements-dev.txt`**, not `requirements.txt` — the latter is runtime
only and does not include `pytest` or `ruff`.

## Before you open a pull request

Run everything CI runs:

```bash
cd backend && pytest && ruff check app/ alembic/
cd ../frontend && npm test && npm run typecheck && npm run build
```

All of these must pass. CI runs the backend suite on Python 3.11, 3.12 and 3.13.

## Dependencies

Runtime dependencies go in `backend/requirements.txt`; test-and-lint-only
dependencies go in `backend/requirements-dev.txt`.

Be explicit about transitive dependencies you actually rely on. A dependency
that happens to be installed on your machine may not be installed on a clean
one — SQLAlchemy, for example, only pulls in `greenlet` automatically on Python
< 3.13, which is why this project depends on `sqlalchemy[asyncio]` rather than
plain `sqlalchemy`. The `fresh-install` CI job exists to catch exactly this
class of bug: it installs `requirements.txt` alone and boots the app.

## Database migrations

Schema changes need an Alembic migration:

```bash
cd backend
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

Migrations run automatically on application startup.

## Style

* Python is formatted and linted with **ruff** (line length 100, target py311).
* TypeScript must pass `tsc --noEmit` with no errors.
* Match the surrounding code — naming, comment density, and existing idioms.
* Comments should explain *why*, not restate *what* the code does.

## Tests

New behaviour needs a test. Bug fixes should come with a test that fails before
the fix.

* Backend tests live in `backend/app/tests/` (`unit/` and `integration/`),
  using pytest with `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` needed.
* Tests must not touch a real data directory or make real network calls. Point
  `ATLAS_DATA_DIR` at a `tmp_path` and stub providers with
  `httpx.MockTransport`.
* Frontend tests use vitest and live in `frontend/src/test/`.

## Security

Never commit secrets. `.env` is gitignored and must stay that way; put
placeholders in `.env.example`. If you find a vulnerability, follow
[SECURITY.md](SECURITY.md) rather than opening a public issue.

## Reporting bugs

Please include:

* what you expected and what happened instead
* OS, Python version, and Node version
* the model provider in use
* relevant log output from `~/.atlas/logs/` — **check it for API keys first**,
  though Atlas redacts them by design
