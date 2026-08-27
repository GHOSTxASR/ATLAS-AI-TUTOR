#!/usr/bin/env python3
"""Run Atlas.

Run it directly, or double-click `start.bat` / `start.sh`, which are one-line
shims onto this file.

    python start.py                # production: one server, opens a browser
    python start.py --dev          # backend --reload plus the Vite dev server
    python start.py --port 9000    # a different port
    python start.py --no-browser   # do not open a browser

Stop it with Ctrl+C. That is why there is no stop script any more: the old
start.bat launched the server into a detached minimised window and returned,
so a separate stop.bat had to hunt the process down by port. Running in the
foreground makes the logs visible and the lifetime obvious.
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
VENV = BACKEND / ".venv"

IS_WINDOWS = os.name == "nt"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
VITE_PORT = 5173


def _supports_colour() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


C_OK = "\033[32m" if _supports_colour() else ""
C_ERR = "\033[31m" if _supports_colour() else ""
C_DIM = "\033[90m" if _supports_colour() else ""
C_OFF = "\033[0m" if _supports_colour() else ""


def die(message: str, *, hint: str = "", code: int = 1) -> None:
    print(f"\n{C_ERR}[error]{C_OFF} {message}", file=sys.stderr)
    if hint:
        print(f"        {hint}", file=sys.stderr)
    raise SystemExit(code)


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")


def load_env_file() -> None:
    """Read .env into the environment without overriding what is already set.

    Real environment variables win, so `ATLAS_PORT=9000 python start.py`
    behaves the way anyone would expect.
    """
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


def port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex((host, port)) != 0


def wait_until_healthy(url: str, timeout: float = 90.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, OSError, TimeoutError):
            pass
        time.sleep(0.5)
    return False


def open_browser_when_ready(health_url: str, app_url: str) -> None:
    """Open a browser once the server answers, on a background thread.

    The first launch loads the local embedding model, so 'ready' can be tens
    of seconds after the process starts -- opening immediately would show a
    connection error.
    """
    def worker() -> None:
        if wait_until_healthy(health_url):
            print(f"{C_OK}  ready{C_OFF} -- opening {app_url}")
            webbrowser.open(app_url)
        else:
            print(f"{C_ERR}  the server did not become healthy in time{C_OFF}", file=sys.stderr)

    threading.Thread(target=worker, daemon=True).start()


def preflight(dev: bool) -> None:
    if not venv_python().exists():
        die(
            "Atlas is not installed yet.",
            hint="Run: python install.py",
        )
    if not dev and not (FRONTEND / "dist" / "index.html").exists():
        die(
            "the built interface is missing (frontend/dist/index.html).",
            hint="Run: python install.py    (or use --dev for the Vite dev server)",
        )


def serve_production(host: str, port: int, open_browser: bool) -> int:
    env = {
        **os.environ,
        "PYTHONPATH": str(BACKEND),
        "ATLAS_ENV": os.environ.get("ATLAS_ENV", "production"),
        "ATLAS_HOST": host,
        "ATLAS_PORT": str(port),
    }
    app_url = f"http://{host}:{port}"

    print("=" * 55)
    print("  Atlas")
    print("=" * 55)
    print(f"  {app_url}")
    print(f"{C_DIM}  Ctrl+C to stop{C_OFF}")
    print()

    if open_browser:
        open_browser_when_ready(f"{app_url}/api/v1/health", app_url)

    return subprocess.call(
        [
            str(venv_python()), "-m", "uvicorn", "app.main:app",
            "--host", host, "--port", str(port),
        ],
        cwd=str(BACKEND),
        env=env,
    )


def serve_dev(host: str, port: int, open_browser: bool) -> int:
    """Backend with --reload plus the Vite dev server, and one Ctrl+C for both."""
    import shutil

    npm = shutil.which("npm")
    if not npm:
        die("--dev needs Node.js and npm on PATH.", hint="https://nodejs.org/")

    env = {
        **os.environ,
        "PYTHONPATH": str(BACKEND),
        "ATLAS_ENV": "development",
        "ATLAS_HOST": host,
        "ATLAS_PORT": str(port),
    }
    vite_url = f"http://{host}:{VITE_PORT}"

    print("=" * 55)
    print("  Atlas (development)")
    print("=" * 55)
    print(f"  interface  {vite_url}")
    print(f"  api        http://{host}:{port}/api/v1")
    print(f"{C_DIM}  Ctrl+C to stop both{C_OFF}")
    print()

    backend = subprocess.Popen(
        [
            str(venv_python()), "-m", "uvicorn", "app.main:app",
            "--reload", "--host", host, "--port", str(port),
        ],
        cwd=str(BACKEND),
        env=env,
    )
    frontend = subprocess.Popen(
        [npm, "run", "dev", "--", "--host", host],
        cwd=str(FRONTEND),
        env=env,
    )

    if open_browser:
        open_browser_when_ready(f"http://{host}:{port}/api/v1/health", vite_url)

    try:
        while True:
            for name, proc in (("backend", backend), ("frontend", frontend)):
                if proc.poll() is not None:
                    print(f"\n{C_ERR}  the {name} exited ({proc.returncode}){C_OFF}", file=sys.stderr)
                    return proc.returncode or 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        return 0
    finally:
        for proc in (frontend, backend):
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()


def main() -> int:
    load_env_file()

    parser = argparse.ArgumentParser(prog="start.py", description="Run Atlas.")
    parser.add_argument("--dev", action="store_true", help="development servers with hot reload")
    parser.add_argument(
        "--port", type=int, default=int(os.environ.get("ATLAS_PORT", DEFAULT_PORT)),
        help=f"API port (default {DEFAULT_PORT})",
    )
    parser.add_argument("--host", default=os.environ.get("ATLAS_HOST", DEFAULT_HOST))
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser")
    args = parser.parse_args()

    preflight(args.dev)

    if not port_is_free(args.host, args.port):
        die(
            f"port {args.port} is already in use.",
            hint=(
                "Another Atlas may still be running -- switch to its window and press Ctrl+C.\n"
                f"        Or start on a different port: python start.py --port {args.port + 1}"
            ),
        )

    serve = serve_dev if args.dev else serve_production
    return serve(args.host, args.port, not args.no_browser)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nstopped")
        raise SystemExit(0)
