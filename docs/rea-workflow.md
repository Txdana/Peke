# REA to Peke Target Profile Workflow

This document explains how to take findings from **REA** (Reverse Engineering of Web Apps) and convert them into a Peke Target Profile (`.yaml`).

---

## 🔍 Overview

> **Important Note:** REA findings are automated hints and suggestions. They must be reviewed and verified by a human operator before being used in production extraction profiles.

**REA** reverse engineers web applications to discover:
1. Hidden API endpoints (e.g. `/api/v2/products`, `/graphql`).
2. Required HTTP headers (e.g., custom authorization tokens, `X-Api-Key`, `User-Agent`).
3. Query parameters or POST payloads.

**Peke** takes those findings and orchestrates fetching via **Scrapling** and extraction via local **llama.cpp** into clean, schema-valid JSON.

---

## 🛠 Step-by-Step Transition Guide

### Step 1: Discover Endpoints with REA
Run REA analysis against your target application. REA will produce an inspection report containing identified API routes:

```json
{
  "target_url": "https://example.com/shop",
  "endpoints": [
    {"method": "GET", "path": "/api/v1/products/list", "size": "12.4KB"},
    {"method": "POST", "path": "/api/v1/cart/checkout", "size": "2.1KB"}
  ],
  "headers": {
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"
  }
}
```

### Step 2: Create a Peke Target Profile (`.yaml`)
Translate the findings into a YAML profile under `profiles/`:

```yaml
# profiles/my_target.yaml
name: "E-Commerce Product API"
url: "https://example.com/api/v1/products/list"
fetcher: "StealthyFetcher"  # Use StealthyFetcher if Cloudflare/bot protection is present

headers:
  X-Requested-With: "XMLHttpRequest"
  User-Agent: "Mozilla/5.0 (X11; Linux x86_64)"

params:
  category: "electronics"
  limit: 20

endpoint_hints:
  - method: "GET"
    path: "/api/v1/products/list"
    source: "REA Discovered"

schema_name: "Product"
```

### Step 3: Run Peke Extraction
Execute Peke using the newly created profile:

```bash
peke run profiles/my_target.yaml -o output.json
```

Peke will:
1. Fetch the target data using Scrapling (`Fetcher` or `StealthyFetcher`).
2. Validate direct JSON if clean API endpoints are used.
3. Use local llama.cpp to structure raw payloads into schema-valid JSON if required.
