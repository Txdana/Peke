"""Update checker for comparing installed and published releases."""
from dataclasses import dataclass

from packaging.version import Version

from peke import __version__
from peke.updates.release_client import ReleaseClient, ReleaseClientError, ReleaseInfo


@dataclass
class UpdateCheckResult:
    update_available: bool
    current_version: str
    latest_version: str
    latest_release: ReleaseInfo | None
    message: str


def check_for_updates(channel: str = "stable", force_refresh: bool = False) -> UpdateCheckResult:
    """Check GitHub Releases for a newer version of Peke."""
    current_ver_str = __version__
    try:
        client = ReleaseClient()
        latest = client.get_latest_release(channel=channel)
        if not latest:
            return UpdateCheckResult(
                update_available=False,
                current_version=current_ver_str,
                latest_version=current_ver_str,
                latest_release=None,
                message="Peke is up to date (no remote release found).",
            )

        current_ver = Version(current_ver_str)
        latest_ver = Version(latest.version)

        if latest_ver > current_ver:
            return UpdateCheckResult(
                update_available=True,
                current_version=current_ver_str,
                latest_version=latest.version,
                latest_release=latest,
                message=f"Update available: {latest.version} (current: {current_ver_str}).",
            )
        return UpdateCheckResult(
            update_available=False,
            current_version=current_ver_str,
            latest_version=latest.version,
            latest_release=latest,
            message="Peke is up to date.",
        )
    except ReleaseClientError as exc:
        return UpdateCheckResult(
            update_available=False,
            current_version=current_ver_str,
            latest_version=current_ver_str,
            latest_release=None,
            message=f"Update check failed: {exc}",
        )
