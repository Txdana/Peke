# Target Profiles Field Reference

Peke target profiles define how HTTP requests are dispatched and how responses are parsed into structured data.

## YAML Profile Schema

```yaml
# Primary target URL (Required)
target_url: "https://example.com/api/items"

# Scrapling fetcher backend ("Fetcher" or "StealthyFetcher")
fetcher_type: "StealthyFetcher"

# Custom HTTP Headers
headers:
  User-Agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
  Accept: "application/json"

# HTTP Query Parameters
params:
  page: "1"
  limit: "20"

# Target Pydantic schema registered in schema registry
schema_name: "Product"

# Enable LLM parsing when direct JSON validation fails
use_llm_fallback: true

# Discovered endpoint hints from REA
endpoint_hints:
  - "https://example.com/api/v1/items"
```

## Field Descriptions

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `target_url` | string | **Required** | Target web application or API endpoint URL |
| `fetcher_type` | string | `"Fetcher"` | Fetcher backend (`Fetcher` for standard HTTP, `StealthyFetcher` for Cloudflare bypass) |
| `headers` | dictionary | `{}` | Custom key-value HTTP headers |
| `params` | dictionary | `{}` | Key-value query parameters appended to request |
| `schema_name` | string | `"Article"` | Pydantic schema model used for validation |
| `use_llm_fallback` | boolean | `true` | Whether to pass unparsed HTML/Markdown payloads to local llama.cpp |
| `endpoint_hints` | list of strings | `[]` | Candidate endpoints suggested by REA analysis |
