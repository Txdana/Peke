from pathlib import Path


def test_gui_assets_are_present_in_source_tree() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "src/peke/gui/theme.qss").is_file()
    assert (root / "src/peke/gui/assets/peke.png").is_file()
    assert (root / "src/peke/gui/assets/peke.svg").is_file()
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert '"src/peke/gui/assets/*.svg"' in pyproject
    assert '"src/peke/gui/assets/**/*"' in pyproject


def test_doctor_reports_readiness_without_a_model() -> None:
    from typer.testing import CliRunner

    from peke.cli import app

    result = CliRunner().invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Peke doctor" in result.stdout
    assert "MODEL_PATH" in result.stdout
    assert "PySide6 GUI" in result.stdout


def test_source_distribution_includes_installer_scripts_and_docs() -> None:
    root = Path(__file__).resolve().parents[1]
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert '[tool.hatch.build.targets.sdist]' in pyproject
    assert '"/install.sh"' in pyproject
    assert '"/install.ps1"' in pyproject
    assert '"/docs"' in pyproject
