# Peke MCP Security Architecture & Threat Model

This document outlines the security posture, threat model, and defense mechanisms built into Peke's MCP server.

---

## Threat Model & Core Assumptions

1. **Untrusted External Web Content:**
   All web content retrieved from external web servers or APIs via `peke_fetch`, `peke_discover_endpoints`, or `peke_probe_endpoint` is treated as untrusted data.
   - **Defense:** Returned tool payloads set `"untrusted": true`, and prompt-injection posture directives remind agents and system prompts that web content must never be executed or followed as instructions.

2. **Server-Side Request Forgery (SSRF):**
   Agents calling `peke_fetch` or `peke_probe_endpoint` could attempt to access internal infrastructure, cloud metadata endpoints (`169.254.169.254`), CGNAT addresses (`100.64.0.0/10`), or loopback services (`127.0.0.1`).
   - **Defense:** `validate_url_security` resolves target hostnames and checks resolved IP addresses against loopback, private, link-local, CGNAT, multicast, and unspecified ranges. Private host access is blocked by default unless `allow_private_hosts=true` is explicitly configured.

3. **DNS Rebinding & Host Header Attacks:**
   HTTP transport connections could be targeted by malicious websites performing DNS rebinding attacks against local loopback ports.
   - **Defense:** The Streamable HTTP server binds strictly to `127.0.0.1`. Middleware validates `Host` and `Origin` headers, rejecting any request where the Host or Origin does not resolve to `127.0.0.1` or `localhost`. Mandatory 32-byte secret bearer tokens (`~/.peke/mcp-token`, `0600` permissions) are verified with constant-time comparison (`hmac.compare_digest`).

4. **Resource Contention & Local Model Lock:**
   Concurrent execution of llama.cpp or GGUF weights from multiple clients or background GUI processes could exhaust VRAM/RAM or cause crash loops.
   - **Defense:** File lock `~/.peke/model.lock` prevents concurrent GGUF loads across GUI, CLI, and MCP server. If locked, MCP tools return a retryable busy error (`"Peke model is busy, retry shortly"`).

5. **Secrets Leakage:**
   API keys, cookies, or bearer tokens in profile definitions or headers could be logged or returned to agents.
   - **Defense:** All loggers, activity entries (`~/.peke/activity.jsonl`), profile views (`peke_get_profile`), and error messages pass through `redact_secrets` which replaces sensitive headers and tokens with `"***"`.

6. **Scope Boundaries — What Peke Does NOT Do:**
   - Peke does **NOT** execute arbitrary shell commands.
   - Peke does **NOT** execute fetched JavaScript or remote code.
   - Peke does **NOT** send state-changing HTTP requests (`POST`, `PUT`, `DELETE`). Fetch and probe tools are strictly `GET` and `HEAD` only.
   - Peke does **NOT** delete files or write files outside `~/.peke/`.
