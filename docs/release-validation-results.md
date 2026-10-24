# Release validation results

The earlier version of this file described a Docker-backed SearXNG controller. That controller no
longer exists; Peke now runs the bundled `searx.webapp` as a private local process. See
`QA-REPORT.md` (shipped with the 2026-10-24 QA pass) for the current, evidence-based results.
Windows x64 runtime validation has **not** been performed; run the smoke test in
`docs/bundled-searxng-validation.md` on a real Windows machine before publishing.
