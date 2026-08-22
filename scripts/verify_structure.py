from __future__ import annotations

from pathlib import Path


REQUIRED_PATHS = [
    "backend/app/main.py",
    "backend/app/config.py",
    "frontend/package.json",
    "frontend/src/main.tsx",
    "docs/README.md",
    "profiles/README.md",
    "tests/README.md",
]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    missing = [path for path in REQUIRED_PATHS if not (root / path).exists()]
    if missing:
        for path in missing:
            print(f"missing: {path}")
        return 1
    print("LearningOS structure verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

