"""Secret management using keyring with restricted permissions file fallback."""
import logging
import os
from pathlib import Path
from typing import Any

import platformdirs

logger = logging.getLogger(__name__)

SERVICE_NAME = "PekeWorkbench"


def _secrets_toml_path() -> Path:
    return Path(platformdirs.user_config_dir("peke", "Peke")) / "secrets.toml"


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
    if path.is_file():
        try:
            import tomllib

            data = tomllib.loads(path.read_text(encoding="utf-8"))
            val = data.get(key)
            if isinstance(val, str):
                return val
        except Exception as exc:
            logger.debug("Reading secrets.toml failed: %s", exc)

    return None


def set_secret(key: str, value: str) -> None:
    """Save secret to keyring, falling back to ~/.peke/secrets.toml with 0600 permissions."""
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
        path.parent.mkdir(parents=True, exist_ok=True)
        existing: dict[str, Any] = {}
        if path.is_file():
            try:
                import tomllib

                existing = tomllib.loads(path.read_text(encoding="utf-8"))
            except Exception:
                existing = {}
        existing[key] = value

        import tomli_w

        content = tomli_w.dumps(existing)
        path.write_text(content, encoding="utf-8")
        if os.name != "nt":
            path.chmod(0o600)
            path.parent.chmod(0o700)
        logger.info("Saved secret %s to file fallback %s (0600 permissions)", key, path)


def delete_secret(key: str) -> None:
    """Delete a secret from keyring and file fallback."""
    try:
        import keyring

        keyring.delete_password(SERVICE_NAME, key)
    except Exception:
        pass

    path = _secrets_toml_path()
    if path.is_file():
        try:
            import tomllib

            data = tomllib.loads(path.read_text(encoding="utf-8"))
            if key in data:
                del data[key]
                import tomli_w

                path.write_text(tomli_w.dumps(data), encoding="utf-8")
                if os.name != "nt":
                    path.chmod(0o600)
        except Exception:
            pass
