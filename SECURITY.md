# Security policy

## Reporting a vulnerability

Please do not disclose a suspected vulnerability in a public issue. Contact the project maintainers privately with reproduction steps, affected versions, and impact. Do not include real credentials, session cookies, or private target data in a report.

## Security model and boundaries

Peke is a local-first desktop application. It does not provide a network service and does not send prompts to a hosted LLM. Network requests are made to the target URLs explicitly supplied by the user; optional REA integration talks to a loopback-only Chrome DevTools Protocol endpoint and a locally installed `rea` executable.

- Target profiles accept only `http://` and `https://` URLs and reject embedded credentials and control characters. Localhost and private-network HTTP targets are intentionally permitted for local development and authorized internal testing. Users must only fetch targets they are authorized to access.
- Profile headers reject invalid token names, CR/LF injection, excessive counts, and oversized values. Never place credentials in target URL query strings; query values are omitted from Peke's own URL log messages.
- REA's browser debugging endpoint must use a literal loopback IP. Never expose Chrome DevTools Protocol on a public or LAN interface. `REA_COMMAND` is an explicitly configured executable prefix and will be executed as a subprocess without a shell; configure it only to a trusted local binary.
- User-supplied Pydantic schema files are checked against a declarative AST subset before import. This is a guardrail, **not a sandbox**. Only load schema files from trusted sources.
- Model files are local and are not downloaded automatically. A GGUF file is native model data consumed by the llama.cpp runtime; use trusted model sources and keep the runtime updated.
- Output paths are user-configurable. Choose a directory whose contents are appropriate for the sensitivity of extracted data.

## Automated checks

CI runs unit and integration tests, Ruff, Bandit static analysis, and `pip-audit` against installed dependency versions. Dependency audit failures should be investigated and resolved or explicitly documented with a bounded mitigation; do not suppress them without review.

## Known limitations

Peke intentionally permits user-selected private-network targets, so it is not an SSRF-hardened multi-tenant server. Running it on a workstation grants it the same network reachability as that user. It does not yet sandbox arbitrary schema imports or model runtimes, nor encrypt extracted output files. Avoid running it with elevated privileges and do not use untrusted schema files or model weights.
