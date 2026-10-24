from pathlib import Path


def test_gui_assets_are_present_in_source_tree() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "src/peke/gui/theme.qss").is_file()
    assert (root / "src/peke/gui/assets/peke.png").is_file()
    assert (root / "src/peke/gui/assets/peke.svg").is_file()
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert 'packages = ["src/peke", "src/searx"]' in pyproject
    assert '"src/searx/**"' in pyproject
    assert '"licenses/SEARXNG-LICENSE" = "searx/SEARXNG-LICENSE"' in pyproject
    assert (root / "src/searx/webapp.py").is_file()
    assert (root / "src/searx/settings.yml").is_file()
    assert (root / "licenses/SEARXNG-LICENSE").is_file()
    assert (root / "licenses/SEARXNG-REQUIREMENTS.txt").is_file()
    assert (root / "vendor/searxng-master-source-archive.zip").is_file()


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
    assert '"/src/searx"' in pyproject
    assert '"/licenses"' in pyproject
    assert '"/vendor/searxng-master-source-archive.zip"' in pyproject


def test_bundled_searxng_is_windows_safe_and_docker_free() -> None:
    root = Path(__file__).resolve().parents[1]
    runtime = (root / "src/peke/searxng_runtime.py").read_text(encoding="utf-8")
    valkey = (root / "src/searx/valkeydb.py").read_text(encoding="utf-8")
    gui = (root / "src/peke/gui/panes/search_page.py").read_text(encoding="utf-8")
    assert '"-m", "searx.webapp"' in runtime
    assert '["docker"' not in runtime.lower()
    assert "except ImportError" in valkey and "import pwd" in valkey
    assert "Start bundled SearXNG" in gui
    assert "No Docker installation is required" in gui
