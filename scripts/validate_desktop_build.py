"""Static checks for the Windows desktop packaging contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    spec = (ROOT / "packaging/windows/Peke.spec").read_text(encoding="utf-8")
    iss = (ROOT / "packaging/windows/Peke.iss").read_text(encoding="utf-8")
    installer = (ROOT / "install.ps1").read_text(encoding="utf-8")
    assert "console=False" in spec, "PyInstaller must use windowed mode"
    assert "peke.ico" in spec, "PyInstaller must use the application icon"
    assert "PrivilegesRequired=lowest" in iss, "Installer should be per-user by default"
    assert "{autoprograms}\\Peke" in iss, "Start menu shortcut is missing"
    assert "Tasks: desktopicon" in iss, "Optional desktop shortcut is missing"
    assert "UninstallDisplayIcon" in iss, "Uninstaller registration is missing"
    assert "rev-parse HEAD" in installer, "Installer must verify the checked-out commit"
    assert "PinnedCommit" in installer, "Installer must pin a source revision"
    assert '"fetch", "--depth", "1", "origin", $PinnedCommit' in installer, "Installer should fetch the pinned revision only"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
