[CmdletBinding()]
param(
    [string]$PEKE_VERSION = $env:PEKE_VERSION,
    [switch]$NoModifyPath,
    [switch]$DryRun,
    [switch]$Yes,
    [switch]$Uninstall,
    [switch]$FromSource
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$Repo = "Txdana/Peke"

# Prevent pip/pipx Unicode status messages from failing in legacy Windows console code pages.
$env:PYTHONIOENCODING = "utf-8"

Write-Host "Peke release installer"
Write-Host "Verifies the release wheel and hash-locked runtime requirements before installation."
Write-Host "The Peke wheel bundles SearXNG for local search; Docker is not required."
Write-Host "No administrator elevation is used; model weights are never downloaded."

if ($Uninstall) {
    if (-not $Yes) {
        $answer = Read-Host "Uninstall Peke from pipx and remove desktop integration? User configuration is retained [y/N]"
        if ($answer -notin @("y", "Y")) { return }
    }
    if (Get-Command peke -ErrorAction SilentlyContinue) {
        peke desktop uninstall
    }
    if (Get-Command pipx -ErrorAction SilentlyContinue) {
        pipx uninstall peke
        if ($LASTEXITCODE -ne 0) { throw "pipx uninstall failed with exit code $LASTEXITCODE" }
    } else {
        Write-Host "pipx was not found; no package was removed."
    }
    Write-Host "Peke package and desktop integration removed if installed. User configuration was retained."
    return
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $python) { throw "Python 3.10+ is required. Install Python for your user and retry." }
$versionText = & $python.Source -c "import sys; print('%s.%s' % sys.version_info[:2])"
if ($LASTEXITCODE -ne 0 -or [version]$versionText -lt [version]"3.10") { throw "Python 3.10+ is required." }
if ($DryRun) {
    if ($FromSource) {
        Write-Host "Dry run: would install the current source tree with pipx using the GUI extra and bundled SearXNG dependencies."
    } else {
        $target = if ($PEKE_VERSION) { "version $PEKE_VERSION" } else { "latest stable release" }
        Write-Host "Dry run: would download $target, verify SHA256SUMS and locked requirements, then install with pipx."
    }
    return
}
if (-not (Get-Command pipx -ErrorAction SilentlyContinue)) {
    Write-Host "pipx was not found; installing it for your user (no administrator rights needed)..."
    & $python.Source -m pip install --user --quiet pipx
    if ($LASTEXITCODE -ne 0) {
        throw "Could not install pipx automatically. Install it yourself with: python -m pip install --user pipx"
    }
    $script:PekePython = $python.Source
    # Until the user's PATH is refreshed in a new terminal, route 'pipx' through the Python module
    # so the rest of this installer (and this session) works immediately.
    function pipx { & $script:PekePython -m pipx @args }
    if (-not $NoModifyPath) {
        & $python.Source -m pipx ensurepath | Out-Null
    }
    $pipxBin = (& $python.Source -m pipx environment --value PIPX_BIN_DIR 2>$null)
    if ($pipxBin -and (Test-Path -LiteralPath "$pipxBin") -and (($env:Path -split ';') -notcontains "$pipxBin")) {
        $env:Path = "$pipxBin;$env:Path"   # current session only; ensurepath handles future terminals
    }
    & $python.Source -m pipx --version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "pipx was installed but could not be started. Open a new terminal and run this installer again."
    }
    Write-Host "pipx installed."
}

if ($FromSource) {
    Write-Host "Installing this Peke source tree, including bundled SearXNG, into the user-level pipx environment."
    Push-Location $PSScriptRoot
    try {
        pipx install --force --editable '.[gui]'
        if ($LASTEXITCODE -ne 0) { throw "pipx source installation failed with exit code $LASTEXITCODE" }
    } finally {
        Pop-Location
    }
    if (-not $NoModifyPath) {
        Write-Host "If peke is not recognized, add your pipx binary directory to the user PATH and open a new terminal."
    }
    if (Get-Command peke -ErrorAction SilentlyContinue) { peke desktop install }
    Write-Host "Installed current source. Start Peke with: peke launch"
    Write-Host "Source mode resolves dependencies from the configured package index; use the default mode for verified release assets."
    return
}

if ($PEKE_VERSION) {
    $version = $PEKE_VERSION.TrimStart('v')
    $apiUrl = "https://api.github.com/repos/$Repo/releases/tags/v$version"
} else {
    $apiUrl = "https://api.github.com/repos/$Repo/releases/latest"
}
try {
    $release = Invoke-RestMethod -Uri $apiUrl -Headers @{ "Accept" = "application/vnd.github+json"; "X-GitHub-Api-Version" = "2022-11-28" }
} catch {
    if ($PEKE_VERSION) {
        throw "Could not find or access Peke release v$version on GitHub. Confirm that this tag has a published release with the wheel, requirements-hashed.txt, and SHA256SUMS. For source installation, clone https://github.com/$Repo, cd into the checkout, and run .\install.ps1 -FromSource."
    }
    throw "No latest stable Peke release is published on GitHub yet (the Releases page may be empty). For source installation, run: git clone https://github.com/$Repo; cd Peke; .\install.ps1 -FromSource. For verified release installation, the maintainer must publish a release containing the wheel, requirements-hashed.txt, and SHA256SUMS."
}
$wheels = @($release.assets | Where-Object { $_.name -like "peke-*.whl" })
if ($wheels.Count -ne 1) { throw "Expected exactly one Peke wheel in release; found $($wheels.Count). Refusing to install an incomplete release." }
$wheelAsset = $wheels[0]
$requirementsAsset = $release.assets | Where-Object { $_.name -eq "requirements-hashed.txt" } | Select-Object -First 1
$sumsAsset = $release.assets | Where-Object { $_.name -eq "SHA256SUMS" } | Select-Object -First 1
if (-not $requirementsAsset -or -not $sumsAsset) { throw "Release must contain requirements-hashed.txt and SHA256SUMS." }
foreach ($asset in @($wheelAsset, $requirementsAsset, $sumsAsset)) {
    if ($asset.browser_download_url -notmatch '^https://github\.com/') { throw "Unexpected release asset URL host." }
}
$temp = Join-Path ([IO.Path]::GetTempPath()) ("peke-install-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temp | Out-Null
try {
    $wheelPath = Join-Path $temp $wheelAsset.name
    $requirementsPath = Join-Path $temp "requirements-hashed.txt"
    $sumsPath = Join-Path $temp "SHA256SUMS"
    Invoke-WebRequest -Uri $wheelAsset.browser_download_url -OutFile $wheelPath
    Invoke-WebRequest -Uri $requirementsAsset.browser_download_url -OutFile $requirementsPath
    Invoke-WebRequest -Uri $sumsAsset.browser_download_url -OutFile $sumsPath

    foreach ($target in @(@{ Name = $wheelAsset.name; Path = $wheelPath }, @{ Name = $requirementsAsset.name; Path = $requirementsPath })) {
        $escapedName = [regex]::Escape($target.Name)
        $manifestLines = @(Get-Content $sumsPath | Where-Object { $_ -match ("^([a-fA-F0-9]{64})\s+\*?" + $escapedName + "$") })
        if ($manifestLines.Count -ne 1) { throw "The release manifest has no unique SHA-256 entry for $($target.Name)." }
        $expected = [regex]::Match($manifestLines[0], '^([a-fA-F0-9]{64})').Groups[1].Value.ToLowerInvariant()
        $actual = (Get-FileHash -Algorithm SHA256 -Path $target.Path).Hash.ToLowerInvariant()
        if ($actual -ne $expected) { throw "SHA-256 verification failed for $($target.Name); refusing to continue." }
    }

    Write-Host "Verified $($wheelAsset.name) and hash-locked runtime requirements. Installing..."
    pipx install --force --pip-args="--no-deps" $wheelPath
    if ($LASTEXITCODE -ne 0) { throw "pipx wheel installation failed with exit code $LASTEXITCODE" }
    pipx runpip peke install --require-hashes -r $requirementsPath
    if ($LASTEXITCODE -ne 0) {
        pipx uninstall peke | Out-Null
        throw "Locked dependency installation failed; Peke was removed to avoid leaving a broken install."
    }
} finally {
    Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
}
if (-not $NoModifyPath) {
    Write-Host "If peke is not recognized, add your pipx binary directory to the user PATH and open a new terminal."
}
if (Get-Command peke -ErrorAction SilentlyContinue) {
    peke desktop install
}
Write-Host "Installed. Start Peke with: peke launch"
Write-Host "User configuration is managed by Peke and is not removed by uninstall."
