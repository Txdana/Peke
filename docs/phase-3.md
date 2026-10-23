# Phase 3: live data, REA integration, settings pages

## REA integration contract

Peke's optional adapter uses the official REA CLI. Configure `REA_COMMAND` as an executable prefix such as `rea`; Peke runs `rea list-browser-targets <REA_CDP_ENDPOINT> --json`, selects a unique open page matching the requested URL, then runs `rea analyze-web-bundle <REA_CDP_ENDPOINT> <target_id> --json`. The adapter parses endpoint candidates from the REA Evidence envelope and rejects ambiguous browser target matches. The CDP endpoint must be a literal loopback IP with an explicit port. Peke does not launch or navigate the browser.

The supplied Peke archive did not include REA itself, so integration tests use a fake local CLI implementing the documented public commands and JSON Evidence shape. This verifies command construction, matching, parsing, timeout behavior, and fallback, but is not a live-browser test. See `docs/rea-workflow.md` for setup and the upstream REA documentation links. If REA is not configured, the browser is unavailable, the URL does not match an open page, or REA returns an error, Peke warns and continues with profile endpoint hints.

**REA findings are hints, not proof. Review endpoint paths, methods, headers,
parameters, authentication requirements and authorization before using them.**
Only test systems you own or are authorized to inspect; respect `robots.txt`,
site terms, rate limits and privacy requirements.

## New Phase 3 features

- Endpoint hints now carry optional size, parameters, headers and a hidden flag.
- `peke discover URL --out profiles/target.yaml` creates a draft profile. Use
  `--findings findings.json` to save a normalized findings file too.
- GUI endpoint rows are grouped by host and path; double-click a leaf to review
  its metadata and use it as an API-mode target.
- JSON output uses a lightweight syntax highlighter, line-number gutter,
  search field and a 1 MB preview cap for very large output.
- Console filtering, copy/save, a 5,000-line cap and optional GPU/CPU telemetry
  are available. User settings are stored under the platform-specific Peke
  config directory, not in the repository's `.env`.

## Deliberately left for later

Network pagination, fully interruptible in-flight llama.cpp calls, a complete
schema sandbox, real-time per-token generation streaming, and pixel-perfect
GUI validation on each supported desktop remain future hardening work.
