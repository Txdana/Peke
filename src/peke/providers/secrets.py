"""Secret management using keyring with a private, atomic TOML file fallback."""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import platformdirs

logger = logging.getLogger(__name__)

SERVICE_NAME = "PekeWorkbench"


def _secrets_toml_path() -> Path:
    return Path(platformdirs.user_config_dir("peke", "Peke")) / "secrets.toml"


def _prepare_secrets_path(path: Path) -> None:
    """Secure the parent first and reject unsafe filesystem objects before I/O."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        if path.parent.is_symlink():
            raise OSError("Refusing to use a symbolic link as the secrets directory")
        path.parent.chmod(0o700)
    if path.is_symlink():
        raise OSError("Refusing to follow a symbolic link for the secrets file")
    if path.exists() and not path.is_file():
        raise OSError("Secrets path exists but is not a regular file")


def _write_secrets_file(path: Path, content: str) -> None:
    """Atomically replace the secret file without opening a predictable temp path."""
    _prepare_secrets_path(path)
    temporary: Path | None = None
    try:
        fd, temporary_name = tempfile.mkstemp(prefix="secrets.toml.", suffix=".tmp", dir=path.parent)
        temporary = Path(temporary_name)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        if os.name != "nt":
            temporary.chmod(0o600)
        os.replace(temporary, path)
    except OSError:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def get_secret(key: str) -> str | None:
    """Retrieve secret from keyring or secrets.toml, returning None if not found."""
    try:
        import keyring

        val = keyring.get_password(SERVICE_NAME, key)
        if val is not None:
            return val
    except Exception as exc:
        logger.debug("Keyring access failed for %s: %s", key, exc)

    path = _secrets_toml_path()
    if path.is_symlink():
        logger.warning("Ignoring symbolic-link secrets file %s", path)
        return None
    if path.is_file():
        try:
            from peke.toml_compat import tomllib

            data = tomllib.loads(path.read_text(encoding="utf-8"))
            val = data.get(key)
            if isinstance(val, str):
                return val
        except Exception as exc:
            logger.debug("Reading secrets.toml failed: %s", exc)

    return None


def set_secret(key: str, value: str) -> None:
    """Save to the system keyring, falling back to a 0600 per-user TOML file."""
    keyring_ok = False
    try:
        import keyring

        backend = keyring.get_keyring()
        if type(backend).__name__ != "FailKeyring":
            keyring.set_password(SERVICE_NAME, key, value)
            keyring_ok = True
    except Exception as exc:
        logger.debug("Keyring set_password failed for %s: %s", key, exc)

    if not keyring_ok:
        path = _secrets_toml_path()
        _prepare_secrets_path(path)
        existing: dict[str, Any] = {}
        if path.is_file():
            try:
                from peke.toml_compat import tomllib

                existing = tomllib.loads(path.read_text(encoding="utf-8"))
            except Exception:
                existing = {}
        existing[key] = value

        import tomli_w

        _write_secrets_file(path, tomli_w.dumps(existing))
        logger.info("Saved secret %s to file fallback %s (0600 permissions)", key, path)


def delete_secret(key: str) -> None:
    """Delete a secret from keyring and the private TOML fallback if present."""
    try:
        import keyring

        keyring.delete_password(SERVICE_NAME, key)
    except Exception:
        pass

    path = _secrets_toml_path()
    if path.is_symlink():
        logger.warning("Refusing to modify symbolic-link secrets file %s", path)
        return
    if path.is_file():
        try:
            from peke.toml_compat import tomllib

            data = tomllib.loads(path.read_text(encoding="utf-8"))
            if key in data:
                del data[key]
                import tomli_w

                _write_secrets_file(path, tomli_w.dumps(data))
        except Exception as exc:
            logger.warning("Could not remove secret %s from file fallback: %s", key, exc)
