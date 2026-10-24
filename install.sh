#!/bin/sh
# Verify the published release wheel before installing it with pipx.
# No sudo, elevation, model downloads, or shell-evaluated remote code.
set -eu

REPO="Txdana/Peke"
PEKE_VERSION="${PEKE_VERSION:-}"
NO_MODIFY_PATH=0
DRY_RUN=0
YES=0
FROM_SOURCE=0
for arg in "$@"; do
  case "$arg" in
    --no-modify-path) NO_MODIFY_PATH=1 ;;
    --dry-run) DRY_RUN=1 ;;
    --yes) YES=1 ;;
    --from-source) FROM_SOURCE=1 ;;
    --uninstall)
      printf '%s\n' "Uninstall Peke from pipx and remove desktop integration?"
      if [ "$YES" -ne 1 ]; then
        printf 'Continue [y/N]? '
        if [ -r /dev/tty ]; then read -r answer </dev/tty; else answer=n; fi
        [ "$answer" = y ] || [ "$answer" = Y ] || exit 0
      fi
      if command -v peke >/dev/null 2>&1; then
        peke desktop uninstall || true
      fi
      if command -v pipx >/dev/null 2>&1; then
        pipx uninstall peke || true
      else
        printf '%s\n' "pipx was not found; no package was removed."
      fi
      printf '%s\n' "Peke package and desktop integration removed if installed. User configuration was retained."
      exit 0
      ;;
    *) printf 'Unknown option: %s\n' "$arg" >&2; exit 2 ;;
  esac
done

printf '%s\n' "Peke release installer" "Installs a published release wheel after SHA-256 verification." \
  "No administrator access is used; model weights are never downloaded."
OS="$(uname -s)"
ARCH="$(uname -m)"
case "$OS:$ARCH" in
  Linux:x86_64|Linux:aarch64|Darwin:x86_64|Darwin:arm64) ;;
  *) printf 'Unsupported platform/architecture: %s:%s\n' "$OS" "$ARCH" >&2; exit 1 ;;
esac
command -v python3 >/dev/null 2>&1 || { printf '%s\n' "Python 3.10+ is required." >&2; exit 1; }
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)' || {
  printf '%s\n' "Python 3.10+ is required." >&2; exit 1;
}
if [ "$DRY_RUN" -eq 1 ]; then
  if [ "$FROM_SOURCE" -eq 1 ]; then
    printf '%s\n' "Dry run: would install the current source tree with pipx using the gui extra."
  else
    if [ -n "$PEKE_VERSION" ]; then version="$PEKE_VERSION"; else version="latest stable release"; fi
    printf 'Dry run: would download the %s GitHub release, verify the wheel and hash-locked requirements, then install with pipx.\n' "$version"
  fi
  exit 0
fi

command -v pipx >/dev/null 2>&1 || {
  printf '%s\n' "pipx is required. Install it for your user with: python3 -m pip install --user pipx" >&2
  exit 1
}

if [ "$FROM_SOURCE" -eq 1 ]; then
  printf '%s\n' "Installing Peke from local source tree using pipx..."
  pipx install --force --editable '.[gui]'
  if [ "$NO_MODIFY_PATH" -eq 0 ]; then
    case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) printf '%s\n' "If peke is not found, add $HOME/.local/bin to PATH and reopen your terminal." ;; esac
  fi
  if command -v peke >/dev/null 2>&1; then
    peke desktop install || true
  fi
  printf '\n%s\n' "Installed Peke from source. Start Peke with: peke launch"
  exit 0
fi

command -v curl >/dev/null 2>&1 || { printf '%s\n' "curl is required for downloading releases." >&2; exit 1; }

if [ -n "$PEKE_VERSION" ]; then
  PEKE_VERSION="${PEKE_VERSION#v}"
  API_URL="https://api.github.com/repos/$REPO/releases/tags/v$PEKE_VERSION"
else
  API_URL="https://api.github.com/repos/$REPO/releases/latest"
fi
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/peke-install.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT HUP INT TERM
curl --fail --location --silent --show-error --proto '=https' --tlsv1.2 "$API_URL" -o "$TMP_DIR/release.json" 2>/dev/null || {
  if [ -n "$PEKE_VERSION" ]; then
    printf '%s\n' "Could not find or access Peke release v$PEKE_VERSION on GitHub." \
      "Confirm that this tag has a published release on https://github.com/$REPO." \
      "For source installation, run: git clone https://github.com/$REPO.git && cd Peke && ./install.sh --from-source" >&2
  else
    printf '%s\n' "No published Peke release was found on GitHub (the releases page may be empty)." \
      "For source installation, run:" \
      "  git clone https://github.com/$REPO.git && cd Peke && ./install.sh --from-source" \
      "Or install directly with pip:" \
      "  python3 -m pip install -e '.[gui]'" >&2
  fi
  exit 1
}
python3 - "$TMP_DIR/release.json" "$TMP_DIR/assets.txt" <<'PY'
import json, re, sys
from pathlib import Path
release = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assets = {item["name"]: item.get("browser_download_url", "") for item in release.get("assets", [])}
wheels = sorted(name for name in assets if name.startswith("peke-") and name.endswith(".whl"))
if len(wheels) != 1:
    raise SystemExit(f"Expected exactly one Peke wheel in release; found {len(wheels)}")
wheel = wheels[0]
requirements = "requirements-hashed.txt"
if not re.fullmatch(r"[A-Za-z0-9_.+-]+\.whl", wheel):
    raise SystemExit("Unexpected wheel filename in release metadata")
if requirements not in assets or "SHA256SUMS" not in assets:
    raise SystemExit("Release must contain requirements-hashed.txt and SHA256SUMS")
Path(sys.argv[2]).write_text("\n".join([wheel, assets[wheel], assets["SHA256SUMS"], requirements, assets[requirements]]) + "\n", encoding="utf-8")
PY
WHEEL_NAME="$(sed -n '1p' "$TMP_DIR/assets.txt")"
WHEEL_URL="$(sed -n '2p' "$TMP_DIR/assets.txt")"
SUMS_URL="$(sed -n '3p' "$TMP_DIR/assets.txt")"
REQUIREMENTS_NAME="$(sed -n '4p' "$TMP_DIR/assets.txt")"
REQUIREMENTS_URL="$(sed -n '5p' "$TMP_DIR/assets.txt")"
case "$WHEEL_URL:$SUMS_URL:$REQUIREMENTS_URL" in https://github.com/*:https://github.com/*:https://github.com/*) ;; *) printf '%s\n' "Release asset URL failed HTTPS/host validation." >&2; exit 1 ;; esac
curl --fail --location --silent --show-error --proto '=https' --tlsv1.2 "$WHEEL_URL" -o "$TMP_DIR/$WHEEL_NAME"
curl --fail --location --silent --show-error --proto '=https' --tlsv1.2 "$SUMS_URL" -o "$TMP_DIR/SHA256SUMS"
curl --fail --location --silent --show-error --proto '=https' --tlsv1.2 "$REQUIREMENTS_URL" -o "$TMP_DIR/$REQUIREMENTS_NAME"
verify_hash() {
  name="$1"
  file="$2"
  expected="$(awk -v target="$name" '$2 == target || $2 == "*" target {print $1}' "$TMP_DIR/SHA256SUMS")"
  [ "$(printf '%s\n' "$expected" | grep -Ec '^[a-fA-F0-9]{64}$')" -eq 1 ] || {
    printf 'The release manifest has no unique SHA-256 entry for %s.\n' "$name" >&2; exit 1;
  }
  if command -v sha256sum >/dev/null 2>&1; then actual="$(sha256sum "$file" | awk '{print $1}')"; else actual="$(shasum -a 256 "$file" | awk '{print $1}')"; fi
  [ "$(printf '%s' "$actual" | tr '[:upper:]' '[:lower:]')" = "$(printf '%s' "$expected" | tr '[:upper:]' '[:lower:]')" ] || {
    printf 'SHA-256 verification failed for %s; refusing to continue.\n' "$name" >&2; exit 1;
  }
}
verify_hash "$WHEEL_NAME" "$TMP_DIR/$WHEEL_NAME"
verify_hash "$REQUIREMENTS_NAME" "$TMP_DIR/$REQUIREMENTS_NAME"
printf 'Verified %s and hash-locked runtime requirements. Installing...\n' "$WHEEL_NAME"
pipx install --force --pip-args='--no-deps' "$TMP_DIR/$WHEEL_NAME"
if ! pipx runpip peke install --require-hashes -r "$TMP_DIR/$REQUIREMENTS_NAME"; then
  pipx uninstall peke >/dev/null 2>&1 || true
  printf '%s\n' "Locked dependency installation failed; Peke was removed to avoid leaving a broken install." >&2
  exit 1
fi

if [ "$NO_MODIFY_PATH" -eq 0 ]; then
  case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) printf '%s\n' "If peke is not found, add $HOME/.local/bin to PATH and reopen your terminal." ;; esac
fi

# Register desktop application shortcut & icon
if command -v peke >/dev/null 2>&1; then
  peke desktop install || true
fi

printf '\n%s\n' "Installed. Start Peke with: peke launch" "User configuration is managed by Peke and is not removed by uninstall."
