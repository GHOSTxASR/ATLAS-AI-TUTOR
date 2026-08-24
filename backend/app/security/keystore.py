from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict

from cryptography.fernet import Fernet, InvalidToken

from app.config import Settings
from app.security.redaction import forget_secret, register_secret

logger = logging.getLogger(__name__)


def restrict_to_current_user(path: Path) -> None:
    """Best-effort: make ``path`` readable only by the current user.

    ``Path.chmod(0o600)`` is a no-op for access control on Windows, which is
    the primary platform here, so fall back to ``icacls`` to strip inherited
    ACLs and grant the current account alone.
    """
    try:
        path.chmod(0o600)
    except OSError:
        pass

    if sys.platform != "win32":
        return

    account = os.environ.get("USERNAME")
    if not account:
        return
    try:
        subprocess.run(
            ["icacls", str(path), "/inheritance:r", "/grant:r", f"{account}:F"],
            check=False,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        # Locking down the file is defence in depth; never block a key write.
        logger.debug("Could not restrict ACLs on %s", path.name, exc_info=True)


class KeyStore:
    """Local, encrypted-at-rest storage for AI provider API keys.

    Keys are encrypted with Fernet (symmetric encryption) before being written
    to ``secrets.enc``. The Fernet key itself lives in a separate file
    (``keystore.key``) next to it, generated on first use. This is the MVP key
    derivation strategy described in ``17_SECURITY_AND_PRIVACY.md``: a
    machine-local stable secret, never transmitted, never logged, never
    included in exports.
    """

    #: icacls is a subprocess; assert the key's ACL once per process.
    _key_acl_checked: bool = False

    def __init__(self, settings: Settings):
        self._secrets_path: Path = settings.paths.secrets_file
        self._key_path: Path = settings.paths.config_dir / "keystore.key"

    def _load_or_create_fernet_key(self) -> bytes:
        self._key_path.parent.mkdir(parents=True, exist_ok=True)
        if self._key_path.exists():
            # Re-assert the ACL on an existing key, not just a new one.
            # Restricting only at creation meant any install made before this
            # hardening kept a key file with inherited permissions forever --
            # the encrypted blob was locked down while the key that opens it
            # was readable by every administrator on the machine. Guarded so
            # this costs one icacls call per process, not one per key read.
            if not KeyStore._key_acl_checked:
                KeyStore._key_acl_checked = True
                restrict_to_current_user(self._key_path)
            return self._key_path.read_bytes().strip()
        key = Fernet.generate_key()
        self._key_path.write_bytes(key)
        KeyStore._key_acl_checked = True
        restrict_to_current_user(self._key_path)
        return key

    def _fernet(self) -> Fernet:
        return Fernet(self._load_or_create_fernet_key())

    def _read_all(self) -> Dict[str, str]:
        if not self._secrets_path.exists():
            return {}
        raw = self._secrets_path.read_bytes()
        if not raw:
            return {}
        try:
            decrypted = self._fernet().decrypt(raw)
            data = json.loads(decrypted.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except (InvalidToken, ValueError, json.JSONDecodeError):
            # Corrupt or unreadable secrets file: fail safe with no keys
            # rather than crashing startup.
            return {}

    def _write_all(self, data: Dict[str, str]) -> None:
        self._secrets_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data).encode("utf-8")
        encrypted = self._fernet().encrypt(payload)
        self._secrets_path.write_bytes(encrypted)
        restrict_to_current_user(self._secrets_path)

    def get(self, provider: str) -> str | None:
        value = self._read_all().get(provider.lower())
        # Registering on read means the redaction layer knows every key this
        # process actually uses, even ones set before it started.
        register_secret(value)
        return value

    def set(self, provider: str, api_key: str) -> None:
        data = self._read_all()
        data[provider.lower()] = api_key
        self._write_all(data)
        register_secret(api_key)

    def delete(self, provider: str) -> None:
        data = self._read_all()
        removed = data.pop(provider.lower(), None)
        if removed is not None:
            self._write_all(data)
            forget_secret(removed)

    def configured_providers(self) -> set[str]:
        return set(self._read_all().keys())
