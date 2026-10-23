# Schemas

Peke includes `Listing`, `Article`, and `Product` Pydantic models. Use `peke schemas` to list built-ins. The selected schema controls deterministic validation and the JSON schema supplied to the local model.

## Custom model

Create a Python module you trust:

```python
from pydantic import BaseModel, Field

class DemoRecord(BaseModel):
    title: str
    url: str | None = None
    price: float | None = Field(default=None, ge=0)
```

Reference it in YAML as `schema_name: path/to/my_schema.py:DemoRecord`. Use an absolute path if the relative path would be ambiguous. Schema modules are executable Python and are imported into the Peke process. **Only load modules you wrote or reviewed.** Do not load untrusted schema files; this is not a sandbox. Validate input types and keep schema code simple. Missing source fields should be optional and nullable rather than guessed.
