"""Unit tests for GitHub Releases auto-updater and installer handoff."""
from unittest.mock import MagicMock, patch

import pytest

from peke.updates import (
    ReleaseClient,
    ReleaseInfo,
    ReleaseUpdater,
    UpdateError,
    check_for_updates,
)


def test_release_client_parse_releases(monkeypatch):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {
            "tag_name": "v0.3.0",
            "prerelease": False,
            "draft": False,
            "html_url": "https://github.com/Txdana/Peke/releases/tag/v0.3.0",
            "body": "Release 0.3.0 notes",
            "published_at": "2026-10-25T12:00:00Z",
            "assets": [
                {"name": "peke-0.3.0-py3-none-any.whl", "browser_download_url": "https://github.com/Txdana/Peke/peke.whl"},
                {"name": "SHA256SUMS", "browser_download_url": "https://github.com/Txdana/Peke/SHA256SUMS"},
                {"name": "requirements-hashed.txt", "browser_download_url": "https://github.com/Txdana/Peke/requirements.txt"},
            ],
        }
    ]

    with patch("httpx.Client.get", return_value=mock_resp):
        client = ReleaseClient()
        releases = client.fetch_releases(force_refresh=True)
        assert len(releases) == 1
        assert releases[0].version == "0.3.0"
        assert releases[0].wheel_name == "peke-0.3.0-py3-none-any.whl"


def test_check_for_updates_available(monkeypatch):
    mock_release = ReleaseInfo(
        version="0.9.0",
        tag_name="v0.9.0",
        prerelease=False,
        draft=False,
        html_url="https://github.com/Txdana/Peke/releases/tag/v0.9.0",
        body="Future release",
        published_at="2026-12-01",
        wheel_name="peke-0.9.0-py3-none-any.whl",
        wheel_url="http://example.com/wheel",
        sums_url="http://example.com/sums",
        requirements_url="http://example.com/reqs",
    )

    with patch("peke.updates.checker.ReleaseClient.get_latest_release", return_value=mock_release):
        result = check_for_updates(channel="stable")
        assert result.update_available is True
        assert result.latest_version == "0.9.0"


def test_updater_verification_failure(tmp_path):
    release = ReleaseInfo(
        version="0.3.0",
        tag_name="v0.3.0",
        prerelease=False,
        draft=False,
        html_url="",
        body="",
        published_at="",
        wheel_name="peke-0.3.0-py3-none-any.whl",
        wheel_url="http://example.com/wheel.whl",
        sums_url="http://example.com/SHA256SUMS",
        requirements_url="http://example.com/req.txt",
    )

    mock_sums = MagicMock()
    mock_sums.status_code = 200
    mock_sums.text = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  peke-0.3.0-py3-none-any.whl\ne3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  requirements-hashed.txt"

    mock_wheel = MagicMock()
    mock_wheel.status_code = 200
    mock_wheel.content = b"corrupted content mismatching hash"

    def _get(url, **kwargs):
        if "SHA256SUMS" in url:
            return mock_sums
        return mock_wheel

    with patch("httpx.Client.get", side_effect=_get):
        updater = ReleaseUpdater(release)
        with pytest.raises(UpdateError, match="SHA-256 hash mismatch"):
            updater.download_and_verify(tmp_path)
