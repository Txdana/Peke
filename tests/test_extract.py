"""Tests for direct JSON parsing and LLM extraction."""

from unittest.mock import MagicMock

from peke.extract import (
    LocalExtractor,
    direct_validate_json,
    extract_data,
    model_to_markdown,
)
from peke.schemas import Article


def test_model_to_markdown():
    art = Article(
        title="Sample Title",
        content="Sample content body text.",
        author="Author Name",
        tags=["tag1", "tag2"],
    )
    md = model_to_markdown(art)
    assert "# Article" in md
    assert "**Title**: Sample Title" in md
    assert "- tag1" in md


def test_direct_validate_json_clean_dict():
    raw_dict = {
        "title": "Clean Article",
        "content": "This is direct clean json content.",
        "author": "Bot",
    }
    validated = direct_validate_json(raw_dict, Article)
    assert validated is not None
    assert validated.title == "Clean Article"
    assert validated.author == "Bot"


def test_direct_validate_json_fails_returns_none():
    bad_dict = {"invalid_field": "123"}
    validated = direct_validate_json(bad_dict, Article)
    assert validated is None


def test_extract_data_skips_llm_on_direct_json():
    clean_json = {
        "title": "Headphones",
        "price": "$50",
        "in_stock": True,
    }
    result = extract_data(clean_json, schema_name="Product", is_json_payload=True)
    assert result.used_llm is False
    assert result.data.title == "Headphones"
    assert result.json_output["price"] == "$50"


def test_local_extractor_mocked_llm(tmp_path):
    mock_llm = MagicMock()
    mock_llm.create_chat_completion.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"title": "Extracted Title", "content": "Extracted Content Body"}'
                }
            }
        ],
        "usage": {"completion_tokens": 20},
    }

    dummy_model_file = tmp_path / "model.gguf"
    dummy_model_file.write_text("gguf")

    extractor = LocalExtractor(model_path=dummy_model_file, temperature=0.1)
    extractor._llm = mock_llm  # Inject mocked LLM

    result = extractor.extract(
        content="Raw HTML page text content", schema_model=Article
    )
    assert result.used_llm is True
    assert result.data.title == "Extracted Title"
    assert result.data.content == "Extracted Content Body"
    assert result.retries == 0


def test_local_extractor_retries_on_validation_error(tmp_path):
    mock_llm = MagicMock()
    # First response is invalid json, second response is valid
    mock_llm.create_chat_completion.side_effect = [
        {
            "choices": [{"message": {"content": '{"title": "Only Title Missing Content"}'}}],
            "usage": {"completion_tokens": 10},
        },
        {
            "choices": [
                {
                    "message": {
                        "content": '{"title": "Valid Title", "content": "Valid Content Here"}'
                    }
                }
            ],
            "usage": {"completion_tokens": 15},
        },
    ]

    dummy_model_file = tmp_path / "model.gguf"
    dummy_model_file.write_text("gguf")

    extractor = LocalExtractor(model_path=dummy_model_file, temperature=0.1)
    extractor._llm = mock_llm

    result = extractor.extract(
        content="Raw HTML page text", schema_model=Article, max_retries=2
    )
    assert result.used_llm is True
    assert result.retries == 1
    assert result.data.title == "Valid Title"
