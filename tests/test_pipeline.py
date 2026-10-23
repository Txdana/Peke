from unittest.mock import patch
from peke.config import Settings
from peke.fetch import FetchResult
from peke.pipeline import Pipeline
from peke.profile import load_profile


def test_api_mode_skips_llm():
    payload = {"title": "Fixture", "content": "Hello"}
    fetched = FetchResult("https://example.com", 200, "application/json", str(payload), payload, 1.0)
    with patch("peke.pipeline.fetch", return_value=fetched) as mocked_fetch:
        result = Pipeline(settings=Settings(None)).run(load_profile({"url": "https://example.com", "mode": "api", "schema_name": "Article"}))
    assert result.records[0].title == "Fixture"
    assert result.extraction_result is None
    mocked_fetch.assert_called_once()
