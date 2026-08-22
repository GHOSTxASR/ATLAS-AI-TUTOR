from __future__ import annotations

import argparse
import os
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.utils.env_utils import load_dotenv_file


APP_NAME = "LearningOS"
DEFAULT_VERSION = "0.1.0"


@dataclass(frozen=True)
class AppSettings:
    name: str = APP_NAME
    version: str = DEFAULT_VERSION
    environment: str = "development"
    data_dir: str = ""


@dataclass(frozen=True)
class ServerSettings:
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "info"


@dataclass(frozen=True)
class ModelSettings:
    provider: str = "openai"
    chat_model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"
    temperature: float = 0.7
    max_tokens: int = 4096
    context_window: int = 128000
    # "auto" uses the provider's real embeddings API. "hash" substitutes
    # deterministic pseudo-vectors for offline development and tests; it must
    # be requested explicitly because those vectors carry no meaning and make
    # semantic search return arbitrary results.
    embedding_backend: str = "auto"


@dataclass(frozen=True)
class IngestionSettings:
    max_file_size_mb: int = 50
    ocr_language: str = "eng"
    tesseract_path: str = ""


@dataclass(frozen=True)
class PathSettings:
    data_dir: Path
    sqlite_dir: Path
    chroma_dir: Path
    graph_dir: Path
    profiles_dir: Path
    config_dir: Path
    logs_dir: Path
    backups_dir: Path
    settings_file: Path
    secrets_file: Path


@dataclass(frozen=True)
class Settings:
    app: AppSettings
    server: ServerSettings
    model: ModelSettings
    paths: PathSettings
    ingestion: IngestionSettings


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_data_dir() -> Path:
    return Path.home() / ".learningos"


def _read_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _setting(raw: dict[str, Any], section: str, key: str, default: Any) -> Any:
    return raw.get(section, {}).get(key, default)


def _env(name: str, default: Any) -> Any:
    value = os.getenv(name)
    return default if value is None or value == "" else value


def _int_env(name: str, default: int) -> int:
    value = _env(name, default)
    return int(value)


def _float_env(name: str, default: float) -> float:
    value = _env(name, default)
    return float(value)


def build_paths(app_settings: AppSettings) -> PathSettings:
    configured = os.getenv("LEARNINGOS_DATA_DIR") or app_settings.data_dir
    data_dir = Path(configured).expanduser() if configured else default_data_dir()
    data_dir = data_dir.resolve()
    return PathSettings(
        data_dir=data_dir,
        sqlite_dir=data_dir / "data" / "sqlite",
        chroma_dir=data_dir / "data" / "chroma",
        graph_dir=data_dir / "data" / "graph",
        profiles_dir=data_dir / "profiles",
        config_dir=data_dir / "config",
        logs_dir=data_dir / "logs",
        backups_dir=data_dir / "backups",
        settings_file=data_dir / "config" / "settings.toml",
        secrets_file=data_dir / "config" / "secrets.enc",
    )


def load_settings(config_path: Path | None = None) -> Settings:
    load_dotenv_file(project_root() / ".env")

    env_data_dir = os.getenv("LEARNINGOS_DATA_DIR", "")
    bootstrap_data_dir = Path(env_data_dir).expanduser() if env_data_dir else None
    default_settings_file = (
        bootstrap_data_dir / "config" / "settings.toml"
        if bootstrap_data_dir is not None
        else default_data_dir() / "config" / "settings.toml"
    )
    raw = _read_toml(config_path or default_settings_file)

    app = AppSettings(
        name=str(_setting(raw, "app", "name", APP_NAME)),
        version=str(_setting(raw, "app", "version", DEFAULT_VERSION)),
        environment=str(_env("LEARNINGOS_ENV", _setting(raw, "app", "environment", "development"))),
        data_dir=str(_env("LEARNINGOS_DATA_DIR", _setting(raw, "app", "data_dir", ""))),
    )
    server = ServerSettings(
        host=str(_env("LEARNINGOS_HOST", _setting(raw, "server", "host", "127.0.0.1"))),
        port=_int_env("LEARNINGOS_PORT", int(_setting(raw, "server", "port", 8000))),
        log_level=str(_env("LEARNINGOS_LOG_LEVEL", _setting(raw, "server", "log_level", "info"))),
    )
    model = ModelSettings(
        provider=str(_env("LEARNINGOS_MODEL_PROVIDER", _setting(raw, "model", "provider", "openai"))),
        chat_model=str(_env("LEARNINGOS_CHAT_MODEL", _setting(raw, "model", "chat_model", "gpt-4o"))),
        embedding_model=str(
            _env("LEARNINGOS_EMBEDDING_MODEL", _setting(raw, "model", "embedding_model", "text-embedding-3-small"))
        ),
        temperature=_float_env("LEARNINGOS_TEMPERATURE", float(_setting(raw, "model", "temperature", 0.7))),
        max_tokens=_int_env("LEARNINGOS_MAX_TOKENS", int(_setting(raw, "model", "max_tokens", 4096))),
        context_window=_int_env(
            "LEARNINGOS_CONTEXT_WINDOW",
            int(_setting(raw, "model", "context_window", 128000)),
        ),
        embedding_backend=str(
            _env("LEARNINGOS_EMBEDDING_BACKEND", _setting(raw, "model", "embedding_backend", "auto"))
        ).strip().lower(),
    )
    ingestion = IngestionSettings(
        max_file_size_mb=_int_env(
            "LEARNINGOS_MAX_FILE_SIZE_MB", int(_setting(raw, "ingestion", "max_file_size_mb", 50))
        ),
        ocr_language=str(
            _env("LEARNINGOS_OCR_LANGUAGE", _setting(raw, "ingestion", "ocr_language", "eng"))
        ),
        tesseract_path=str(
            _env("LEARNINGOS_TESSERACT_PATH", _setting(raw, "ingestion", "tesseract_path", ""))
        ),
    )
    return Settings(app=app, server=server, model=model, paths=build_paths(app), ingestion=ingestion)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def default_settings_toml(settings: Settings) -> str:
    return f"""[app]
name = "{settings.app.name}"
version = "{settings.app.version}"
environment = "{settings.app.environment}"
data_dir = "{settings.paths.data_dir.as_posix()}"

[server]
host = "{settings.server.host}"
port = {settings.server.port}
log_level = "{settings.server.log_level}"

[model]
provider = "{settings.model.provider}"
chat_model = "{settings.model.chat_model}"
embedding_model = "{settings.model.embedding_model}"
temperature = {settings.model.temperature}
max_tokens = {settings.model.max_tokens}
context_window = {settings.model.context_window}

[ingestion]
max_file_size_mb = {settings.ingestion.max_file_size_mb}
ocr_language = "{settings.ingestion.ocr_language}"
tesseract_path = "{settings.ingestion.tesseract_path}"
"""


def ensure_data_directories(settings: Settings | None = None) -> None:
    active = settings or get_settings()
    for path in (
        active.paths.sqlite_dir,
        active.paths.chroma_dir,
        active.paths.graph_dir,
        active.paths.profiles_dir,
        active.paths.config_dir,
        active.paths.logs_dir,
        active.paths.backups_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
    if not active.paths.settings_file.exists():
        active.paths.settings_file.write_text(default_settings_toml(active), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="LearningOS configuration utilities")
    parser.add_argument("--init-data", action="store_true", help="Create local data directories and settings.toml")
    args = parser.parse_args()
    if args.init_data:
        ensure_data_directories()
        print(f"Initialized data directory: {get_settings().paths.data_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
