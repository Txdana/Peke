"""Tests for target profile model and loading."""

import pytest

from peke.profile import ProfileError, TargetProfile, load_profile


def test_target_profile_defaults():
    profile = TargetProfile(url="https://example.com")
    assert profile.url == "https://example.com"
    assert profile.fetcher == "Fetcher"
    assert profile.headers == {}
    assert profile.schema_name == "Article"


def test_load_profile_from_dict():
    data = {
        "name": "Dict Profile",
        "url": "https://example.com/api",
        "fetcher": "StealthyFetcher",
        "headers": {"X-Test": "123"},
        "schema_name": "Product",
    }
    profile = load_profile(data)
    assert profile.name == "Dict Profile"
    assert profile.fetcher == "StealthyFetcher"
    assert profile.headers["X-Test"] == "123"
    assert profile.schema_name == "Product"


def test_load_profile_from_yaml(tmp_path):
    yaml_file = tmp_path / "test_profile.yaml"
    yaml_file.write_text(
        """
name: YAML Profile
url: https://example.com/yaml
fetcher: Fetcher
schema_name: Listing
"""
    )
    profile = load_profile(yaml_file)
    assert profile.name == "YAML Profile"
    assert profile.url == "https://example.com/yaml"
    assert profile.schema_name == "Listing"


def test_load_profile_nonexistent_file():
    with pytest.raises(ProfileError) as exc_info:
        load_profile("nonexistent_profile_12345.yaml")
    assert "file not found" in str(exc_info.value)


def test_load_profile_invalid_yaml(tmp_path):
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("[[invalid yaml string:::")
    with pytest.raises(ProfileError):
        load_profile(bad_yaml)
