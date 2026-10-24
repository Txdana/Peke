"""Peke MCP Run Store (~/.peke/runs/<run_id>/)."""

import json
import os
import random
import shutil
import string
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def get_peke_dir() -> Path:
    """Return canonical ~/.peke directory or PEKE_HOME if set."""
    home = os.getenv("PEKE_HOME")
    if home and home.strip():
        return Path(home).expanduser()
    return Path.home() / ".peke"


def get_runs_dir() -> Path:
    """Return run storage directory ~/.peke/runs."""
    d = get_peke_dir() / "runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def generate_run_id() -> str:
    """Generate time-sortable unique run ID."""
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%d_%H%M%S_%f")
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"{ts}_{rand}"


def prune_runs(max_runs: int = 50, max_bytes: int = 500 * 1024 * 1024) -> int:
    """Prune oldest runs if run count or total size exceeds limits."""
    runs_dir = get_runs_dir()
    if not runs_dir.is_dir():
        return 0

    run_dirs: list[Path] = [p for p in runs_dir.iterdir() if p.is_dir()]
    run_dirs.sort(key=lambda p: p.name, reverse=True)  # Newest first

    pruned = 0
    # Keep up to max_runs
    if len(run_dirs) > max_runs:
        to_remove = run_dirs[max_runs:]
        for rdir in to_remove:
            try:
                shutil.rmtree(rdir, ignore_errors=True)
                pruned += 1
            except OSError:
                pass
        run_dirs = run_dirs[:max_runs]

    # Calculate total size and prune if over max_bytes
    def dir_size(path: Path) -> int:
        total = 0
        try:
            for p in path.rglob("*"):
                if p.is_file():
                    total += p.stat().st_size
        except OSError:
            pass
        return total

    total_size = sum(dir_size(p) for p in run_dirs)
    while total_size > max_bytes and len(run_dirs) > 1:
        oldest = run_dirs.pop()  # Pop the oldest
        sz = dir_size(oldest)
        try:
            shutil.rmtree(oldest, ignore_errors=True)
            pruned += 1
            total_size -= sz
        except OSError:
            pass

    return pruned


class RunStore:
    """Manages files within a single run folder ~/.peke/runs/<run_id>/."""

    def __init__(self, run_id: str | None = None, tool_name: str = "unknown") -> None:
        self.run_id = run_id or generate_run_id()
        self.dir = get_runs_dir() / self.run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.start_time = time.monotonic()
        self.meta: dict[str, Any] = {
            "run_id": self.run_id,
            "tool": tool_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
            "content_file": None,
            "records_file": None,
            "endpoints_file": None,
        }
        self._write_meta()

    def _write_meta(self) -> None:
        meta_path = self.dir / "meta.json"
        try:
            meta_path.write_text(json.dumps(self.meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except OSError:
            pass

    def save_content(self, content: str, content_type: str = "text/plain", ext: str = "txt") -> str:
        filename = f"content.{ext}"
        filepath = self.dir / filename
        try:
            filepath.write_text(content, encoding="utf-8")
            self.meta["content_file"] = filename
            self.meta["content_type"] = content_type
            self.meta["content_length"] = len(content)
            self._write_meta()
        except OSError:
            pass
        return filename

    def save_records(self, records: list[dict[str, Any]]) -> str:
        filename = "records.json"
        filepath = self.dir / filename
        try:
            filepath.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            self.meta["records_file"] = filename
            self.meta["record_count"] = len(records)
            self._write_meta()
        except OSError:
            pass
        return filename

    def save_endpoints(self, endpoints: list[dict[str, Any]]) -> str:
        filename = "endpoints.json"
        filepath = self.dir / filename
        try:
            filepath.write_text(json.dumps(endpoints, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            self.meta["endpoints_file"] = filename
            self.meta["endpoint_count"] = len(endpoints)
            self._write_meta()
        except OSError:
            pass
        return filename

    def add_event(self, event: dict[str, Any]) -> None:
        filepath = self.dir / "events.jsonl"
        try:
            with filepath.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def finish(self, status: str = "ok", meta_extra: dict[str, Any] | None = None) -> None:
        elapsed_ms = int((time.monotonic() - self.start_time) * 1000)
        self.meta["status"] = status
        self.meta["elapsed_ms"] = elapsed_ms
        if meta_extra:
            self.meta.update(meta_extra)
        self._write_meta()


def list_runs(limit: int = 50) -> list[dict[str, Any]]:
    """Return list of run metadata dicts."""
    runs_dir = get_runs_dir()
    if not runs_dir.is_dir():
        return []

    res = []
    run_dirs = [p for p in runs_dir.iterdir() if p.is_dir()]
    run_dirs.sort(key=lambda p: p.name, reverse=True)
    for rdir in run_dirs[:limit]:
        meta_file = rdir / "meta.json"
        if meta_file.is_file():
            try:
                res.append(json.loads(meta_file.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                pass
    return res


def get_run_part(run_id: str, part: str = "meta", offset: int = 0, limit: int = 20000) -> tuple[Any, bool, int | None]:
    """Get part of a stored run.

    returns: (data, truncated, next_offset)
    """
    runs_dir = get_runs_dir()
    rdir = runs_dir / run_id
    if not rdir.is_dir():
        raise FileNotFoundError(f"Run {run_id} not found")

    if part == "meta":
        meta_file = rdir / "meta.json"
        if not meta_file.is_file():
            raise FileNotFoundError(f"Run {run_id} has no meta.json")
        data = json.loads(meta_file.read_text(encoding="utf-8"))
        return data, False, None

    elif part == "content":
        content_file = None
        for cand in ("content.html", "content.txt", "content.json"):
            if (rdir / cand).is_file():
                content_file = rdir / cand
                break
        if not content_file:
            raise FileNotFoundError(f"Run {run_id} has no content artifact")

        text = content_file.read_text(encoding="utf-8")
        sliced = text[offset : offset + limit]
        truncated = (offset + limit) < len(text)
        next_offset = (offset + limit) if truncated else None
        return sliced, truncated, next_offset

    elif part in ("records", "endpoints"):
        pfile = rdir / f"{part}.json"
        if not pfile.is_file():
            return [], False, None
        records = json.loads(pfile.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            return records, False, None
        sliced = records[offset : offset + limit]
        truncated = (offset + limit) < len(records)
        next_offset = (offset + limit) if truncated else None
        return sliced, truncated, next_offset

    elif part == "events":
        pfile = rdir / "events.jsonl"
        if not pfile.is_file():
            return [], False, None
        lines = pfile.read_text(encoding="utf-8").strip().splitlines()
        events = []
        for line in lines:
            if line.strip():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        sliced = events[offset : offset + limit]
        truncated = (offset + limit) < len(events)
        next_offset = (offset + limit) if truncated else None
        return sliced, truncated, next_offset

    else:
        raise ValueError(f"Unknown run part: {part}")
