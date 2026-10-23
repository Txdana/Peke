from peke.schemas import Article, get_schema, list_schemas


def test_registry_and_nullable_fields():
    assert get_schema("article") is Article
    assert {"Article", "Listing", "Product"}.issubset(set(list_schemas()))
    assert Article.model_validate({"title": "Known"}).content is None
