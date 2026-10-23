# Writing Custom Pydantic Schemas

Peke uses Pydantic v2 schemas to strictly validate extracted JSON data structures.

## Built-in Schemas

Peke includes standard built-in schemas out-of-the-box:
- `Article` (`title`, `author`, `published_date`, `content`, `tags`)
- `Product` (`name`, `price`, `currency`, `description`, `in_stock`, `rating`)
- `Listing` (`title`, `items`, `page`, `total_pages`)

## Defining Custom Schemas

You can register custom Pydantic schemas in Python:

```python
from pydantic import BaseModel, Field
from peke.schemas import register_schema

class JobPosting(BaseModel):
    title: str = Field(description="Job title")
    company: str = Field(description="Employer name")
    location: str = Field(description="Office location or Remote")
    salary_range: str | None = Field(default=None, description="Salary details")

register_schema("JobPosting", JobPosting)
```

## LLM Schema Constraints

When LLM fallback is triggered, Peke extracts the Pydantic JSON schema via `JobPosting.model_json_schema()` and passes it in the llama.cpp call:

```python
response_format = {
    "type": "json_object",
    "schema": schema_class.model_json_schema()
}
```

This enforces strict GBNF grammar constraints in llama.cpp, guaranteeing schema-valid JSON output.
