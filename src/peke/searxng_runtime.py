"""Run the bundled SearXNG server as a private, per-user local process.

No Docker daemon, external Python installation, or remote SearXNG service is
needed after Peke's normal Python/pipx installation. The server is bound to
127.0.0.1 only and uses a per-user generated secret and settings file.
"""
from __future__ import annotations

import atexit
import json
import math
import os
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

from platformdirs import user_config_dir

from peke.search import SearxngClient

BASE_URL = "http://127.0.0.1:8888"
_STARTUP_TIMEOUT = 75.0
_SERVER_PROCESS: subprocess.Popen[bytes] | None = None
_SERVER_LOG: Any = None
_LOG_START_OFFSET = 0
# Serialises start/stop so repeated clicks or concurrent callers cannot spawn duplicates
# or overwrite the handle of the process that actually owns the port.
_LIFECYCLE_LOCK = threading.RLock()


class SearXNGServiceError(RuntimeError):
    """The bundled local SearXNG service could not be started or stopped."""


def _config_dir() -> Path:
    return Path(user_config_dir("peke", "Peke")) / "searxng"


def _settings_file() -> Path:
    return _config_dir() / "settings.yml"


def _state_file() -> Path:
    return _config_dir() / "searxng.state.json"


def _write_settings(token: str = "") -> Path:
    """Create safe local settings; never overwrite a symlink target."""
    path = _settings_file()
    temporary: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            path.parent.chmod(0o700)
        if path.is_symlink():
            raise OSError("settings.yml is a symbolic link; refusing to replace it")
        settings = (
            "use_default_settings: true\n"
            "general:\n"
            f'  instance_name: "Peke Search{" " + token if token else ""}"\n'
            "search:\n"
            "  safe_search: 1\n"
            "  formats:\n"
            "    - html\n"
            "    - json\n"
            "server:\n"
            '  bind_address: "127.0.0.1"\n'
            "  port: 8888\n"
            f'  secret_key: "{secrets.token_hex(32)}"\n'
            "  limiter: false\n"
        )
        fd, temporary_name = tempfile.mkstemp(prefix="settings.yml.", suffix=".tmp", dir=path.parent)
        temporary = Path(temporary_name)
        if os.name != "nt":
            temporary.chmod(0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(settings)
            handle.flush()
            os.fsync(handle.fileno())
        if path.is_symlink():
            raise OSError("settings.yml became a symbolic link; refusing to replace it")
        os.replace(temporary, path)
    except OSError as exc:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise SearXNGServiceError(f"Could not prepare local SearXNG configuration: {exc}") from exc
    return path


def _port_in_use(host: str = "127.0.0.1", port: int = 8888) -> bool:
    """True if something is already listening on the service port."""
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _read_state() -> dict[str, Any] | None:
    try:
        data = json.loads(_state_file().read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("pid"), int) and isinstance(data.get("token"), str):
            return data
    except (OSError, ValueError):
        pass
    return None


def _write_state(pid: int, token: str) -> None:
    try:
        path = _state_file()
        if path.is_symlink():
            return
        path.write_text(json.dumps({"pid": pid, "token": token}), encoding="utf-8")
        if os.name != "nt":
            path.chmod(0o600)
    except OSError:
        pass  # ownership record is best-effort; the in-memory handle still works


def _clear_state() -> None:
    try:
        _state_file().unlink(missing_ok=True)
    except OSError:
        pass


def _answering_token() -> str | None:
    """Per-launch token reported by whatever answers on the service port, if it is ours."""
    try:
        # BASE_URL is hardcoded loopback URL http://127.0.0.1:8888
        with urllib.request.urlopen(BASE_URL + "/config", timeout=1.5) as resp:  # nosec B310
            name = str(json.loads(resp.read(1024 * 1024)).get("instance_name", ""))
    except Exception:
        return None
    prefix = "Peke Search "
    return name[len(prefix):] if name.startswith(prefix) and len(name) > len(prefix) else None


def _adopted_state() -> dict[str, Any] | None:
    """State record for a Peke-launched service from an earlier session, only if it still answers
    with the matching per-launch token. A recycled PID or a foreign program can never match."""
    state = _read_state()
    if state is not None and _answering_token() == state["token"]:
        return state
    return None


def _tail_log(limit: int = 5000) -> str:
    """Last part of the log written by the current launch only (never stale earlier runs)."""
    try:
        log_path = _config_dir() / "searxng.log"
        if log_path.is_file():
            size = log_path.stat().st_size
            begin = min(_LOG_START_OFFSET, size)
            with log_path.open("rb") as handle:
                handle.seek(max(begin, size - limit))
                text = handle.read(limit).decode("utf-8", errors="replace").strip()
            if "Address already in use" in text:
                return "Port 8888 on 127.0.0.1 is already in use by another program."
            return text
    except OSError:
        pass
    return ""


def _is_ready(timeout: float = 1.5) -> dict[str, Any]:
    return SearxngClient(BASE_URL, timeout=timeout).status()


def start_local_server(*, startup_timeout: float = _STARTUP_TIMEOUT) -> dict[str, Any]:
    """Launch the bundled SearXNG module and wait for its JSON API."""
    if isinstance(startup_timeout, bool):
        raise SearXNGServiceError("SearXNG startup timeout must be a positive finite number.")
    try:
        timeout = float(startup_timeout)
    except (TypeError, ValueError) as exc:
        raise SearXNGServiceError("SearXNG startup timeout must be a positive finite number.") from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise SearXNGServiceError("SearXNG startup timeout must be a positive finite number.")
    timeout = min(max(5.0, timeout), 300.0)
    with _LIFECYCLE_LOCK:
        return _start_locked(timeout)


def _start_locked(timeout: float) -> dict[str, Any]:
    global _SERVER_PROCESS, _SERVER_LOG, _LOG_START_OFFSET
    if _SERVER_PROCESS is not None and _SERVER_PROCESS.poll() is not None:
        _clear_process_handle()

    # If Peke already owns a running or adopted process, wait for it to be ready
    owned_process = (_SERVER_PROCESS is not None and _SERVER_PROCESS.poll() is None) or _adopted_state() is not None
    if owned_process:
        retry_deadline = time.monotonic() + 5.0
        while time.monotonic() < retry_deadline:
            try:
                status = _is_ready(timeout=1.0)
                if status.get("available"):
                    return {"url": BASE_URL, "already_running": True, "managed_by_peke": True, "status": status}
            except Exception:
                pass
            time.sleep(0.2)

    try:
        status = _is_ready()
        if status.get("available"):
            return {"url": BASE_URL, "already_running": True, "managed_by_peke": False, "status": status}
    except Exception:
        pass

    # Something else may hold the port without being a working SearXNG; say so plainly
    # instead of spawning a process that will only fail to bind.
    if _port_in_use():
        raise SearXNGServiceError(
            "Port 8888 on 127.0.0.1 is already in use by another program that is not a working "
            "SearXNG JSON service. Peke will not stop it; close that program and try again."
        )

    token = secrets.token_hex(8)
    settings_path = _write_settings(token)
    config_dir = settings_path.parent
    log_path = config_dir / "searxng.log"
    try:
        if log_path.is_symlink():
            raise OSError("searxng.log is a symbolic link; refusing to write through it")
        if log_path.exists() and log_path.stat().st_size > 5 * 1024 * 1024:
            try:
                os.replace(log_path, config_dir / "searxng.log.1")
            except OSError:
                log_path.write_bytes(b"")  # rotation blocked (file in use); truncate instead
        _SERVER_LOG = log_path.open("ab", buffering=0)
        _LOG_START_OFFSET = log_path.stat().st_size
        env = os.environ.copy()
        env["SEARXNG_SETTINGS_PATH"] = str(config_dir)
        # Force the local service's network boundary even if the user's shell
        # has SearXNG environment variables intended for another instance.
        env["SEARXNG_BIND_ADDRESS"] = "127.0.0.1"
        env["SEARXNG_PORT"] = "8888"
        env["SEARXNG_LIMITER"] = "false"
        env["SEARXNG_PUBLIC_INSTANCE"] = "false"
        env["SEARXNG_BASE_URL"] = BASE_URL + "/"
        env.pop("SEARXNG_SECRET", None)  # the per-user generated YAML secret is authoritative
        package_root = str(Path(__file__).resolve().parents[1])
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = package_root + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
        env["SEARXNG_DISABLE_ETC_SETTINGS"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        # Windows consoles default to a legacy code page (e.g. cp1252) which breaks SearXNG's
        # text-file reads and non-ASCII log output; force UTF-8 for the child only.
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        # Keep SearXNG's cache databases in a private per-user directory instead of the shared,
        # predictable system temp folder (also avoids stale files from other instances).
        private_tmp = config_dir / "tmp"
        private_tmp.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            private_tmp.chmod(0o700)
        for name in ("TMPDIR", "TEMP", "TMP"):
            env[name] = str(private_tmp)
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        _SERVER_PROCESS = subprocess.Popen(
            [sys.executable, "-m", "searx.webapp"],
            stdin=subprocess.DEVNULL,
            stdout=_SERVER_LOG,
            stderr=subprocess.STDOUT,
            cwd=str(config_dir),
            env=env,
            creationflags=creationflags,
            close_fds=True,
        )
    except (OSError, ValueError) as exc:
        if _SERVER_LOG is not None:
            _SERVER_LOG.close()
            _SERVER_LOG = None
        _SERVER_PROCESS = None
        raise SearXNGServiceError(
            f"Could not launch bundled SearXNG with {sys.executable!r}: {exc}. "
            "Reinstall Peke so its bundled SearXNG files and dependencies are present."
        ) from exc
    pid = getattr(_SERVER_PROCESS, "pid", None)
    if isinstance(pid, int):
        _write_state(pid, token)

    deadline = time.monotonic() + timeout
    last_reason = "server is starting"
    while time.monotonic() < deadline:
        if _SERVER_PROCESS.poll() is not None:
            detail = _tail_log()
            _clear_process_handle()
            _clear_state()
            raise SearXNGServiceError(
                "Bundled SearXNG exited during startup. " + (detail[-3500:] if detail else last_reason)
            )
        try:
            status = _is_ready(timeout=1.0)
            if status.get("available"):
                atexit.register(stop_local_server)
                return {"url": BASE_URL, "already_running": False, "managed_by_peke": True, "status": status}
            last_reason = str(status.get("reason", last_reason))
        except Exception as exc:
            last_reason = str(exc)
        time.sleep(0.5)

    detail = _tail_log()
    _stop_locked()
    raise SearXNGServiceError(
        f"Bundled SearXNG did not become ready at {BASE_URL} within {timeout:g} seconds ({last_reason}). "
        + (detail[-2500:] if detail else "Check that the bundled SearXNG dependencies installed correctly.")
    )


def _clear_process_handle() -> None:
    global _SERVER_PROCESS, _SERVER_LOG
    _SERVER_PROCESS = None
    if _SERVER_LOG is not None:
        try:
            _SERVER_LOG.close()
        except OSError:
            pass
        _SERVER_LOG = None


def stop_local_server() -> dict[str, Any]:
    """Stop only a server Peke launched (this session, or an earlier one proven by its token)."""
    with _LIFECYCLE_LOCK:
        return _stop_locked()


def _stop_locked() -> dict[str, Any]:
    process = _SERVER_PROCESS
    if process is None:
        adopted = _adopted_state()
        if adopted is not None:
            return _stop_adopted(adopted)
        try:
            status = _is_ready(timeout=1.0)
            if status.get("available"):
                return {
                    "stopped": False,
                    "already_stopped": True,
                    "message": "A SearXNG service is responding, but Peke did not launch it; it was left running.",
                }
        except Exception:
            pass
        _clear_state()
        return {"stopped": False, "already_stopped": True, "message": "No Peke-managed SearXNG process is running."}

    if process.poll() is not None:
        _clear_process_handle()
        _clear_state()
        return {"stopped": False, "already_stopped": True, "message": "Bundled SearXNG had already stopped."}

    process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired as exc:
            raise SearXNGServiceError("Bundled SearXNG did not stop after termination; close it from Task Manager.") from exc
    _clear_process_handle()
    _clear_state()
    return {"stopped": True, "already_stopped": False, "message": "Bundled local SearXNG stopped. Its settings and logs were retained."}


def _stop_adopted(state: dict[str, Any]) -> dict[str, Any]:
    """Stop a Peke-launched service left over from a crashed or force-killed earlier session."""
    pid = state["pid"]
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        # POSIX raises ProcessLookupError for a missing pid; Windows raises a generic OSError
        # (WinError 87/5). Either way, if the service no longer answers with our token it is gone.
        if _answering_token() != state["token"]:
            _clear_state()
            return {"stopped": False, "already_stopped": True, "message": "Bundled SearXNG had already stopped."}
        raise SearXNGServiceError(f"Could not stop the earlier bundled SearXNG (pid {pid}): {exc}") from exc
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if _answering_token() != state["token"]:
            _clear_state()
            return {"stopped": True, "already_stopped": False, "message": "Stopped the bundled SearXNG left by an earlier Peke session."}
        time.sleep(0.25)
    raise SearXNGServiceError("The earlier bundled SearXNG did not stop after termination; close it from Task Manager.")


def local_server_status() -> dict[str, Any]:
    """Return local service status without starting the server."""
    process = _SERVER_PROCESS
    running_process = process is not None and process.poll() is None
    try:
        status = _is_ready(timeout=1.5)
    except Exception as exc:
        status = {"available": False, "reason": str(exc), "url": BASE_URL}
    managed = running_process or (bool(status.get("available")) and _adopted_state() is not None)
    return {
        "bundled": True,
        "installed": True,
        "running": bool(status.get("available")),
        "managed_by_peke": managed,
        **status,
    }
