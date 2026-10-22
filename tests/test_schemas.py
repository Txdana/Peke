"""Tests for extraction schemas and schema registry."""

import pytest

from peke.schemas import Article, Listing, Product, get_schema


def test_schema_registry_lookup():
    assert get_schema("Article") == Article
    assert get_schema("article") == Article
    assert get_schema("Product") == Product
    assert get_schema("Listing") == Listing


def test_unknown_schema_raises_value_error():
    with pytest.raises(ValueError) as exc_info:
        get_schema("UnknownNonexistentSchema")
    assert "Unknown schema_name" in str(exc_info.value)


def test_article_model_validation():
    art = Article(
        title="Test Article Title",
        content="This is the article content text.",
        author="Jane Doe",
        tags=["news", "tech"],
    )
    assert art.title == "Test Article Title"
    assert art.author == "Jane Doe"
    assert len(art.tags) == 2


def test_product_model_validation():
    prod = Product(
        title="Wireless Headphones",
        price="$99.99",
        rating=4.5,
        in_stock=True,
    )
    assert prod.price == "$99.99"
    assert prod.in_stock is True
