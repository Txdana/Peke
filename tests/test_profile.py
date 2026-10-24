import pytest

from peke.profile import ProfileError, load_profile


def test_profile_defaults():
    profile = load_profile({"url": "https://example.com"})
    assert profile.fetcher == "basic" and profile.max_pages == 1


def test_bad_profile_field_is_clear():
    with pytest.raises(ProfileError, match="Invalid profile"):
        load_profile({"url": "https://example.com", "fetcher": "magic"})


def test_yaml_load(tmp_path):
    path = tmp_path / "profile.yaml"
    path.write_text("name: Example\nurl: https://example.com\nschema_name: Article\n", encoding="utf-8")
    assert load_profile(path).name == "Example"
