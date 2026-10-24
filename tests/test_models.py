"""Unit tests for managed GGUF model downloader and file manager."""
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from peke.cli import app
from peke.models import ModelManager, ModelManagerError

runner = CliRunner()


def test_model_manager_list_and_activate(tmp_path):
    manager = ModelManager(base_dir=tmp_path)

    fake_file = tmp_path / "custom.gguf"
    fake_file.write_text("dummy model content")

    info = manager.set_active_model(str(fake_file))
    assert info.active is True
    assert info.file == "custom.gguf"

    models = manager.list_models()
    assert len(models) == 1
    assert models[0].active is True


def test_model_manager_download_mock(tmp_path):
    manager = ModelManager(base_dir=tmp_path)

    mock_sibling = MagicMock()
    mock_sibling.rfilename = "Qwen2.5-7B-Instruct-abliterated-Q4_K_M.gguf"
    mock_sibling.size = 100
    mock_sibling.lfs = {"sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}

    mock_info = MagicMock()
    mock_info.siblings = [mock_sibling]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-length": "0"}
    mock_resp.iter_bytes.return_value = [b""]

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_resp

    progress_calls = []

    def _cb(downloaded, total, speed, eta):
        progress_calls.append((downloaded, total))

    with patch("peke.models.manager.HfApi.model_info", return_value=mock_info), \
         patch("httpx.stream", return_value=mock_client):
        info = manager.download_model(progress_callback=_cb)
        assert info.file == "Qwen2.5-7B-Instruct-abliterated-Q4_K_M.gguf"
        assert info.active is True


def test_model_manager_insufficient_disk_space(tmp_path):
    manager = ModelManager(base_dir=tmp_path)

    mock_sibling = MagicMock()
    mock_sibling.rfilename = "large.gguf"
    mock_sibling.size = 10**12  # 1 TB

    mock_info = MagicMock()
    mock_info.siblings = [mock_sibling]

    with patch("peke.models.manager.HfApi.model_info", return_value=mock_info), \
         patch("shutil.disk_usage", return_value=MagicMock(free=1000)):
        with pytest.raises(ModelManagerError, match="Insufficient disk space"):
            manager.download_model(file="large.gguf")


def test_model_manager_gc(tmp_path):
    manager = ModelManager(base_dir=tmp_path)

    f1 = tmp_path / "m1.gguf"
    f2 = tmp_path / "m2.gguf"
    f1.write_text("m1")
    f2.write_text("m2")

    manager.set_active_model(str(f1))
    manager.set_active_model(str(f2))

    removed = manager.gc(keep_last=1)
    assert "m1.gguf" in removed
    assert not f1.exists()
    assert f2.exists()


def test_cli_models_list(tmp_path, monkeypatch):
    monkeypatch.setattr("peke.models.manager.ModelManager._load_manifest", lambda self: {
        "repo/file.gguf": {
            "repo": "testrepo",
            "file": "test.gguf",
            "local_path": str(tmp_path / "test.gguf"),
            "size_bytes": 1048576,
            "active": True,
        }
    })
    (tmp_path / "test.gguf").write_text("fake")

    result = runner.invoke(app, ["models", "list"])
    assert result.exit_code == 0
    assert "test.gguf" in result.output
