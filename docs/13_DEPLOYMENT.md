# 13. Deployment

## 1. Deployment Overview
Atlas is designed exclusively for local deployment. It runs directly on the user's personal computer. There are no cloud servers, no Docker containers (to keep installation simple for non-developers), and no centralized databases. The system consists of a FastAPI backend and a static React frontend.

## 2. System Requirements
*   **Operating System**: Windows 10/11 (Primary Target), macOS 12+, Ubuntu 20.04+.
*   **Dependencies**: Python 3.11+, Node.js 20 LTS (for development/setup).
*   **Optional**: Tesseract OCR (if processing image-based PDFs).
*   **Hardware**: 4GB RAM minimum (8GB recommended for embedding generation). 5GB free disk space for local models and databases.

## 3. `setup.bat` — Complete Specification
The initialization script for Windows users. Steps:
1.  **Check Python**: `python --version`. If < 3.11 or missing, echo download link and `exit /b 1`.
2.  **Check Node.js**: `node --version`. If missing, echo download link and `exit /b 1`.
3.  **Check Tesseract**: Look in `%ProgramFiles%\Tesseract-OCR\`. Warn if missing but continue.
4.  **Create Venv**: `python -m venv backend\.venv`.
5.  **Install Python Deps**: `call backend\.venv\Scripts\activate.bat` -> `pip install -r backend\requirements.txt`.
6.  **Install Node Deps**: `cd frontend` -> `npm install`.
7.  **Build Frontend**: `npm run build`.
8.  **Run Migrations**: `cd ..\backend` -> `alembic upgrade head`.
9.  **Create Config**: Copy `.env.example` to `~/.atlas/config/settings.toml` if it doesn't exist.
10. **Success**: `echo Setup Complete. Run start.bat to launch.`

## 4. `start.bat` — Complete Specification
The daily launch script.
1.  **Terminal Title**: `title Atlas Server`.
2.  **Venv Check**: Ensure `backend\.venv` exists.
3.  **Port Conflict Check**: `netstat -ano | findstr :8000`. Warn if in use.
4.  **Activate**: `call backend\.venv\Scripts\activate.bat`.
5.  **Environment Variables**: Set `PYTHONPATH=app`, `ATLAS_ENV=production`.
6.  **Launch Backend**: `start /MIN uvicorn app.main:app --host 127.0.0.1 --port 8000`. (Minimizes the terminal window).
7.  **Health Check Loop**: Ping `http://localhost:8000/api/v1/health` using PowerShell `Invoke-WebRequest` every 500ms. Timeout after 30s.
8.  **Launch Browser**: `start http://localhost:8000`.
9.  **Keep Alive**: Script waits. On `Ctrl+C`, it finds the Uvicorn PID and sends `SIGTERM` to gracefully shutdown.

## 5. `start-dev.bat` — Complete Specification
For developers.
1. Launches backend with `--reload`: `start cmd /k "cd backend && call .venv\Scripts\activate && uvicorn app.main:app --reload"`
2. Launches frontend dev server: `start cmd /k "cd frontend && npm run dev"`
3. Opens browser to `http://localhost:5173`.

## 6. Unix Scripts (`setup.sh`, `start.sh`)
Exact equivalents of the `.bat` files using `bash` syntax.
*   Uses `python3` and `pip3`.
*   Venv activation via `source backend/.venv/bin/activate`.
*   Process backgrounding via `&` and `wait`.
*   `setup.sh` checks for Tesseract OCR via `command -v tesseract` and warns (with a distro-specific install hint) if missing, but continues — matching `setup.bat`.

## 7. Data Directory Initialization
On the very first run of `main.py`, `lifespan.py` checks for the existence of `~/.atlas/`.
If missing, it creates the full directory tree:
`data/sqlite`, `data/chroma`, `data/graph`, `profiles/`, `config/`, `logs/`.
On Unix, it applies `chmod 700` to ensure only the local user can read the files. On Windows, it sets ACLs restricting access to the current user.

## 8. `settings.toml` Default Values
```toml
[app]
environment = "production"
port = 8000

[paths]
data_dir = "~/.atlas/"
tesseract_path = "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

[models]
provider = "openai" # Options: openai, anthropic, ollama
embedding_model = "text-embedding-3-small"
chat_model = "gpt-4o"

[logging]
level = "INFO"
```

## 9. First-Time User Flow
1. User runs `start.bat`.
2. Browser opens to `localhost:8000`.
3. Frontend detects no profiles via API.
4. Redirects to `/setup`.
5. User selects API provider and enters Key (encrypted locally).
6. User creates their first Profile.
7. Redirects to `/dashboard` ready for use.

## 10. Dependency Management
*   **Backend**: `requirements.txt` strictly pins versions (e.g., `fastapi==0.111.0`) to guarantee stability across environments. Avoids global Python packages by strictly enforcing the `.venv`.
*   **Frontend**: `package-lock.json` ensures deterministic builds.

## 11. Frontend Serving
In development, Vite (`localhost:5173`) proxies API calls to FastAPI.
In production, `npm run build` generates the `dist/` folder.
FastAPI mounts this folder:
```python
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="../frontend/dist", html=True), name="static")
```
This reduces the deployed app to a single port (8000) and a single process.

## 12. Packaging — Option A (ZIP Distribution)
For users who don't want to install Node/Python.
A self-contained ZIP (~150MB) containing:
1.  Python Embeddable Package (pre-configured).
2.  Pre-installed `site-packages`.
3.  Pre-built frontend `dist` folder.
4.  Simple `run.bat` that executes the embedded python without needing admin rights or global installs.

## 13. Packaging — Option B (NSIS Installer)
A formal Windows `.exe` installer built using NSIS.
1. Installs to `%LOCALAPPDATA%\Atlas`.
2. Bundles the Python runtime and Tesseract binaries.
3. Creates a Start Menu shortcut and Desktop icon pointing to a hidden `uvicorn` runner script.
4. Total size ~200MB.

## 14. Update Process (`update.bat`)
A script for users tracking the `git` repo:
```bat
git pull origin main
call backend\.venv\Scripts\activate
pip install -r backend\requirements.txt
cd frontend && npm install && npm run build
cd ..\backend && alembic upgrade head
echo Update complete.
```

## 15. CI/CD Pipeline
GitHub Actions configured in `.github/workflows/main.yml`:
1.  **Lint**: Runs `ruff` for Python, `ESLint` for React.
2.  **Type Check**: Runs `mypy` and `tsc`.
3.  **Test**: Runs `pytest` suite.
4.  **Build**: Compiles frontend.

## 16. Release Workflow
Triggered by pushing a semver tag (e.g., `v1.0.0`):
1. Runs full CI pipeline.
2. Builds the ZIP Distribution (Option A).
3. Creates a GitHub Release.
4. Uploads the ZIP as an asset.
5. Auto-generates changelog from commits.

## 17. Branch Strategy
*   `main`: Production-ready, always deployable.
*   `dev`: Integration branch for ongoing work.
*   `feature/*`: Individual feature branches (e.g., `feature/hybrid-roadmap`).
*   `hotfix/*`: For critical bugs on `main`.

## 18. Security Checklist
*   [x] FastAPI strictly bound to `127.0.0.1` (no LAN access by default).
*   [x] API keys encrypted with Fernet symmetric encryption.
*   [x] Uploaded files renamed with UUIDs to prevent path traversal (`../../../windows/system32`).
*   [x] No API keys or sensitive user facts logged to `backend.log`.
*   [x] `~/.atlas` directory restricted to the current OS user.

## 19. Troubleshooting Guide
*   **Port 8000 in use**: Check Task Manager for dangling `python.exe` processes, or edit `settings.toml` to change the port to 8080.
*   **Python not found**: Ensure Python is added to the system PATH during installation.
*   **OCR Disabled**: Ensure Tesseract is installed and the path in `settings.toml` matches the actual installation directory.
*   **Database Migration Failed**: Usually implies database corruption. Stop server, rename `atlas.db` to `.bak`, restart to build fresh schema.
*   **Frontend White Screen**: Ensure `npm run build` was executed successfully.

## 20. Log File Locations
All logs are in `~/.atlas/logs/`.
*   `backend.log`: General server info, API requests, routing.
*   `ingestion.log`: Specific logs for PyMuPDF, chunking, and embedding.
*   `errors.log`: Only contains stack traces and HTTP 500 errors.

## 21. Backup and Restore
*   **Auto Backup**: `APScheduler` runs daily at 3 AM. It copies `atlas.db` and the `chroma` folder to `~/.atlas/backups/`.
*   **Manual Restore**: Stop the server. Copy the DB and Chroma folders from the backup directory over the live ones. Restart the server.

## 22. macOS / Linux Differences
*   `Tesseract` is installed via `brew install tesseract` or `apt-get install tesseract-ocr`.
*   Paths use `/` instead of `\`.
*   The data directory defaults to `~/.atlas/` which expands to `/home/user/.atlas` or `/Users/user/.atlas`.

## 23. Testing the Installation
After running `setup.bat` and `start.bat`:
1.  Navigate to `http://localhost:8000`.
2.  Complete the setup wizard.
3.  Upload a small PDF. Watch the status change to `indexed`.
4.  Open Chat, type "Summarize the document."
5.  If streaming text appears with citations, the system is fully operational.

## 24. Master Plan Deployment Addendum

### Complete `settings.toml` Template
Use this as the initial file written to `~/.atlas/config/settings.toml`:
```toml
[app]
name = "Atlas"
version = "1.0.0"
environment = "production"
data_dir = ""

[server]
host = "127.0.0.1"
port = 8000
log_level = "warning"

[model]
provider = "openai"
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

### Script Exit Codes
| Code | Meaning |
| :--- | :--- |
| `0` | Success. |
| `1` | Missing required dependency. |
| `2` | Dependency installation failed. |
| `3` | Database migration failed. |
| `4` | Frontend build failed. |
| `5` | Backend failed health check. |
| `6` | Port conflict. |

Scripts should print a short human-readable cause and a next action before exiting non-zero.

### `setup.bat` Verification Steps
After dependency installation, `setup.bat` should verify:
1. `backend\.venv\Scripts\python.exe` exists.
2. `pip check` exits successfully.
3. `frontend\node_modules` exists.
4. `npm run build` creates `frontend\dist\index.html`.
5. Alembic can run `upgrade head`.
6. `~/.atlas/config/settings.toml` exists.
7. Required data directories exist.

### `start.bat` Process Rules
*   Read the configured port from `settings.toml` when possible; default to `8000`.
*   Refuse to continue if the selected port is already owned by an unrelated process.
*   Start Uvicorn with host `127.0.0.1`.
*   Poll `/api/v1/health` until ready or timeout.
*   Open the browser only after health succeeds.
*   On shutdown, stop the child Uvicorn process and allow FastAPI lifespan shutdown to flush graph/scheduler state.

### Clean Machine Release Test
Before publishing a ZIP or installer, test on a clean Windows user profile:
1. No global Python packages assumed.
2. No global Node packages assumed unless using source setup.
3. No existing `~/.atlas` directory.
4. Run setup.
5. Launch app.
6. Create profile.
7. Add API key.
8. Upload text PDF.
9. Confirm indexed status.
10. Ask chat question and verify streamed answer with citation.
11. Stop and restart app.
12. Confirm profile, document, chat, and memory still exist.
