import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_install_scripts_verify_release_artifact_before_install() -> None:
    shell = (ROOT / "install.sh").read_text(encoding="utf-8")
    powershell = (ROOT / "install.ps1").read_text(encoding="utf-8")
    assert "set -eu" in shell
    assert "--dry-run" in shell
    assert "--uninstall" in shell
    assert "SHA256SUMS" in shell
    assert "requirements-hashed.txt" in shell
    assert "sha256sum" in shell and "shasum -a 256" in shell
    assert "pipx install --force --pip-args='--no-deps'" in shell
    assert "pipx runpip peke install --require-hashes -r" in shell
    assert "Set-StrictMode" in powershell
    assert "$DryRun" in powershell
    assert "$Uninstall" in powershell
    assert "$FromSource" in powershell
    assert "pipx install --force --editable '.[gui]'" in powershell
    assert "SHA256SUMS" in powershell
    assert "requirements-hashed.txt" in powershell
    assert "Get-FileHash -Algorithm SHA256" in powershell
    assert "--require-hashes -r $requirementsPath" in powershell


def test_posix_installer_syntax_and_dry_run() -> None:
    result = subprocess.run(["sh", "-n", str(ROOT / "install.sh")], check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    env = os.environ.copy()
    env["PEKE_VERSION"] = "0.1.0"
    result = subprocess.run(["sh", str(ROOT / "install.sh"), "--dry-run"], cwd=ROOT, env=env, check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "hash-locked requirements" in result.stdout
    assert "0.1.0" in result.stdout


def test_release_workflow_generates_checksums_and_tests_installers() -> None:
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "sha256sum *.whl *.tar.gz requirements-hashed.txt" in workflow
    assert "uv export --locked" in workflow
    assert 'version: "0.10.0"' in workflow
    assert "installer-smoke" in workflow
    assert "macos-latest" in workflow
    assert "windows-latest" in workflow
    assert "twine check dist/*" in workflow
    assert "Smoke-install wheel without resolving dependencies" in workflow
