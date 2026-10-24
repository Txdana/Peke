[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$NoLaunch,
    [switch]$NoBootstrap,
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA "Programs\Peke")
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Release maintainers MUST replace this with the full 40-character commit SHA
# of the source revision that contains this installer before publishing.
$Repo = "https://github.com/Txdana/Peke.git"
$PinnedCommit = "REPLACE_WITH_FULL_40_CHARACTER_COMMIT_SHA"
$AppName = "Peke"
$WorkRoot = Join-Path ([IO.Path]::GetTempPath()) ("peke-source-build-" + [guid]::NewGuid().ToString("N"))

function Assert-ValidPin {
    if ($PinnedCommit -notmatch '^[0-9a-f]{40}$') {
        throw "Installer source revision is not release-pinned. Maintainers must set PinnedCommit to a full 40-character Git commit SHA."
    }
}
function Invoke-Checked([string]$File, [string[]]$Args) {
    & $File @Args
    if ($LASTEXITCODE -ne 0) { throw "'$File $($Args -join ' ')' failed with exit code $LASTEXITCODE." }
}
Write-Host "Peke source-build installer"
Write-Host "Pinned revision: $PinnedCommit"
Write-Host "Builds Peke and its setup EXE locally; no installer binary is hosted in the repository and no model is downloaded."
if ($DryRun) {
    if ($PinnedCommit -notmatch '^[0-9a-f]{40}$') { Write-Warning "PinnedCommit is not configured yet; a real install will refuse to run until a reviewed source SHA is committed." }
    Write-Host "DRY RUN: would ensure Git, Python 3.11 x64, and Inno Setup 6 are available (using winget when needed), fetch and verify $PinnedCommit, build Peke.exe, compile a local setup EXE, install it to $InstallRoot, and launch Peke."
    return
}
Assert-ValidPin

function Find-ToolPath([string]$Name, [string[]]$Candidates = @()) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($candidate in $Candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) { return $candidate }
    }
    return $null
}
function Install-WingetPackage([string]$Id) {
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) { throw "winget is unavailable. Install App Installer from Microsoft Store, then rerun this command." }
    Write-Host "Installing build prerequisite $Id with winget..."
    & $winget.Source install --id $Id --exact --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw "winget could not install $Id (exit code $LASTEXITCODE). Install it manually and retry." }
}

$git = Find-ToolPath "git.exe" @((Join-Path $env:ProgramFiles "Git\cmd\git.exe"), (Join-Path ${env:ProgramFiles(x86)} "Git\cmd\git.exe"))
$python = Find-ToolPath "python.exe" @((Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"), (Join-Path $env:ProgramFiles "Python311\python.exe"))
$iscc = Find-ToolPath "ISCC.exe" @((Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"), (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"))
if (-not $NoBootstrap) {
    if (-not $git) { Install-WingetPackage "Git.Git" }
    if (-not $python) { Install-WingetPackage "Python.Python.3.11" }
    if (-not $iscc) { Install-WingetPackage "JRSoftware.InnoSetup" }
    # winget installers may not refresh this PowerShell process' PATH. Probe standard locations again.
    $git = Find-ToolPath "git.exe" @((Join-Path $env:ProgramFiles "Git\cmd\git.exe"), (Join-Path ${env:ProgramFiles(x86)} "Git\cmd\git.exe"))
    $python = Find-ToolPath "python.exe" @((Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"), (Join-Path $env:ProgramFiles "Python311\python.exe"))
    $iscc = Find-ToolPath "ISCC.exe" @((Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"), (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"))
}
if (-not $git) { throw "Git for Windows was not found after prerequisite setup. Install Git and retry." }
if (-not $python) { throw "Python 3.11 x64 was not found after prerequisite setup. Install Python 3.11 x64 and retry." }
if (-not $iscc) { throw "Inno Setup 6 compiler (ISCC.exe) was not found after prerequisite setup. Install Inno Setup 6 and retry." }
$pythonVersion = & $python --version 2>&1
if ($pythonVersion -notmatch '^Python 3\.(11|12)\.') { throw "Python 3.11 or later is required; found '$pythonVersion'." }
New-Item -ItemType Directory -Path $WorkRoot | Out-Null
try {
    $source = Join-Path $WorkRoot "source"
    Invoke-Checked $git @("init", $source)
    Invoke-Checked $git @("-C", $source, "remote", "add", "origin", $Repo)
    Invoke-Checked $git @("-C", $source, "fetch", "--depth", "1", "origin", $PinnedCommit)
    Invoke-Checked $git @("-C", $source, "checkout", "--detach", "FETCH_HEAD")
    $actual = (& $git -C $source rev-parse HEAD).Trim().ToLowerInvariant()
    if ($LASTEXITCODE -ne 0 -or $actual -ne $PinnedCommit) { throw "Source revision verification failed. Expected $PinnedCommit; got $actual. Refusing to build." }

    $venv = Join-Path $source ".venv-build"
    Invoke-Checked $python @("-m", "venv", $venv)
    $python = Join-Path $venv "Scripts\python.exe"
    $pip = @("-m", "pip", "install", "--disable-pip-version-check", "--upgrade", "pip")
    Invoke-Checked $python $pip
    Invoke-Checked $python @("-m", "pip", "install", ".[gui]", "pyinstaller==6.16.0")
    Invoke-Checked $python @("-m", "PyInstaller", "packaging/windows/Peke.spec", "--clean", "--noconfirm")
    $exe = Join-Path $source "dist\Peke\Peke.exe"
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw "PyInstaller did not produce dist\Peke\Peke.exe." }

    Invoke-Checked $iscc @("/DAppVersion=0.3.0", (Join-Path $source "packaging\windows\Peke.iss"))
    $setup = Join-Path $source "dist-installer\Peke-Setup-0.3.0-x64.exe"
    if (-not (Test-Path -LiteralPath $setup -PathType Leaf)) { throw "Inno Setup did not produce the expected setup executable." }
    if ($NoLaunch) {
        $savedSetup = Join-Path (Get-Location).Path "Peke-Setup-0.3.0-x64.exe"
        Copy-Item -LiteralPath $setup -Destination $savedSetup -Force
        Write-Host "Build complete: $savedSetup"
        return
    }
    $args = @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/DIR=$InstallRoot")
    $proc = Start-Process -FilePath $setup -ArgumentList $args -Wait -PassThru
    if ($proc.ExitCode -ne 0) { throw "Peke Setup exited with code $($proc.ExitCode)." }
    $installedExe = Join-Path $InstallRoot "Peke.exe"
    if (-not (Test-Path -LiteralPath $installedExe -PathType Leaf)) { throw "Installation completed but Peke.exe was not found at $installedExe." }
    Write-Host "Peke installed to $InstallRoot. Launching the desktop app..."
    Start-Process -FilePath $installedExe -WorkingDirectory $InstallRoot
} finally {
    Remove-Item -LiteralPath $WorkRoot -Recurse -Force -ErrorAction SilentlyContinue
}
