"""Security, SSRF guard, secret redaction, and HTTP transport unit tests."""

import pytest
from starlette.testclient import TestClient

from peke.config import Settings
from peke.mcp.http import create_http_app, run_http_server
from peke.mcp.security import (
    SecurityError,
    get_or_create_mcp_token,
    redact_secrets,
    rotate_mcp_token,
    validate_url_security,
    verify_mcp_token,
)
from peke.mcp.server import build_server


def test_ssrf_guard_ip_matrix(tmp_path, monkeypatch):
    monkeypatch.setenv("PEKE_HOME", str(tmp_path))
    settings = Settings(model_path=None, mcp_allow_private_hosts=False)

    blocked_urls = [
        "http://127.0.0.1/admin",
        "http://127.0.0.2:8080/path",
        "http://localhost/path",
        "http://10.0.0.1/internal",
        "http://172.16.0.1/internal",
        "http://192.168.1.1/internal",
        "http://169.254.169.254/latest/meta-data/",
        "http://169.254.1.1/link-local",
        "http://100.64.0.1/cgnat",
        "http://0.0.0.0/",
        "http://2130706433/",  # Decimal 127.0.0.1
        "http://0x7f000001/",  # Hex 127.0.0.1
        "ftp://example.com/file",
    ]

    for url in blocked_urls:
        with pytest.raises(SecurityError):
            validate_url_security(url, settings)

    # Valid external URL
    valid_url = "https://example.com/items"
    assert validate_url_security(valid_url, settings) == valid_url


def test_ssrf_guard_allowed_and_blocked_domains(tmp_path, monkeypatch):
    monkeypatch.setenv("PEKE_HOME", str(tmp_path))
    # Mock DNS lookup so test doesn't depend on external network DNS
    monkeypatch.setattr(
        "socket.getaddrinfo",
        lambda host, port: [(2, 1, 6, "", ("93.184.216.34", 0))],
    )

    # Allowed domains filter
    s_allowed = Settings(model_path=None, mcp_allowed_domains=("example.com", "api.shop.org"))
    assert validate_url_security("https://example.com/page", s_allowed) == "https://example.com/page"
    assert validate_url_security("https://sub.example.com/page", s_allowed) == "https://sub.example.com/page"
    with pytest.raises(SecurityError):
        validate_url_security("https://unallowed.com/page", s_allowed)

    # Blocked domains filter
    s_blocked = Settings(model_path=None, mcp_blocked_domains=("malicious.com",))
    with pytest.raises(SecurityError):
        validate_url_security("https://malicious.com/phish", s_blocked)


def test_allow_private_hosts_override(tmp_path, monkeypatch):
    monkeypatch.setenv("PEKE_HOME", str(tmp_path))
    s_private = Settings(model_path=None, mcp_allow_private_hosts=True)

    # Private IP allowed when flag is explicitly True
    url = "http://127.0.0.1:8080/test"
    assert validate_url_security(url, s_private) == url


def test_secret_redaction():
    payload = {
        "Authorization": "Bearer secret_jwt_token_123",
        "Cookie": "session=abc123xyz",
        "api_key": "sk-1234567890",
        "normal_field": "public_data",
        "nested": {
            "password": "my_password",
            "url": "https://user:pass@example.com",
        },
    }

    redacted = redact_secrets(payload)
    assert redacted["Authorization"] == "***"
    assert redacted["Cookie"] == "***"
    assert redacted["api_key"] == "***"
    assert redacted["normal_field"] == "public_data"
    assert redacted["nested"]["password"] == "***"


def test_http_token_management(tmp_path, monkeypatch):
    monkeypatch.setenv("PEKE_HOME", str(tmp_path))

    token1 = get_or_create_mcp_token()
    assert len(token1) >= 32
    assert verify_mcp_token(token1) is True
    assert verify_mcp_token("wrong_token") is False

    token2 = rotate_mcp_token()
    assert token2 != token1
    assert verify_mcp_token(token2) is True
    assert verify_mcp_token(token1) is False


def test_http_transport_security_middleware(tmp_path, monkeypatch):
    monkeypatch.setenv("PEKE_HOME", str(tmp_path))

    server = build_server()
    app = create_http_app(server)
    client = TestClient(app)

    token = get_or_create_mcp_token()

    # Reject missing auth
    res_no_auth = client.get("/", headers={"Host": "127.0.0.1:8765"})
    assert res_no_auth.status_code == 401

    # Reject bad token
    res_bad_token = client.get("/", headers={"Authorization": "Bearer wrongtoken", "Host": "127.0.0.1:8765"})
    assert res_bad_token.status_code == 401

    # Reject bad Host header
    res_bad_host = client.get(
        "/",
        headers={"Authorization": f"Bearer {token}", "Host": "evil.com"},
    )
    assert res_bad_host.status_code == 403

    # Reject bad Origin header
    res_bad_origin = client.get(
        "/",
        headers={"Authorization": f"Bearer {token}", "Origin": "http://evil.com"},
    )
    assert res_bad_origin.status_code == 403

    # Accept valid request with token and loopback host
    res_ok = client.get(
        "/",
        headers={"Authorization": f"Bearer {token}", "Host": "127.0.0.1:8765"},
    )
    assert res_ok.status_code != 401
    assert res_ok.status_code != 403


def test_run_http_server_refuses_non_loopback():
    server = build_server()
    with pytest.raises(ValueError, match="127.0.0.1 ONLY"):
        run_http_server(server, host="0.0.0.0")
