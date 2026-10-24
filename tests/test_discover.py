import json

from peke.discover import load_findings, merge_findings
from peke.profile import load_profile


def test_load_and_merge_findings(tmp_path):
    path = tmp_path / "findings.json"
    path.write_text(json.dumps({"endpoints": [{"method": "GET", "path": "/api", "discovered_by": "REA"}]}), encoding="utf-8")
    hints = load_findings(path)
    profile = merge_findings(load_profile({"url": "https://example.com"}), hints)
    assert profile.endpoints[0].path == "/api"
