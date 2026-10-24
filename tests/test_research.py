"""Situation-aware research: search, link fallback, ranking, safety."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

from peke.config import Settings
from peke.fetch import FetchResult
from peke.research import research
from peke.search import SearxngClient, detect
from peke.situation import extract_urls, keywords, search_query


def test_prompt_links_and_keywords():
    p = "Compare pricing at https://a.com/p, b.io/docs. Email me@x.com"
    assert extract_urls(p) == ["https://a.com/p", "https://b.io/docs"]
    assert keywords(p) == ["compare", "pricing"] and search_query(p) == "compare pricing"


class _Fake(BaseHTTPRequestHandler):
    code = 200

    def log_message(self, *a):
        pass

    def do_GET(self):
        if _Fake.code != 200:
            self.send_response(_Fake.code)
            self.end_headers()
            return
        body = json.dumps({"results": [{"url": "https://s.com/1", "title": "one", "content": "c"}]}).encode()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body)


def _server(code=200):
    _Fake.code = code
    srv = HTTPServer(("127.0.0.1", 0), _Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"


def _page(url, *a, **k):
    html = f"<title>Pricing {url}</title><p>pricing plans cost 20 dollars</p>"
    return FetchResult(url.url, 200, "text/html", "pricing plans cost 20 dollars", None, 1.0, raw_html=html)


def _run(prompt, searx, **kw):
    s = Settings(None, request_delay_seconds=0.0)
    with patch("peke.research.fetch", side_effect=_page), patch("peke.research.validate_url_security", side_effect=lambda u, _s: u):
        return research(prompt, s, searxng_url=searx, **kw)


def test_search_plus_prompt_links():
    srv, url = _server()
    r = _run("pricing plans https://a.com/p", url)
    assert r.situation["mode"] == "search+links"
    assert [s.via for s in r.sources][0] == "prompt" and {s.via for s in r.sources} == {"prompt", "search"}
    srv.shutdown()


def test_falls_back_to_prompt_links_when_search_refuses_json():
    srv, url = _server(403)
    r = _run("pricing plans https://a.com/p", url)
    assert r.situation["mode"] == "links" and len(r.sources) == 1 and "json" in r.situation["search"]["reason"].lower()
    srv.shutdown()


def test_no_search_no_links_is_reported_not_invented():
    r = _run("what is the latest pricing", "http://127.0.0.1:1")
    assert r.situation["mode"] == "none" and r.sources == [] and r.notes


def test_blocked_private_target_is_not_fetched():
    from peke.mcp.security import SecurityError
    with patch("peke.research.fetch") as f, patch("peke.research.validate_url_security", side_effect=SecurityError("private")):
        r = research("see http://169.254.169.254/x", Settings(None, request_delay_seconds=0.0), use_search=False)
    assert f.call_count == 0 and r.sources[0].status == "blocked"


def test_detect_never_raises():
    assert detect("not a url")[0] is None
    assert SearxngClient("http://127.0.0.1:1").status()["available"] is False
