"""Pydantic schemas and schema registry for Peke extraction."""


from pydantic import BaseModel, Field


class Article(BaseModel):
    """Schema model for article extraction."""

    title: str = Field(..., description="Article title or main heading")
    author: str | None = Field(default=None, description="Author name if available")
    publication_date: str | None = Field(default=None, description="Publication or release date")
    summary: str | None = Field(default=None, description="Short summary or abstract")
    content: str = Field(..., description="Main text content or body of the article")
    tags: list[str] = Field(default_factory=list, description="Categories or tags")


class Product(BaseModel):
    """Schema model for product extraction."""

    title: str = Field(..., description="Product name or title")
    price: str | None = Field(default=None, description="Product price string or amount")
    currency: str | None = Field(default=None, description="Currency code or symbol")
    description: str | None = Field(default=None, description="Detailed product description")
    in_stock: bool | None = Field(default=None, description="Stock availability status")
    rating: float | None = Field(default=None, description="Product rating score")
    features: list[str] = Field(default_factory=list, description="Key product features")


class Listing(BaseModel):
    """Schema model for item listing extraction."""

    title: str = Field(..., description="Listing title")
    items: list[dict[str, str]] = Field(
        default_factory=list, description="List of items/rows with key-value properties"
    )
    total_count: int | None = Field(default=None, description="Total number of items")
    page_number: int | None = Field(default=None, description="Current page number if paginated")


SCHEMA_REGISTRY: dict[str, type[BaseModel]] = {
    "Article": Article,
    "Product": Product,
    "Listing": Listing,
    "article": Article,
    "product": Product,
    "listing": Listing,
}


def get_schema(schema_name: str) -> type[BaseModel]:
    """Retrieve Pydantic model class by name from registry.

    :param schema_name: Name of registered schema model.
    :return: Pydantic model subclass.
    :raises ValueError: If schema name is not registered.
    """
    if schema_name in SCHEMA_REGISTRY:
        return SCHEMA_REGISTRY[schema_name]

    # Case-insensitive fallback lookup
    for key, model_cls in SCHEMA_REGISTRY.items():
        if key.lower() == schema_name.lower():
            return model_cls

    raise ValueError(
        f"Unknown schema_name '{schema_name}'. Registered schemas: {list(set(SCHEMA_REGISTRY.keys()))}"
    )
