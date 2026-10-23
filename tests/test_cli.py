from typer.testing import CliRunner
from peke.cli import app


def test_validate_command(tmp_path):
    path = tmp_path / "profile.yaml"
    path.write_text("url: https://example.com\nschema_name: Article\n", encoding="utf-8")
    result = CliRunner().invoke(app, ["validate", str(path)])
    assert result.exit_code == 0


def test_invalid_profile_exit_code(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("url: https://example.com\nfetcher: invalid\n", encoding="utf-8")
    result = CliRunner().invoke(app, ["validate", str(path)])
    assert result.exit_code == 2
