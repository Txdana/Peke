# Peke installer fix — replacement files

These files replace `install.ps1`, `install.sh`, and `NOTICE` in `Txdana/Peke`.

- `install.ps1`: avoids the Windows console Unicode issue and reports missing releases clearly; source mode remains available.
- `install.sh`: adds `--from-source` and clear diagnostics for an unpublished release while retaining SHA-256 verification for release installs.
- `NOTICE`: records Txdana as original creator while retaining SearXNG third-party notice.

## Replace on GitHub
For each file, open the matching file in `https://github.com/Txdana/Peke`, click Edit, replace the entire contents with the corresponding file in this package, and commit. Prefer a branch and pull request if you want CI to test it before merging.

## Install source before the first release
Windows:
```powershell
git clone https://github.com/Txdana/Peke.git
cd Peke
.\install.ps1 -FromSource
```
Linux/macOS:
```sh
git clone https://github.com/Txdana/Peke.git
cd Peke
./install.sh --from-source
```

## Publish a verified release
The existing `.github/workflows/release.yml` is tag-triggered and currently `pyproject.toml` declares version `0.3.0`. Once the final code is committed and CI passes, push the matching tag to run the release workflow:
```sh
git tag v0.3.0
git push origin v0.3.0
```
Do not create the tag until ready to publish. The workflow should publish the wheel, source archive, `requirements-hashed.txt`, and `SHA256SUMS` after its validation jobs pass.

## Checks
The shell installer is checked with `sh -n` and its dry-run. The Windows workflow should run the PowerShell parser and dry-run on `windows-latest`; this environment does not have PowerShell installed.
