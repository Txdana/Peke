# Peke MCP Server User Guide

Peke 0.2.0 includes a built-in Model Context Protocol (MCP) server that lets local AI agents (Claude Code, Claude Desktop, Codex, Cursor, Gemini CLI, VS Code, Windsurf) use Peke's stealth fetching, endpoint discovery, and schema-constrained extraction capabilities as native tools.

---

## Quickstart

1. **Install or update Peke:**
   ```bash
   pipx install peke
   ```

2. **Register Peke with your local AI agents:**
   ```bash
   peke mcp install
   ```
   Or register a specific client:
   ```bash
   peke mcp install --client claude_code
   ```

3. **Restart your AI agent.**

4. **Example Agent Prompts:**
   - *"Use Peke to find the API behind https://demo.example/shop and extract the products as JSON."*
   - *"Stealth fetch https://news.example.com and extract top articles using the Article schema."*

---

## Tool Reference (11 Tools)

Every tool name is prefixed with `peke_`.

| Tool Name | Read-Only | Description |
|---|:---:|---|
| `peke_doctor` | Yes | Report Peke runtime health, model state, backends, Scrapling browser availability, REA status, and active MCP policy. |
| `peke_fetch` | Yes | Fetch a web page or API using basic HTTP or Scrapling stealth fetcher (GET only). |
| `peke_discover_endpoints` | No | Download page and same-origin scripts to analyze hidden endpoints via REA static analysis. |
| `peke_probe_endpoint` | Yes | Probe an endpoint safely using GET or HEAD to inspect status, content type, and JSON shape. |
| `peke_extract` | Yes | Extract structured JSON matching a Pydantic schema or JSON Schema using local model. |
| `peke_run_profile` | No | Execute a saved extraction profile (fetch, discover, extract, validate). |
| `peke_list_profiles` | Yes | List all saved extraction profiles in `~/.peke/profiles` and built-in profiles. |
| `peke_get_profile` | Yes | Retrieve a saved extraction profile with sensitive headers and tokens redacted. |
| `peke_save_profile` | No | Validate and save a new extraction profile to `~/.peke/profiles/<name>.yaml`. |
| `peke_schemas` | Yes | List available extraction schemas or retrieve detailed field descriptions for a schema. |
| `peke_get_run` | Yes | Retrieve stored artifacts (meta, content, records, endpoints, events) from a previous run. |

---

## Troubleshooting & FAQ

### Standard I/O (stdio) Cleanliness
In stdio mode (`peke mcp serve`), stdout carries **JSON-RPC messages ONLY**. Any `print()` statement or unhandled stdout message breaks the protocol stream. All log output is strictly routed to `sys.stderr` and `~/.peke/logs/mcp.log`.

### Testing with MCP Inspector
You can test Peke's MCP server using the official MCP Inspector tool:
```bash
npx @modelcontextprotocol/inspector peke mcp serve
```

---

## Streamable HTTP Transport

To run Peke MCP server over Streamable HTTP:
```bash
peke mcp serve --http --port 8765
```
- Bound to `127.0.0.1` ONLY for security.
- Requires bearer token authentication (`Authorization: Bearer <token>`).
- Manage bearer tokens via CLI:
  ```bash
  peke mcp token           # Display token
  peke mcp token --rotate  # Rotate token
  ```
