# REA findings to a reviewed profile

The first section is a **schema-only fictional example**. The `.invalid` domain is reserved and intentionally does not resolve; do not use it for a live discovery run.

## 1. Review the discovery output

Assume the optional REA integration writes this normalized finding:

```json
{
  "method": "GET",
  "path": "/api/demo/items",
  "parameters": {"limit": "10"},
  "headers": {"Accept": "application/json"},
  "note": "Example endpoint from fictional demo app",
  "discovered_by": "rea"
}
```

A finding means only that a tool observed or inferred a possible route. It does not prove that the endpoint is public, stable, or permitted for your intended use.

## 2. Convert it into a hand-reviewed profile

```yaml
name: Fictional Demo Items
url: https://demo.invalid/api/demo/items
fetcher: basic
headers:
  Accept: application/json
params:
  limit: 10
method: GET
endpoints:
  - method: GET
    path: /api/demo/items
    note: Reviewed fictional example
    discovered_by: rea
schema_name: Listing
mode: api
max_pages: 1
```

`demo.invalid` is intentionally non-resolving. Replace it only with a target you own or are explicitly authorized to test. Confirm the route, method, parameter meanings, response schema, rate limits, and applicable terms before use.

## 3. Generate a draft

For a live run, replace the example URL with a page you own or are authorized to inspect, open that exact URL in the CDP-enabled browser described below, then run `peke discover <authorized-page-url> --out profiles/draft.yaml`. The resulting YAML is a draft: inspect every URL, path, parameter, and header before running it. If REA is missing or fails, create the profile manually; Peke does not depend on REA.


## Connect Peke to the official REA CLI

Peke uses REA's documented CLI for browser inspection. Install REA using its official setup instructions (for example `npm install --global rea-agents`) and set `REA_COMMAND=rea`. Peke does not install or update REA automatically; avoid runtime package runners if you want to keep Peke offline except for the target site and local CDP endpoint. See the upstream [CLI and Evidence guide](https://github.com/morluto/rea/blob/main/docs/cli.md) and [website observation guide](https://github.com/morluto/rea/blob/main/docs/browser-observation.md).

REA observes an already-running Chrome-family browser; it does not launch or navigate the browser. Start a dedicated browser profile with a loopback debugging endpoint, for example:

```sh
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/peke-rea-profile http://127.0.0.1:3000/
```

Set `REA_CDP_ENDPOINT=http://127.0.0.1:9222`, open the exact target page in that browser, and run `peke discover http://127.0.0.1:3000/` for the local example. Replace the URL with your own authorized page when testing a real site. Peke first calls `rea list-browser-targets`, matches the requested URL to exactly one page, then calls `rea analyze-web-bundle <endpoint> <target_id> --json`. Ambiguous targets are rejected instead of selecting one arbitrarily. The CDP endpoint must use a literal loopback IP and explicit port; do not expose browser debugging on your LAN or the public internet.

REA returns an Evidence envelope. Peke reads `normalized_result.observations.endpoints` and keeps route-like path candidates as reviewable endpoint hints. Findings are inferences or observations, not proof of a live, public, safe, stable, or authorized API. Review each candidate before using it. If REA is not installed, the browser is not open, the page doesn't match, the CDP endpoint is unavailable, or REA returns an error, Peke warns and continues without REA findings.

Automated tests use a fake local CLI to verify command order, target matching, Evidence parsing, timeout handling, and ambiguity refusal. They do not claim a live browser/REA integration test has run in this environment; that requires an installed REA CLI and a running browser with CDP enabled.
