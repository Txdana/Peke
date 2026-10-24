from unittest.mock import MagicMock

from peke.config import Settings
from peke.extract import Extractor
from peke.schemas import Article


def test_retry_after_invalid_model_output(tmp_path):
    model_path = tmp_path / "model.gguf"
    model_path.write_text("stub", encoding="utf-8")
    extractor = Extractor(Settings(model_path=model_path))
    llm = MagicMock()
    llm.create_chat_completion.side_effect = [
        {"choices": [{"message": {"content": '{"title": 2}'}}], "usage": {}},
        {"choices": [{"message": {"content": '{"title":"ok","content":"text"}'}}], "usage": {"completion_tokens": 4}},
    ]
    extractor._llm = llm
    result = extractor.run("Source text", Article)
    assert result.model.title == "ok"
    assert result.attempts == 2
    assert llm.create_chat_completion.call_count == 2


def test_long_input_is_chunked_and_list_fields_merge(tmp_path):
    model_path = tmp_path / "model.gguf"
    model_path.write_text("stub", encoding="utf-8")
    settings = Settings(model_path=model_path, max_input_chars=15)
    extractor = Extractor(settings)
    llm = MagicMock()
    llm.create_chat_completion.side_effect = [
        {"choices": [{"message": {"content": '{"title":"first","tags":["a"]}'}}], "usage": {}},
        {"choices": [{"message": {"content": '{"title":"second","tags":["b"]}'}}], "usage": {}},
    ]
    extractor._llm = llm
    result = extractor.run("paragraph one\nparagraph two", Article)
    assert result.model.title == "first"
    assert result.model.tags == ["a", "b"]
    assert llm.create_chat_completion.call_count >= 2
