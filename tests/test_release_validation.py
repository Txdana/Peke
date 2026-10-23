from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_release.py"


def test_release_validator_rejects_tag_version_mismatch() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(ROOT), "--tag", "v99.99.99"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "does not match pyproject version" in result.stderr


def test_release_validator_is_included_in_sdist_contract() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"/scripts/validate_release.py"' in pyproject


def test_release_workflow_runs_artifact_validation_after_checksums() -> None:
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "Validate release assets and tag version" in workflow
    assert "scripts/validate_release.py --tag" in workflow
    assert "build==1.2.2.post1 twine==6.1.0" in workflow
