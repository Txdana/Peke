"""Managed Hugging Face GGUF model downloader and file manager."""
import hashlib
import json
import logging
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from huggingface_hub import HfApi

logger = logging.getLogger(__name__)

DEFAULT_MODEL_REPO = "richardyoung/Qwen2.5-7B-Instruct-abliterated-GGUF"
DEFAULT_MODEL_FILE = "Qwen2.5-7B-Instruct-abliterated-Q4_K_M.gguf"


@dataclass
class ModelInfo:
    repo: str
    file: str
    local_path: str
    size_bytes: int
    sha256: str | None
    download_time: float
    last_used: float
    active: bool = False


class ModelManagerError(Exception):
    """Model manager operation failure."""


class ModelManager:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or (Path.home() / ".peke" / "models")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.base_dir / "manifest.json"

    def _load_manifest(self) -> dict[str, dict[str, Any]]:
        if not self.manifest_path.is_file():
            return {}
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_manifest(self, manifest: dict[str, dict[str, Any]]) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.manifest_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        tmp.replace(self.manifest_path)

    def list_models(self) -> list[ModelInfo]:
        """Return list of managed models."""
        manifest = self._load_manifest()
        result = []
        for _key, item in manifest.items():
            path = Path(item["local_path"])
            if path.is_file():
                result.append(
                    ModelInfo(
                        repo=item.get("repo", ""),
                        file=item.get("file", ""),
                        local_path=str(path),
                        size_bytes=item.get("size_bytes", path.stat().st_size),
                        sha256=item.get("sha256"),
                        download_time=item.get("download_time", 0.0),
                        last_used=item.get("last_used", 0.0),
                        active=item.get("active", False),
                    )
                )
        return sorted(result, key=lambda m: m.last_used, reverse=True)

    def get_active_model(self) -> ModelInfo | None:
        models = self.list_models()
        for m in models:
            if m.active:
                return m
        return models[0] if models else None

    def set_active_model(self, key_or_path: str) -> ModelInfo:
        manifest = self._load_manifest()
        target_key = None
        for k, v in manifest.items():
            if k == key_or_path or v.get("local_path") == str(Path(key_or_path).resolve()) or v.get("file") == key_or_path:
                target_key = k
                break

        if not target_key:
            path = Path(key_or_path).expanduser().resolve()
            if not path.is_file():
                raise ModelManagerError(f"Model file not found: {key_or_path}")
            target_key = f"custom/{path.name}"
            manifest[target_key] = {
                "repo": "custom",
                "file": path.name,
                "local_path": str(path),
                "size_bytes": path.stat().st_size,
                "sha256": None,
                "download_time": time.time(),
                "last_used": time.time(),
                "active": True,
            }

        now = time.time()
        for k, v in manifest.items():
            v["active"] = (k == target_key)
            if k == target_key:
                v["last_used"] = now

        self._save_manifest(manifest)
        info = manifest[target_key]
        return ModelInfo(
            repo=info["repo"],
            file=info["file"],
            local_path=info["local_path"],
            size_bytes=info["size_bytes"],
            sha256=info.get("sha256"),
            download_time=info.get("download_time", 0.0),
            last_used=now,
            active=True,
        )

    def download_model(
        self,
        repo: str = DEFAULT_MODEL_REPO,
        file: str = DEFAULT_MODEL_FILE,
        progress_callback: Callable[[int, int, float, float], None] | None = None,
    ) -> ModelInfo:
        """Download GGUF model from Hugging Face Hub with resume and space check."""
        target_dir = self.base_dir / repo.replace("/", "_")
        target_dir.mkdir(parents=True, exist_ok=True)
        final_file = target_dir / file
        part_file = target_dir / f"{file}.part"

        api = HfApi()
        try:
            model_info = api.model_info(repo_id=repo, files_metadata=True)
            sibling = next((s for s in model_info.siblings if s.rfilename == file), None)
            expected_size = sibling.size if sibling and hasattr(sibling, "size") and sibling.size else None
            expected_sha256 = sibling.lfs.get("sha256") if sibling and hasattr(sibling, "lfs") and sibling.lfs else None
        except Exception as exc:
            logger.warning("Could not fetch Hugging Face metadata for %s/%s: %s", repo, file, exc)
            expected_size = None
            expected_sha256 = None

        if expected_size:
            usage = shutil.disk_usage(target_dir)
            if usage.free < expected_size + 100 * 1024 * 1024:
                needed_mb = (expected_size - usage.free) / (1024 * 1024)
                raise ModelManagerError(
                    f"Insufficient disk space. Need {expected_size / (1024**3):.2f} GB, "
                    f"free: {usage.free / (1024**3):.2f} GB (short by {needed_mb:.1f} MB)."
                )

        if final_file.is_file():
            size = final_file.stat().st_size
            if not expected_size or size == expected_size:
                return self.set_active_model(f"{repo}/{file}")

        url = f"https://huggingface.co/{repo}/resolve/main/{file}"
        downloaded_bytes = part_file.stat().st_size if part_file.is_file() else 0
        headers = {}
        if downloaded_bytes > 0:
            headers["Range"] = f"bytes={downloaded_bytes}-"

        start_time = time.perf_counter()
        last_time = start_time
        bytes_since_last = 0

        mode = "ab" if downloaded_bytes > 0 else "wb"
        hasher = hashlib.sha256()

        try:
            with httpx.stream("GET", url, headers=headers, follow_redirects=True, timeout=30.0) as resp:
                if resp.status_code not in {200, 206}:
                    raise ModelManagerError(f"HTTP download failed with status {resp.status_code}")

                total_size = expected_size or int(resp.headers.get("content-length", 0)) + downloaded_bytes

                with open(part_file, mode) as f:
                    for chunk in resp.iter_bytes(chunk_size=65536):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded_bytes += len(chunk)
                        bytes_since_last += len(chunk)

                        now = time.perf_counter()
                        elapsed = max(now - last_time, 0.001)
                        if elapsed >= 0.5:
                            speed = bytes_since_last / elapsed
                            eta = (total_size - downloaded_bytes) / speed if (speed > 0 and total_size > downloaded_bytes) else 0.0
                            if progress_callback:
                                progress_callback(downloaded_bytes, total_size, speed, eta)
                            last_time = now
                            bytes_since_last = 0

            part_file.replace(final_file)

            sha256_hex = None
            if expected_sha256:
                with open(final_file, "rb") as f:
                    for chunk in iter(lambda: f.read(1048576), b""):
                        hasher.update(chunk)
                sha256_hex = hasher.hexdigest()
                if sha256_hex.lower() != expected_sha256.lower():
                    final_file.unlink(missing_ok=True)
                    raise ModelManagerError(f"SHA-256 checksum mismatch for downloaded model {file}")

            manifest = self._load_manifest()
            key = f"{repo}/{file}"
            manifest[key] = {
                "repo": repo,
                "file": file,
                "local_path": str(final_file),
                "size_bytes": final_file.stat().st_size,
                "sha256": sha256_hex or expected_sha256,
                "download_time": time.time(),
                "last_used": time.time(),
                "active": True,
            }
            self._save_manifest(manifest)
            return self.set_active_model(key)
        except Exception as exc:
            if isinstance(exc, ModelManagerError):
                raise
            raise ModelManagerError(f"Model download failed for {repo}/{file}: {exc}") from exc

    def remove_model(self, key_or_path: str) -> bool:
        manifest = self._load_manifest()
        target_key = None
        for k, v in manifest.items():
            if k == key_or_path or v.get("file") == key_or_path or v.get("local_path") == str(Path(key_or_path).resolve()):
                target_key = k
                break

        if not target_key or target_key not in manifest:
            return False

        info = manifest[target_key]
        path = Path(info["local_path"])
        if path.is_file():
            path.unlink(missing_ok=True)

        del manifest[target_key]
        self._save_manifest(manifest)
        return True

    def gc(self, keep_last: int = 1) -> list[str]:
        models = self.list_models()
        if len(models) <= keep_last:
            return []

        removed = []
        for m in models[keep_last:]:
            if not m.active:
                key = f"{m.repo}/{m.file}" if m.repo != "custom" else m.file
                if self.remove_model(key):
                    removed.append(m.file)
        return removed
