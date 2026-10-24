#!/usr/bin/env python3
"""Validate built Peke release artifacts before publishing them.

This script is intentionally dependency-light so it can run in CI after the
build step. It does not install packages or access the network.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import tarfile
from email.parser import Parser
from pathlib import Path
from typing import NoReturn
from zipfile import ZipFile

import tomllib


def fail(message: str) -> NoReturn:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def read_project_version(root: Path) -> str:
    try:
        with (root / "pyproject.toml").open("rb") as handle:
            project = tomllib.load(handle)["project"]
        version = str(project["version"])
    except (OSError, KeyError, tomllib.TOMLDecodeError) as exc:
        fail(f"Cannot read project version from pyproject.toml: {exc}")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[a-zA-Z0-9.+-]*)?", version):
        fail(f"Project version is not a valid release version: {version!r}")
    return version


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def manifest_entries(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        fail(f"Cannot read checksum manifest: {exc}")
    for line in lines:
        match = re.fullmatch(r"([a-fA-F0-9]{64})\s+\*?([^\s]+)", line.strip())
        if not match:
            fail(f"Malformed checksum manifest line: {line!r}")
        digest, name = match.groups()
        if name in entries:
            fail(f"Duplicate checksum entry: {name}")
        entries[name] = digest.lower()
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="project root")
    parser.add_argument("--dist", type=Path, default=Path("dist"), help="distribution directory, relative to root unless absolute")
    parser.add_argument("--assets", type=Path, default=Path("release-assets"), help="release asset directory, relative to root unless absolute")
    parser.add_argument("--tag", default="", help="optional release tag such as v0.1.0")
    args = parser.parse_args()

    root = args.root.resolve()
    dist = args.dist if args.dist.is_absolute() else root / args.dist
    assets = args.assets if args.assets.is_absolute() else root / args.assets
    version = read_project_version(root)
    if args.tag:
        tag_version = args.tag.removeprefix("refs/tags/").removeprefix("v")
        if tag_version != version:
            fail(f"Release tag version {tag_version!r} does not match pyproject version {version!r}")

    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))
    if len(wheels) != 1:
        fail(f"Expected exactly one wheel in {dist}, found {len(wheels)}")
    if len(sdists) != 1:
        fail(f"Expected exactly one source distribution in {dist}, found {len(sdists)}")
    wheel, sdist = wheels[0], sdists[0]
    if not wheel.name.lower().startswith(f"peke-{version.lower()}-"):
        fail(f"Wheel filename does not match project version {version}: {wheel.name}")
    if sdist.name != f"peke-{version}.tar.gz":
        fail(f"Source archive does not match project version {version}: {sdist.name}")

    try:
        with ZipFile(wheel) as archive:
            names = set(archive.namelist())
            bad_member = next((name for name in names if name.startswith("/") or ".." in Path(name).parts), None)
            if bad_member:
                fail(f"Unsafe path in wheel: {bad_member}")
            metadata_files = [name for name in names if name.endswith(".dist-info/METADATA")]
            if len(metadata_files) != 1:
                fail("Wheel must contain exactly one dist-info/METADATA")
            metadata = Parser().parsestr(archive.read(metadata_files[0]).decode("utf-8"))
            if metadata.get("Name", "").lower().replace("_", "-") != "peke":
                fail(f"Unexpected wheel distribution name: {metadata.get('Name')!r}")
            if metadata.get("Version") != version:
                fail(f"Wheel metadata version {metadata.get('Version')!r} != {version!r}")
            required = {
                "peke/cli.py",
                "peke/gui/theme.qss",
                "peke/gui/assets/peke.svg",
            }
            missing = sorted(required - names)
            if missing:
                fail(f"Wheel is missing required files: {', '.join(missing)}")
            if not any(name.endswith(".dist-info/entry_points.txt") for name in names):
                fail("Wheel is missing console-script entry points")
    except (OSError, ValueError, KeyError) as exc:
        fail(f"Could not validate wheel {wheel.name}: {exc}")

    try:
        with tarfile.open(sdist, "r:gz") as archive:
            names = set(archive.getnames())
            required_suffixes = (
                "/pyproject.toml", "/README.md", "/LICENSE", "/install.sh",
                "/install.ps1", "/docs/installers.md", "/tests/test_cli.py",
            )
            for suffix in required_suffixes:
                if not any(name.endswith(suffix) for name in names):
                    fail(f"Source distribution is missing {suffix}")
            for member in archive.getmembers():
                if member.name.startswith("/") or ".." in Path(member.name).parts:
                    fail(f"Unsafe path in source archive: {member.name}")
    except (OSError, tarfile.TarError) as exc:
        fail(f"Could not validate source distribution {sdist.name}: {exc}")

    required_assets = [wheel.name, sdist.name, "requirements-hashed.txt"]
    for name in required_assets:
        path = assets / name
        if not path.is_file():
            fail(f"Release asset is missing: {path}")
    manifest_path = assets / "SHA256SUMS"
    entries = manifest_entries(manifest_path)
    for name in required_assets:
        path = assets / name
        if name not in entries:
            fail(f"Checksum manifest has no entry for {name}")
        actual = sha256(path)
        if actual != entries[name]:
            fail(f"Checksum mismatch for {name}: expected {entries[name]}, got {actual}")

    extra = sorted(set(entries) - set(required_assets))
    if extra:
        fail(f"Unexpected checksum entries not present in the release asset contract: {', '.join(extra)}")
    print(f"Release validation passed for Peke {version}")
    print(f"  Wheel: {wheel.name} ({wheel.stat().st_size:,} bytes)")
    print(f"  Source: {sdist.name} ({sdist.stat().st_size:,} bytes)")
    print(f"  Verified assets: {', '.join(required_assets)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
