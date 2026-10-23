# Profile reference

A profile is a YAML document describing one target and the schema used to validate its records. Start from `profiles/example.yaml` and keep a reviewed copy for each target.

| Field | Type | Default / values | Meaning |
|---|---|---|---|
| `name` | string | required | Human-readable profile name |
| `url` | URL string | required | Target URL; use only targets you are authorized to access |
| `fetcher` | string | `basic` or `stealthy` | Scrapling fetcher mode |
| `headers` | string map | `{}` | Request headers; do not commit secrets |
| `params` | map | `{}` | Query parameters |
| `method` | string | `GET` or `POST` | HTTP method |
| `body` | object/null | optional | JSON body for POST requests |
| `endpoints` | list | `[]` | Reviewed endpoint hints; each has `method`, `path`, optional `note`, and `discovered_by` |
| `schema_name` | string | built-in name or `path/to/schema.py:ModelName` | Pydantic model used for validation |
| `mode` | string | `auto`, `api`, `llm` | `auto` tries deterministic parsing first; `api` requires direct validation; `llm` forces model extraction |
| `max_pages` | integer | `1` | Page limit supported by the configured pipeline mode |
| `item_path` | string/null | optional | Dot-separated path to records in a JSON response, e.g. `data.items` |

Example:

```yaml
name: Fictional Demo Catalog
url: https://demo.invalid/api/items
fetcher: basic
headers:
  Accept: application/json
params:
  limit: 20
method: GET
body: null
endpoints: []
schema_name: Product
mode: auto
max_pages: 1
item_path: data.items
```

Validate before running: `peke validate profiles/example.yaml`. `peke discover` writes a draft profile; review all discovered paths, parameters, and headers before using it. Never store API keys or cookies in a shared profile.
