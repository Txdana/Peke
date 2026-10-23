"""Tests for Pipeline orchestration."""

from unittest.mock import patch

from peke.fetch import FetchResult
from peke.pipeline import Pipeline, PipelineResult
from peke.profile import TargetProfile


@patch("peke.pipeline.fetch_target")
def test_pipeline_run_direct_json_flow(mock_fetch):
    mock_fetch.return_value = FetchResult(
        url="https://example.com/json",
        status_code=200,
        headers={"content-type": "application/json"},
        text='{"title": "Test Title", "content": "Test Content"}',
        json_data={"title": "Test Title", "content": "Test Content"},
        is_json=True,
        fetcher_used="Fetcher",
        cloudflare_bypassed=False,
    )

    events_captured = []

    def on_event(ev):
        events_captured.append(ev)

    profile = TargetProfile(
        name="Pipeline Test Profile",
        url="https://example.com/json",
        schema_name="Article",
    )

    pipeline = Pipeline(event_callback=on_event)
    result: PipelineResult = pipeline.run(profile)

    assert result.fetch_result is not None
    assert result.extraction_result is not None
    assert result.extraction_result.used_llm is False
    assert result.extraction_result.data.title == "Test Title"
    assert len(events_captured) >= 3
