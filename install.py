#!/usr/bin/env python3
"""Install Atlas: virtual environment, dependencies, frontend build, data dirs.

Run it directly, or double-click `install.bat` / `install.sh`, which are
one-line shims onto this file.

    python install.py                 # full install
    python install.py --skip-frontend # backend only (dist/ already built)
    python install.py --quiet         # less pip/npm noise

This is deliberately one cross-platform script rather than a .bat and a .sh
saying the same thing twice. The two had already drifted -- the shell version
told you how to install Tesseract for your package manager and the batch
version just said "not found" -- and there were three unused PowerShell
reimplementations behind them. Python is already a hard prerequisite for
Atlas, so putting the logic here costs nothing and it can only drift from
itself.

Uses the standard library only: it has to run on the system interpreter,
before the virtual environment it is about to create exists.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
VENV = BACKEND / ".venv"

MIN_PYTHON = (3, 11)
MIN_NODE_MAJOR = 18

IS_WINDOWS = os.name == "nt"


# ── output ────────────────────────────────────────────────────────────


def _supports_colour() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


C_OK = "\033[32m" if _supports_colour() else ""
C_WARN = "\033[33m" if _supports_colour() else ""
C_ERR = "\033[31m" if _supports_colour() else ""
C_DIM = "\033[90m" if _supports_colour() else ""
C_OFF = "\033[0m" if _supports_colour() else ""

TOTAL_STEPS = 5
_step = 0


def step(message: str) -> None:
    global _step
    _step += 1
    print(f"\n[{_step}/{TOTAL_STEPS}] {message}")


def ok(message: str) -> None:
    print(f"  {C_OK}+{C_OFF} {message}")


def warn(message: str) -> None:
    print(f"  {C_WARN}!{C_OFF} {message}")


def note(message: str) -> None:
    print(f"    {C_DIM}{message}{C_OFF}")


def die(message: str, *, hint: str = "", code: int = 1) -> None:
    print(f"\n{C_ERR}[error]{C_OFF} {message}", file=sys.stderr)
    if hint:
        print(f"        {hint}", file=sys.stderr)
    raise SystemExit(code)


def run(cmd: list[str], *, cwd: Path | None = None, quiet: bool = False) -> None:
    """Run a command, failing the install if it fails."""
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.DEVNULL if quiet else None,
        stderr=None,
    )
    if result.returncode != 0:
        die(
            f"command failed: {' '.join(cmd)}",
            hint="Scroll up for the tool's own error message.",
            code=result.returncode or 1,
        )


def which(name: str) -> str | None:
    """Locate an executable, accepting Windows' .cmd/.bat wrappers."""
    return shutil.which(name)


# ── venv paths ────────────────────────────────────────────────────────


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")


# ── steps ─────────────────────────────────────────────────────────────


def ensure_env_file() -> None:
    env = ROOT / ".env"
    if env.exists():
        ok(".env already present, left as it is")
        return
    example = ROOT / ".env.example"
    if example.exists():
        # .env.example ships ATLAS_ENV=development because it doubles as the
        # template for contributors and CI. The copy an installer writes is a
        # user's configuration, so it says production -- otherwise every fresh
        # install reports "development" on its health endpoint.
        text = example.read_text(encoding="utf-8").replace(
            "ATLAS_ENV=development", "ATLAS_ENV=production", 1
        )
        env.write_text(text, encoding="utf-8")
        ok("created .env from .env.example")
    else:
        # Only the keys the app actually reads. An earlier version of the
        # installer wrote AI_PROVIDER=offline here, which nothing has ever
        # read -- a dead setting in the first file a curious user opens.
        env.write_text(
            "ATLAS_ENV=production\n"
            "ATLAS_HOST=127.0.0.1\n"
            "ATLAS_PORT=8000\n",
            encoding="utf-8",
        )
        ok("created a default .env")


def check_python() -> None:
    if sys.version_info < MIN_PYTHON:
        die(
            f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required, "
            f"but this is {platform.python_version()}.",
            hint="Install a newer Python from https://www.python.org/downloads/",
        )
    ok(f"Python {platform.python_version()} ({sys.executable})")


def create_venv(quiet: bool) -> None:
    if venv_python().exists():
        ok("virtual environment already exists")
    else:
        note(f"creating {VENV.relative_to(ROOT)}")
        run([sys.executable, "-m", "venv", str(VENV)], quiet=quiet)
        if not venv_python().exists():
            die(
                "the virtual environment was created but has no interpreter.",
                hint=f"Delete {VENV} and try again.",
            )
        ok("virtual environment created")

    py = str(venv_python())
    note("installing backend dependencies (this is the slow part)")
    run([py, "-m", "pip", "install", "--upgrade", "pip"], quiet=True)
    run(
        [py, "-m", "pip", "install", "-r", str(BACKEND / "requirements.txt")]
        + (["--quiet"] if quiet else []),
        quiet=False,
    )
    ok("backend dependencies installed")


def build_frontend(quiet: bool) -> None:
    npm = which("npm")
    node = which("node")
    if not node or not npm:
        die(
            "Node.js is required to build the interface.",
            hint=(
                f"Install Node {MIN_NODE_MAJOR} LTS or newer from https://nodejs.org/ "
                "and run this again.\n"
                "        Already have a built frontend/dist? Re-run with --skip-frontend."
            ),
        )

    version = subprocess.run(
        [node, "--version"], capture_output=True, text=True
    ).stdout.strip()
    try:
        major = int(version.lstrip("v").split(".")[0])
        if major < MIN_NODE_MAJOR:
            warn(f"Node {version} is older than the supported {MIN_NODE_MAJOR}; the build may fail")
        else:
            ok(f"Node {version}")
    except ValueError:
        ok(f"Node {version or 'detected'}")

    note("installing npm packages")
    run([npm, "install"] + (["--silent"] if quiet else []), cwd=FRONTEND, quiet=quiet)
    note("building production assets")
    run([npm, "run", "build"], cwd=FRONTEND, quiet=quiet)

    if not (FRONTEND / "dist" / "index.html").exists():
        die("the frontend build reported success but produced no dist/index.html.")
    ok("frontend built")


def init_data() -> None:
    env = {**os.environ, "PYTHONPATH": str(BACKEND)}
    result = subprocess.run(
        [str(venv_python()), "-m", "app.config", "--init-data"],
        cwd=str(BACKEND),
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        die(
            "could not create the local data directory.",
            hint=(result.stderr or result.stdout or "").strip()[:400],
        )
    ok((result.stdout or "data directory ready").strip())


def check_optional_tools() -> None:
    """Report optional extras. None of these block anything."""
    if which("tesseract"):
        ok("Tesseract OCR found -- scanned PDFs and images will be readable")
    else:
        warn("Tesseract OCR not found -- optional, only for scanned documents")
        system = platform.system()
        if system == "Darwin":
            note("install with: brew install tesseract")
        elif system == "Linux":
            if which("apt-get"):
                note("install with: sudo apt-get install -y tesseract-ocr")
            elif which("dnf"):
                note("install with: sudo dnf install -y tesseract")
            else:
                note("see https://github.com/tesseract-ocr/tesseract")
        else:
            note("see https://github.com/UB-Mannheim/tesseract/wiki")
        note("PDF, DOCX and TXT uploads work without it")

    if which("ollama"):
        ok("Ollama found -- you can run chat models locally with no API key")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="install.py", description="Install Atlas and its dependencies."
    )
    parser.add_argument(
        "--skip-frontend",
        action="store_true",
        help="skip npm install and the Vite build (frontend/dist must already exist)",
    )
    parser.add_argument("--quiet", action="store_true", help="less output from pip and npm")
    args = parser.parse_args()

    print("=" * 55)
    print("  Atlas installer")
    print("=" * 55)

    step("Checking Python")
    check_python()

    step("Preparing configuration")
    ensure_env_file()

    step("Setting up the backend")
    create_venv(args.quiet)

    step("Building the interface")
    if args.skip_frontend:
        if (FRONTEND / "dist" / "index.html").exists():
            ok("skipped -- using the existing frontend/dist")
        else:
            die(
                "--skip-frontend was given but frontend/dist/index.html does not exist.",
                hint="Run without --skip-frontend to build it.",
            )
    else:
        build_frontend(args.quiet)

    step("Initialising local storage")
    init_data()
    check_optional_tools()

    launch = "start.bat" if IS_WINDOWS else "./start.sh"
    print()
    print("=" * 55)
    print(f"  {C_OK}Atlas is installed.{C_OFF}")
    print("=" * 55)
    print()
    print(f"  Start it with:  {launch}")
    print("                  (or: python start.py)")
    print()
    print("  Document upload and search work straight away -- embeddings run")
    print("  on this machine and need no API key. For the AI tutor, quizzes")
    print("  and roadmaps, add a chat provider key on the Settings page.")
    print()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        raise SystemExit(130)
