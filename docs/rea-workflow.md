# REA Workflow: From Discovery to Profile

This guide demonstrates how REA (Reverse Engineering Assistant) discovery findings are converted into a Peke Target Profile YAML using a fictional demo target (`https://api.democorp-example.internal/products`).

## Step 1: Run REA Discovery

Using the Peke CLI, initiate endpoint discovery against the target URL:

```bash
peke discover https://api.democorp-example.internal/products -o profiles/demo_products.yaml
```

If REA is reachable at `REA_SERVER_URL`, Peke queries REA for candidate endpoints, required request headers, and parameter parameters.

## Step 2: Review Generated Findings

REA saves raw inspection hints to `profiles/demo_products.json`:

```json
{
  "target_url": "https://api.democorp-example.internal/products",
  "endpoint_hints": [
    "https://api.democorp-example.internal/v2/items?category=electronics"
  ],
  "headers": {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)",
    "X-Client-App": "DemoCorpWeb"
  },
  "params": {
    "category": "electronics",
    "limit": "50"
  },
  "schema_name": "Product",
  "note": "REA findings are hints that must be reviewed before use."
}
```

## Step 3: Refine Draft Profile YAML

Review and clean the draft YAML file (`profiles/demo_products.yaml`):

```yaml
target_url: https://api.democorp-example.internal/v2/items
fetcher_type: StealthyFetcher
headers:
  User-Agent: Mozilla/5.0 (X11; Linux x86_64)
  X-Client-App: DemoCorpWeb
params:
  category: electronics
  limit: 50
schema_name: Product
use_llm_fallback: true
```

## Step 4: Run Extraction Pipeline

Execute the pipeline with the finalized profile:

```bash
peke run profiles/demo_products.yaml -o output.json
```
