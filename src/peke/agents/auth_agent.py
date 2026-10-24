"""Authentication-analysis agent with automatic secret value redaction."""
from dataclasses import dataclass
from typing import Any


@dataclass
class AuthAgentResult:
    tokens: list[dict[str, Any]]
    notes: list[str]


class AuthAgent:
    SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie", "x-api-key", "x-auth-token", "bearer"}

    def analyze(self, headers: dict[str, str], cookies: dict[str, str] | None = None, reveal_secrets: bool = False) -> AuthAgentResult:
        tokens: list[dict[str, Any]] = []
        notes: list[str] = []

        for name, value in headers.items():
            name_lower = name.lower()
            if name_lower in self.SENSITIVE_HEADERS or any(sh in name_lower for sh in self.SENSITIVE_HEADERS):
                is_dynamic = "jwt" in value.lower() or "bearer" in value.lower() or len(value) > 20
                displayed_value = value if reveal_secrets else f"[REDACTED len={len(value)}]"
                tokens.append({
                    "name": name,
                    "location": "header",
                    "dynamic": is_dynamic,
                    "value": displayed_value,
                    "redacted": not reveal_secrets,
                })

        if cookies:
            for name, value in cookies.items():
                is_dynamic = len(value) > 16
                displayed_value = value if reveal_secrets else f"[REDACTED len={len(value)}]"
                tokens.append({
                    "name": name,
                    "location": "cookie",
                    "dynamic": is_dynamic,
                    "value": displayed_value,
                    "redacted": not reveal_secrets,
                })

        notes.append(f"Analyzed auth metadata: found {len(tokens)} token/credential header(s) or cookie(s).")
        if not reveal_secrets and tokens:
            notes.append("Secret values are redacted by default.")

        return AuthAgentResult(tokens=tokens, notes=notes)
