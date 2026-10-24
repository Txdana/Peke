"""Unit tests for deep discovery sub-agent orchestration."""
import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from peke.agents import AuthAgent, BundleAgent, Orchestrator
from peke.cli import app
from peke.config import Settings

runner = CliRunner()


def test_bundle_agent_analysis():
    ba = BundleAgent()
    html = '<html><script>fetch("/api/v1/users")</script>Authorization: Bearer test</html>'
    res = ba.analyze(html, "http://example.com", Settings(model_path=None))
    assert any(e["path"] == "/api/v1/users" for e in res.endpoints)
    assert "authorization" in res.secret_headers


def test_auth_agent_redaction():
    aa = AuthAgent()
    headers = {"Authorization": "Bearer secret_jwt_token_value_12345", "X-Custom": "public"}
    res = aa.analyze(headers, reveal_secrets=False)

    token = next(t for t in res.tokens if t["name"] == "Authorization")
    assert token["redacted"] is True
    assert "REDACTED" in token["value"]
    assert "secret_jwt_token_value_12345" not in token["value"]

    res_revealed = aa.analyze(headers, reveal_secrets=True)
    token_revealed = next(t for t in res_revealed.tokens if t["name"] == "Authorization")
    assert token_revealed["redacted"] is False
    assert token_revealed["value"] == "Bearer secret_jwt_token_value_12345"


def test_orchestrator_run_reconnaissance(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    events = []
    settings = Settings(model_path=None)

    mock_fetch_res = MagicMock()
    mock_fetch_res.text = "<html>/api/v2/items</html>"
    mock_fetch_res.content_type = "text/html"
    mock_fetch_res.status = 200

    with patch("peke.agents.network_agent.fetch", return_value=mock_fetch_res), \
         patch("peke.agents.orchestrator.fetch", return_value=mock_fetch_res), \
         patch("peke.agents.bundle_agent.run_rea", return_value=[]):

        orchestrator = Orchestrator(settings=settings, on_event=lambda e: events.append(e))
        res = orchestrator.run_reconnaissance("http://example.com")

        assert res.ok is True
        assert len(res.run_id) > 0
        assert any(e.stage == "subagent:bundle" for e in events)
        assert any(e.stage == "subagent:network" for e in events)
        assert any(e.stage == "subagent:auth" for e in events)

        run_file = tmp_path / ".peke" / "runs" / res.run_id / "subagents.json"
        assert run_file.is_file()
        run_data = json.loads(run_file.read_text(encoding="utf-8"))
        assert run_data["run_id"] == res.run_id


def test_orchestrator_cancellation(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    settings = Settings(model_path=None)

    orchestrator = Orchestrator(settings=settings)
    res = orchestrator.run_reconnaissance("http://example.com", cancel_check=lambda: True)
    assert res.ok is False
    assert "Cancelled" in str(res.error)


def test_cli_discover_deep(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    mock_fetch_res = MagicMock()
    mock_fetch_res.text = "<html>/api/v1/test</html>"
    mock_fetch_res.content_type = "text/html"
    mock_fetch_res.status = 200

    with patch("peke.agents.network_agent.fetch", return_value=mock_fetch_res), \
         patch("peke.agents.orchestrator.fetch", return_value=mock_fetch_res), \
         patch("peke.agents.bundle_agent.run_rea", return_value=[]):

        result = runner.invoke(app, ["discover", "--deep", "http://example.com", "--out", str(tmp_path / "out.yaml")])
        assert result.exit_code == 0
        assert "Deep discovery completed" in result.output
        assert (tmp_path / "out.yaml").is_file()
