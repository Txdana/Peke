import json
import sys
from pathlib import Path

import pytest

from peke.config import Settings
from peke.discover import _validate_cdp_endpoint, parse_rea_output, run_rea


def test_parse_recorded_rea_output():
    fixture = Path(__file__).parent / "fixtures" / "rea-output.json"
    hints = parse_rea_output(fixture.read_text(encoding="utf-8"))
    assert len(hints) == 2
    assert hints[0].path == "/api/products"
    assert hints[0].params["limit"] == "20"
    assert hints[0].hidden is True
    assert hints[0].headers["X-Requested-With"] == "XMLHttpRequest"
    assert hints[1].discovered_by == "rea"


def test_parse_official_rea_evidence_envelope():
    evidence = {
        "operation": "analyze_web_bundle",
        "normalized_result": {
            "observations": {
                "endpoints": [
                    {"path": "/api/products", "method": "GET", "confidence": "observed", "mechanism": "fetch"},
                    {"path": "token", "method": "GET", "confidence": "inferred"},
                ]
            }
        },
    }
    hints = parse_rea_output(json.dumps(evidence))
    assert len(hints) == 1
    assert hints[0].path == "/api/products"
    assert "fetch" in hints[0].note
    assert "confidence: observed" in hints[0].note


def test_rea_not_configured_is_optional():
    events = []
    settings = Settings(model_path=None, rea_command=None)
    assert run_rea("https://example.test", settings, events.append) == []
    assert events and events[0].level == "warn"


def test_rea_bad_output_fails_clearly():
    with pytest.raises(ValueError, match="valid JSON"):
        parse_rea_output("not-json")


def test_cdp_endpoint_requires_literal_loopback_and_explicit_port():
    assert _validate_cdp_endpoint("http://127.0.0.1:9222") == "http://127.0.0.1:9222"
    with pytest.raises(ValueError, match="loopback"):
        _validate_cdp_endpoint("http://192.168.1.10:9222")
    with pytest.raises(ValueError, match="explicit-port"):
        _validate_cdp_endpoint("http://127.0.0.1")


def test_rea_cli_lists_targets_then_analyzes_matching_page(tmp_path):
    fake_cli = tmp_path / "fake_rea.py"
    fake_cli.write_text(
        "import json, sys\n"
        "if sys.argv[1] == 'list-browser-targets':\n"
        " print(json.dumps({'normalized_result': {'targets': ["
        "{'target_id': 'page-123', 'url': 'https://example.test/catalog', 'type': 'page'},"
        "{'target_id': 'other-page', 'url': 'https://other.test/', 'type': 'page'}]}}))\n"
        "elif sys.argv[1] == 'analyze-web-bundle':\n"
        " assert sys.argv[2] == 'http://127.0.0.1:9222'\n"
        " assert sys.argv[3] == 'page-123'\n"
        " assert '--json' in sys.argv\n"
        " print(json.dumps({'normalized_result': {'observations': {'endpoints': ["
        "{'path': '/api/items', 'method': 'GET', 'confidence': 'observed'}]}}}))\n"
        "else: raise SystemExit(2)\n",
        encoding="utf-8",
    )
    settings = Settings(model_path=None, rea_command=f'"{sys.executable}" "{fake_cli}"')
    events = []
    hints = run_rea("https://example.test/catalog", settings, events.append)
    assert len(hints) == 1
    assert hints[0].path == "/api/items"
    assert events[-1].level == "ok"


def test_rea_refuses_ambiguous_matching_browser_targets(tmp_path):
    fake_cli = tmp_path / "fake_rea.py"
    fake_cli.write_text(
        "import json, sys\n"
        "print(json.dumps({'normalized_result': {'targets': ["
        "{'target_id': 'page-a', 'url': 'https://example.test/catalog?x=1', 'type': 'page'},"
        "{'target_id': 'page-b', 'url': 'https://example.test/catalog?x=2', 'type': 'page'}]}}))\n",
        encoding="utf-8",
    )
    settings = Settings(model_path=None, rea_command=f'"{sys.executable}" "{fake_cli}"')
    events = []
    assert run_rea("https://example.test/catalog", settings, events.append) == []
    assert "multiple browser targets" in events[-1].message


def test_rea_timeout_is_warning_only():
    settings = Settings(model_path=None, rea_command=f'"{sys.executable}" -c "import time; time.sleep(2)"')
    events = []
    assert run_rea("https://example.test", settings, events.append, timeout=0.05) == []
    assert events and events[-1].level == "warn"
