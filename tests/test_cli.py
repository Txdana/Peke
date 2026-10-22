"""Tests for Typer CLI commands."""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from peke.cli import app

runner = CliRunner()


@patch("peke.cli.Pipeline")
def test_cli_run_command_success(mock_pipeline_cls, tmp_path):
    mock_pipeline = MagicMock()
    mock_result = MagicMock()
    mock_extraction = MagicMock()
    mock_extraction.json_output = {"title": "CLI Test Article", "content": "CLI Content"}
    mock_result.extraction_result = mock_extraction
    mock_pipeline.run.return_value = mock_result
    mock_pipeline_cls.return_value = mock_pipeline

    out_json_path = tmp_path / "out.json"

    res = runner.invoke(app, ["run", "https://example.com", "-o", str(out_json_path)])
    assert res.exit_code == 0
    assert out_json_path.exists()
    data = json.loads(out_json_path.read_text())
    assert data["title"] == "CLI Test Article"


@patch("peke.cli.Pipeline")
def test_cli_run_command_failing_pipeline(mock_pipeline_cls):
    mock_pipeline = MagicMock()
    mock_result = MagicMock()
    mock_result.extraction_result = None
    mock_pipeline.run.return_value = mock_result
    mock_pipeline_cls.return_value = mock_pipeline

    res = runner.invoke(app, ["run", "https://example.com"])
    assert res.exit_code == 1
    assert "no extracted data was produced" in res.stdout
