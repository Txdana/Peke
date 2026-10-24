from pathlib import Path


def test_windows_desktop_release_contract():
    root = Path(__file__).resolve().parents[1]
    installer = (root / "install.ps1").read_text(encoding="utf-8")
    spec = (root / "packaging/windows/Peke.spec").read_text(encoding="utf-8")
    iss = (root / "packaging/windows/Peke.iss").read_text(encoding="utf-8")
    assert "REPLACE_WITH_FULL_40_CHARACTER_COMMIT_SHA" in installer
    assert "rev-parse HEAD" in installer
    assert "if ($DryRun)" in installer
    assert "winget" in installer
    assert "compile a local setup EXE" in installer
    assert "Start-Process -FilePath $installedExe" in installer
    assert "console=False" in spec
    assert "peke.ico" in spec
    assert "{autoprograms}\\Peke" in iss
    assert "Tasks: desktopicon" in iss
    assert "UninstallDisplayIcon" in iss
    assert (root / "src/peke/gui/assets/peke.ico").is_file()
