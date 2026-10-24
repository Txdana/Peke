# Sub-Agent Orchestration in Peke 0.3.0

Peke 0.3.0 introduces opt-in multi-agent deep discovery reconnaissance (`peke discover --deep`).

## Sub-Agent Roles

1. **Bundle Agent:**
   - Static analysis of JavaScript/HTML bundles and REA findings integration.
2. **Network Agent:**
   - Scrapling GET/HEAD route probing with strict SSRF validation.
3. **Auth-Analysis Agent:**
   - Header and cookie static analysis with automatic secret redaction (`[REDACTED]`).

## Execution and Persistence

Run details are saved in `~/.peke/runs/<run_id>/subagents.json`.
The GUI Sub-Agents tab provides live execution monitoring, run history, and session secret reveal controls.
