"""Update management package for Peke desktop application."""
from peke.updates.checker import UpdateCheckResult, check_for_updates
from peke.updates.installer_handoff import perform_pipx_upgrade
from peke.updates.release_client import ReleaseClient, ReleaseClientError, ReleaseInfo
from peke.updates.updater import ReleaseUpdater, UpdateError

__all__ = [
    "ReleaseClient",
    "ReleaseClientError",
    "ReleaseInfo",
    "UpdateCheckResult",
    "check_for_updates",
    "ReleaseUpdater",
    "UpdateError",
    "perform_pipx_upgrade",
]
