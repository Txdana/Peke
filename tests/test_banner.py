from io import StringIO

from rich.console import Console

from peke.banner import print_banner, rea_available


def test_banner_plain_text_for_non_tty() -> None:
    stream = StringIO()
    console = Console(file=stream, force_terminal=False, color_system=None)
    print_banner(console, None)
    output = stream.getvalue()
    assert "PEKE" in output
    assert "[REA CLI Missing]" in output
    assert "Scrapling" in output
    assert "Clean JSON Formatted" in output
    assert "Cloudflare Bypassed" not in output
    assert "\x1b[" not in output


def test_no_color_forces_plain_banner(monkeypatch) -> None:
    stream = StringIO()
    console = Console(file=stream, force_terminal=True, color_system="truecolor")
    monkeypatch.setenv("NO_COLOR", "1")
    print_banner(console, None)
    assert "\x1b[" not in stream.getvalue()


def test_rea_command_is_only_best_effort(monkeypatch) -> None:
    monkeypatch.setattr("peke.banner.shutil.which", lambda executable: "/bin/rea")
    assert rea_available("rea --stdio")
    assert not rea_available(None)
    assert not rea_available("'")


def test_version_command_has_banner_and_version() -> None:
    from typer.testing import CliRunner
    from peke.cli import app

    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "PEKE" in result.stdout
    assert "peke 0.1.0" in result.stdout


def test_version_command_can_disable_banner() -> None:
    from typer.testing import CliRunner
    from peke.cli import app

    result = CliRunner().invoke(app, ["--version", "--no-banner"])
    assert result.exit_code == 0
    assert "PEKE" not in result.stdout
    assert "peke 0.1.0" in result.stdout


def test_banner_uses_color_on_tty_when_allowed(monkeypatch) -> None:
    stream = StringIO()
    console = Console(file=stream, force_terminal=True, color_system="truecolor")
    monkeypatch.delenv("NO_COLOR", raising=False)
    print_banner(console, None)
    assert "\x1b[" in stream.getvalue()
