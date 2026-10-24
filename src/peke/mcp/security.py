"""Peke MCP Security, SSRF Guard, and Token Authentication."""

import hmac
import ipaddress
import os
import re
import secrets
import socket
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from peke.config import Settings
from peke.mcp.runs import get_peke_dir

SENSITIVE_KEY_RE = re.compile(
    r"(authorization|cookie|bearer|token|api[-_]?key|secret|password|credential|private[-_]?key)",
    re.IGNORECASE,
)


class SecurityError(ValueError):
    """Raised when a request violates security or policy rules."""


def redact_secrets(val: Any) -> Any:
    """Recursively redact sensitive headers, keys, or credentials."""
    if isinstance(val, dict):
        new_dict = {}
        for k, v in val.items():
            if SENSITIVE_KEY_RE.search(str(k)):
                new_dict[k] = "***"
            else:
                new_dict[k] = redact_secrets(v)
        return new_dict
    elif isinstance(val, list):
        return [redact_secrets(item) for item in val]
    elif isinstance(val, tuple):
        return tuple(redact_secrets(item) for item in val)
    elif isinstance(val, str):
        # Redact bearer token patterns if embedded in strings
        val_sub = re.sub(r"(Bearer\s+)[A-Za-z0-9_\-\.~+/=]+", r"\1***", val, flags=re.IGNORECASE)
        return val_sub
    return val


def parse_ip_literal_or_numeric(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Attempt to parse hostname as IP address literal or integer/hex/octal IP representation."""
    host_clean = host.strip("[]")
    # Direct IP address
    try:
        return ipaddress.ip_address(host_clean)
    except ValueError:
        pass

    # Decimal integer IP trick (e.g., 2130706433 -> 127.0.0.1)
    if host_clean.isdigit():
        try:
            return ipaddress.ip_address(int(host_clean))
        except ValueError:
            pass

    # Hex integer IP trick (e.g., 0x7f000001 -> 127.0.0.1)
    if host_clean.lower().startswith("0x"):
        try:
            return ipaddress.ip_address(int(host_clean, 16))
        except ValueError:
            pass

    return None


def is_ip_private_or_restricted(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check whether an IP address object is loopback, private, link-local, or restricted."""
    if (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
    ):
        return True

    # Explicit check for AWS / Cloud metadata service 169.254.169.254
    if str(ip_obj) == "169.254.169.254":
        return True

    # Carrier-grade NAT 100.64.0.0/10
    if isinstance(ip_obj, ipaddress.IPv4Address):
        cgnat = ipaddress.ip_network("100.64.0.0/10")
        if ip_obj in cgnat:
            return True

    return False


def validate_url_security(url: str, settings: Settings) -> str:
    """Validate URL scheme, domain, and IP address against SSRF and policy rules."""
    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise SecurityError(f"Unsupported URL scheme {parsed.scheme!r}. Only http and https are allowed.")

    hostname = parsed.hostname
    if not hostname:
        raise SecurityError("Invalid URL: missing hostname")

    # Domain list filtering
    allowed = settings.mcp_allowed_domains
    if allowed:
        if not any(hostname == domain or hostname.endswith("." + domain) for domain in allowed):
            raise SecurityError(f"Domain {hostname!r} is not in allowed_domains list.")

    blocked = settings.mcp_blocked_domains
    if blocked:
        if any(hostname == domain or hostname.endswith("." + domain) for domain in blocked):
            raise SecurityError(f"Domain {hostname!r} is blocked by policy.")

    # Private host / SSRF check
    if not settings.mcp_allow_private_hosts:
        if hostname.lower() == "localhost" or hostname.lower().endswith(".localhost"):
            raise SecurityError(f"Access to private/loopback hostname {hostname!r} is blocked.")

        # Check direct IP literal or numeric trick
        ip_obj = parse_ip_literal_or_numeric(hostname)
        if ip_obj is not None:
            if is_ip_private_or_restricted(ip_obj):
                raise SecurityError(f"Access to private/loopback IP address {hostname} is blocked.")
        else:
            # Domain name -> resolve DNS to verify all resolved IPs
            try:
                addrinfo = socket.getaddrinfo(hostname, None)
                if not addrinfo:
                    raise SecurityError(f"Could not resolve hostname {hostname!r}")
                for item in addrinfo:
                    resolved_ip_str = item[4][0]
                    try:
                        resolved_ip = ipaddress.ip_address(resolved_ip_str)
                        if is_ip_private_or_restricted(resolved_ip):
                            raise SecurityError(
                                f"Access to private/loopback IP address ({hostname} -> {resolved_ip_str}) is blocked."
                            )
                    except ValueError:
                        pass
            except socket.gaierror as exc:
                raise SecurityError(f"Could not resolve hostname {hostname!r}: {exc}") from exc

    return url


def get_token_file_path() -> Path:
    """Path to bearer token file ~/.peke/mcp-token."""
    d = get_peke_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "mcp-token"


def get_or_create_mcp_token() -> str:
    """Retrieve existing bearer token or generate a new 32-byte secret token."""
    path = get_token_file_path()
    if path.is_file():
        try:
            token = path.read_text(encoding="utf-8").strip()
            if len(token) >= 32:
                return token
        except OSError:
            pass

    # Generate new token
    new_token = secrets.token_hex(32)
    try:
        path.write_text(new_token + "\n", encoding="utf-8")
        if os.name != "nt":
            path.chmod(0o600)
    except OSError:
        pass
    return new_token


def rotate_mcp_token() -> str:
    """Rotate and return a new bearer token."""
    path = get_token_file_path()
    new_token = secrets.token_hex(32)
    try:
        path.write_text(new_token + "\n", encoding="utf-8")
        if os.name != "nt":
            path.chmod(0o600)
    except OSError:
        pass
    return new_token


def verify_mcp_token(provided_token: str) -> bool:
    """Constant-time compare provided token against stored bearer token."""
    expected = get_or_create_mcp_token()
    return hmac.compare_digest(provided_token.strip(), expected.strip())
