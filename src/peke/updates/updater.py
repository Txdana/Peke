"""Updater module for downloading and verifying release artifacts."""
import hashlib
import logging
import re
from collections.abc import Callable
from pathlib import Path

import httpx

from peke.updates.release_client import ReleaseInfo

logger = logging.getLogger(__name__)


class UpdateError(Exception):
    """Update download or verification error."""


def verify_sha256(file_path: Path, expected_hash: str) -> bool:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    actual_hash = hasher.hexdigest().lower()
    return actual_hash == expected_hash.lower().strip()


def parse_manifest_hash(manifest_text: str, filename: str) -> str | None:
    escaped_name = re.escape(filename)
    pattern = re.compile(r"^([a-fA-F0-9]{64})\s+\*?" + escaped_name + r"$", re.MULTILINE)
    match = pattern.search(manifest_text)
    if match:
        return match.group(1)
    return None


class ReleaseUpdater:
    def __init__(self, release: ReleaseInfo) -> None:
        self.release = release

    def download_and_verify(
        self,
        dest_dir: Path,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> tuple[Path, Path]:
        """Download wheel, requirements, and SHA256SUMS manifest into dest_dir and verify hashes."""
        dest_dir.mkdir(parents=True, exist_ok=True)

        wheel_path = dest_dir / self.release.wheel_name
        req_path = dest_dir / "requirements-hashed.txt"
        sums_path = dest_dir / "SHA256SUMS"

        # Download assets
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            # 1. Download SHA256SUMS
            sums_resp = client.get(self.release.sums_url)
            if sums_resp.status_code != 200:
                raise UpdateError(f"Failed to download SHA256SUMS manifest (HTTP {sums_resp.status_code})")
            sums_text = sums_resp.text
            sums_path.write_text(sums_text, encoding="utf-8")

            # 2. Download wheel
            wheel_hash = parse_manifest_hash(sums_text, self.release.wheel_name)
            if not wheel_hash:
                raise UpdateError(f"No unique SHA-256 hash found in manifest for {self.release.wheel_name}")

            wheel_resp = client.get(self.release.wheel_url)
            if wheel_resp.status_code != 200:
                raise UpdateError(f"Failed to download wheel (HTTP {wheel_resp.status_code})")
            wheel_path.write_bytes(wheel_resp.content)

            if not verify_sha256(wheel_path, wheel_hash):
                wheel_path.unlink(missing_ok=True)
                raise UpdateError(f"SHA-256 hash mismatch for {self.release.wheel_name}")

            # 3. Download requirements
            req_hash = parse_manifest_hash(sums_text, "requirements-hashed.txt")
            if not req_hash:
                raise UpdateError("No unique SHA-256 hash found in manifest for requirements-hashed.txt")

            req_resp = client.get(self.release.requirements_url)
            if req_resp.status_code != 200:
                raise UpdateError(f"Failed to download requirements file (HTTP {req_resp.status_code})")
            req_path.write_bytes(req_resp.content)

            if not verify_sha256(req_path, req_hash):
                req_path.unlink(missing_ok=True)
                raise UpdateError("SHA-256 hash mismatch for requirements-hashed.txt")

        logger.info("Successfully downloaded and verified update artifacts for Peke %s", self.release.version)
        return wheel_path, req_path
