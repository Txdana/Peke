"""YAML target profiles and validation."""
import logging
import re
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)


class ProfileError(Exception):
    """Profile could not be loaded or validated."""


def _validate_headers(value: dict[str, str]) -> dict[str, str]:
    """Reject malformed HTTP header names and CR/LF injection in header values."""
    token = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
    for name, header_value in value.items():
        if not token.fullmatch(name):
            raise ValueError(f"Invalid HTTP header name: {name!r}")
        if any(char in str(header_value) for char in "\r\n"):
            raise ValueError(f"HTTP header {name!r} must not contain CR or LF")
        if len(str(header_value)) > 16_384:
            raise ValueError(f"HTTP header {name!r} exceeds 16384 characters")
    if len(value) > 200:
        raise ValueError("At most 200 HTTP headers may be configured")
    return value


class EndpointHint(BaseModel):
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "GET"
    path: str = Field(min_length=1, max_length=4096)
    size: str | int | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    note: str | None = Field(default=None, max_length=4000)
    discovered_by: str | None = Field(default=None, max_length=100)
    hidden: bool = False

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("endpoint path must not contain control characters")
        return value

    @field_validator("headers")
    @classmethod
    def validate_endpoint_headers(cls, value: dict[str, str]) -> dict[str, str]:
        return _validate_headers(value)


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("headers")
    @classmethod
    def validate_profile_headers(cls, value: dict[str, str]) -> dict[str, str]:
        return _validate_headers(value)

    @field_validator("url")
    @classmethod
    def validate_target_url(cls, value: str) -> str:
        """Allow explicit HTTP(S) targets only; private/local web targets remain valid."""
        if not isinstance(value, str) or not value or value != value.strip():
            raise ValueError("url must be a non-empty URL without surrounding whitespace")
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("url must not contain control characters")
        if "\\" in value:
            raise ValueError("url must not contain backslashes")
        try:
            parsed = urlsplit(value)
            # Accessing .port validates malformed and out-of-range ports.
            _ = parsed.port
        except ValueError as exc:
            raise ValueError("url is malformed") from exc
        if parsed.scheme.lower() not in {"http", "https"}:
            raise ValueError("url must use http:// or https://")
        if not parsed.hostname:
            raise ValueError("url must include a hostname")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("url must not embed credentials; use headers for authentication")
        return value

    name: str = "Unnamed target"
    url: str
    fetcher: Literal["stealthy", "basic"] = "basic"
    headers: dict[str, str] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    method: Literal["GET", "POST"] = "GET"
    body: dict[str, Any] | None = None
    endpoints: list[EndpointHint] = Field(default_factory=list)
    schema_name: str = "Article"
    mode: Literal["auto", "api", "llm"] = "auto"
    max_pages: int = Field(default=1, ge=1)
    item_path: str | None = None


def redact_url(value: str) -> str:
    """Return a log-safe URL without credentials, query values, or fragments."""
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname or "<invalid-host>"
        if ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"
        try:
            port = parsed.port
        except ValueError:
            port = None
        netloc = hostname + (f":{port}" if port is not None else "")
        suffix = "?[REDACTED]" if parsed.query else ""
        return f"{parsed.scheme}://{netloc}{parsed.path}{suffix}"
    except (TypeError, ValueError):
        return "<invalid-url>"


TargetProfile = Profile


def load_profile(path: str | Path | dict[str, Any]) -> Profile:
    """Load and validate a profile from YAML or a mapping."""
    if isinstance(path, dict):
        raw = path
    else:
        file_path = Path(path)
        if not file_path.is_file():
            raise ProfileError(f"Profile file not found: {file_path}")
        try:
            raw = yaml.safe_load(file_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise ProfileError(f"Could not read YAML profile '{file_path}': {exc}") from exc
    if not isinstance(raw, dict):
        raise ProfileError("Profile YAML must contain a mapping of profile fields.")
    try:
        return Profile.model_validate(raw)
    except ValidationError as exc:
        raise ProfileError(f"Invalid profile fields: {exc}") from exc
