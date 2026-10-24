# Sub-Agent Orchestration in Peke 0.3.0

Peke 0.3.0 introduces opt-in multi-agent deep discovery reconnaissance (`peke discover --deep`).

## Sub-Agent Roles

1. **Bundle Agent:**
   - Static analysis of JavaScript/HTML bundles and REA findings integration.
2. **Network Agent:**
   - Scrapling GET/HEAD route probing with strict SSRF validation.
3. **Auth-Analysis Agent:**
   - Header and cookie static analysis with automatic secret redaction (`[REDACTED]`).

4. **Probe Agent:**
   - Sends read-only GET requests (max 12, same-origin, SSRF-checked, rate-limited) to REA/bundle endpoint hints, never to templated paths or non-GET hints, and keeps only status, content type and response *shape*.
5. **Schema Agent:**
   - Finds the item list (`item_path`), field types and pagination keys deterministically, then asks the configured provider to pick a built-in schema. If no AI provider is ready it falls back to the deterministic result.

The Bundle Agent now also fetches up to 5 same-origin `.js` files linked from the page and mines `fetch`/`axios` call literals. `peke discover --deep` writes the richest JSON endpoint into the draft profile (`url`, `params`, `item_path`, `schema_name`). Treat it as a draft: review before running, and only on targets you are authorized to inspect.

## Execution and Persistence

Run details are saved in `~/.peke/runs/<run_id>/subagents.json`.
The GUI Sub-Agents tab provides live execution monitoring, run history, and session secret reveal controls.
