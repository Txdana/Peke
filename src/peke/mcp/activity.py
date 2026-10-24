"""Peke MCP Activity Logger (~/.peke/activity.jsonl)."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from peke.mcp.runs import get_peke_dir

# Sensitive key pattern for redacting header/token data
SENSITIVE_RE = re.compile(
    r"(authorization|cookie|bearer|token|api[-_]?key|secret|password|credential)",
    re.IGNORECASE,
)


def sanitize_value(key: str, val: Any) -> Any:
    """Redact sensitive header/credential values."""
    if SENSITIVE_RE.search(key):
        return "***"
    if isinstance(val, dict):
        return {k: sanitize_value(k, v) for k, v in val.items()}
    if isinstance(val, list):
        return [sanitize_value(key, item) for item in val]
    return val


def get_activity_log_path() -> Path:
    d = get_peke_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "activity.jsonl"


def extract_host(target: str | None) -> str:
    """Safely extract netloc/host without query strings or credentials."""
    if not target:
        return "local"
    try:
        parsed = urlparse(target)
        if parsed.netloc:
            # Strip port or credentials if present
            host = parsed.netloc.rsplit("@", 1)[-1]
            return host
        if parsed.path and not parsed.scheme:
            return parsed.path.split("/")[0]
    except Exception:
        pass
    return "local"


def rotate_activity_log_if_needed(path: Path, max_bytes: int = 5 * 1024 * 1024) -> None:
    """Rotate activity log at 5 MB."""
    if not path.is_file():
        return
    try:
        if path.stat().st_size >= max_bytes:
            backup = path.with_suffix(".jsonl.1")
            backup.unlink(missing_ok=True)
            path.rename(backup)
    except OSError:
        pass


def log_activity(
    client_info: str | None,
    tool: str,
    target: str | None,
    duration_ms: int,
    status: str,
    run_id: str | None = None,
) -> None:
    """Append entry to ~/.peke/activity.jsonl with redaction."""
    path = get_activity_log_path()
    rotate_activity_log_if_needed(path)

    host = extract_host(target)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "client": client_info or "unknown",
        "tool": tool,
        "target_host": host,
        "duration_ms": duration_ms,
        "status": status,
        "run_id": run_id,
    }

    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def read_activity_log(limit: int = 100) -> list[dict[str, Any]]:
    """Read newest activity entries."""
    path = get_activity_log_path()
    if not path.is_file():
        return []

    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        entries = []
        for line in reversed(lines):
            if line.strip():
                try:
                    entries.append(json.loads(line))
                    if len(entries) >= limit:
                        break
                except json.JSONDecodeError:
                    pass
        return entries
    except OSError:
        return []
