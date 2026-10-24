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
# of the reviewed source revision before publishing.
$Repo = "https://github.com/Txdana/Peke.git"
$PinnedCommit = "8575e2fc6b4d8aa9e1647e5d523373170012aeae"
$AppName = "Peke"
$AppVersion = "0.5.0"
$WorkRoot = Join-Path ([IO.Path]::GetTempPath()) ("peke-source-build-" + [guid]::NewGuid().ToString("N"))

function Assert-ValidPin {
    if ($PinnedCommit -notmatch '^[0-9a-f]{40}$') {
        throw "Installer source revision is not release-pinned. Set PinnedCommit to a full 40-character Git commit SHA."
    }
}

function Invoke-Checked([string]$File, [string[]]$Args) {
    & $File @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: '$File $($Args -join ' ')'; exit code $LASTEXITCODE."
    }
}

Write-Host "Peke source-build installer"
Write-Host "Pinned revision: $PinnedCommit"
Write-Host "Builds Peke and its setup EXE locally; no installer binary is hosted in the repository and no model is downloaded."

if ($DryRun) {
    if ($PinnedCommit -notmatch '^[0-9a-f]{40}$') {
        Write-Warning "PinnedCommit is not configured yet; a real install will refuse to run until a reviewed source SHA is committed."
    }

    Write-Host "DRY RUN: would ensure Git, Python 3.11 x64, and Inno Setup 6 are available (using winget when needed), fetch and verify $PinnedCommit, build Peke.exe, compile a local setup EXE, install it to $InstallRoot, and launch Peke."
    return
}

Assert-ValidPin

function Find-ToolPath([string]$Name, [string[]]$Candidates = @()) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    foreach ($candidate in $Candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return $candidate
        }
    }

    return $null
}

function Find-InnoCompiler {
    # Check PATH first.
    $command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($command -and $command.Source -and (Test-Path -LiteralPath $command.Source -PathType Leaf)) {
        return $command.Source
    }

    # Check common machine-wide and per-user installation locations.
    $programFiles = [Environment]::GetFolderPath([Environment+SpecialFolder]::ProgramFiles)
    $programFilesX86 = ${env:ProgramFiles(x86)}
    $localAppData = $env:LOCALAPPDATA
    $candidates = @()

    foreach ($base in @($programFilesX86, $programFiles)) {
        if ($base) {
            $candidates += (Join-Path $base "Inno Setup 6\ISCC.exe")
        }
    }

    if ($localAppData) {
        $candidates += (Join-Path $localAppData "Programs\Inno Setup 6\ISCC.exe")
        $candidates += (Join-Path $localAppData "Programs (x86)\Inno Setup 6\ISCC.exe")
    }

    # Search uninstall registry entries safely.
    # Not every registry entry has the same properties.
    $registryKeys = @(
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*"
    )

    foreach ($key in $registryKeys) {
        $entries = Get-ItemProperty -Path $key -ErrorAction SilentlyContinue

        foreach ($entry in $entries) {
            $displayNameProperty = $entry.PSObject.Properties['DisplayName']
            $displayName = if ($displayNameProperty) {
                [string]$displayNameProperty.Value
            } else {
                ''
            }

            if ($displayName -like "Inno Setup 6*") {
                $installLocationProperty = $entry.PSObject.Properties['InstallLocation']
                $installLocation = if ($installLocationProperty) {
                    [string]$installLocationProperty.Value
                } else {
                    ''
                }

                if (-not [string]::IsNullOrWhiteSpace($installLocation)) {
                    $candidates += (Join-Path $installLocation "ISCC.exe")
                }

                $displayIconProperty = $entry.PSObject.Properties['DisplayIcon']
                $displayIcon = if ($displayIconProperty) {
                    [string]$displayIconProperty.Value
                } else {
                    ''
                }

                if (-not [string]::IsNullOrWhiteSpace($displayIcon)) {
                    $iconPath = ($displayIcon -replace ',\s*-?\d+\s*$', '').Trim('"')

                    if ((Split-Path -Leaf $iconPath) -ieq "ISCC.exe") {
                        $candidates += $iconPath
                    } elseif ($iconPath -and (Test-Path -LiteralPath $iconPath -PathType Leaf)) {
                        $candidates += (Join-Path (Split-Path -Parent $iconPath) "ISCC.exe")
                    }
                }
            }
        }
    }

    foreach ($candidate in ($candidates | Where-Object { $_ } | Select-Object -Unique)) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    return $null
}

function Install-WingetPackage([string]$Id) {
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue

    if (-not $winget) {
        throw "winget is unavailable. Install App Installer from Microsoft Store, then rerun this command."
    }

    Write-Host "Installing build prerequisite $Id with winget..."

    & $winget.Source install --id $Id --exact --silent --accept-package-agreements --accept-source-agreements

    if ($LASTEXITCODE -ne 0) {
        throw "winget could not install $Id (exit code $LASTEXITCODE). Install it manually and retry."
    }
}

# Find the required build tools.
$git = Find-ToolPath "git.exe" @(
    (Join-Path $env:ProgramFiles "Git\cmd\git.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Git\cmd\git.exe")
)

$python = Find-ToolPath "python.exe" @(
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"),
    (Join-Path $env:ProgramFiles "Python311\python.exe")
)

$iscc = Find-InnoCompiler

# Install missing prerequisites when bootstrap is enabled.
if (-not $NoBootstrap) {
    if (-not $git) {
        Install-WingetPackage "Git.Git"
    }

    if (-not $python) {
        Install-WingetPackage "Python.Python.3.11"
    }

    if (-not $iscc) {
        Install-WingetPackage "JRSoftware.InnoSetup"
    }

    # Recheck after installation because this PowerShell session's PATH
    # might not have been refreshed by winget.
    $git = Find-ToolPath "git.exe" @(
        (Join-Path $env:ProgramFiles "Git\cmd\git.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Git\cmd\git.exe")
    )

    $python = Find-ToolPath "python.exe" @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"),
        (Join-Path $env:ProgramFiles "Python311\python.exe")
    )

    $iscc = Find-InnoCompiler
}

if (-not $git) {
    throw "Git for Windows was not found after prerequisite setup. Install Git and retry."
}

if (-not $python) {
    throw "Python 3.11 x64 was not found after prerequisite setup. Install Python 3.11 x64 and retry."
}

if (-not $iscc) {
    throw "Inno Setup was installed or requested, but ISCC.exe could not be located. Check the Inno Setup install folder, or rerun with -NoBootstrap after installing Inno Setup 6 manually."
}

Write-Host "Using Inno Setup compiler: $iscc"

# Verify the Python version and architecture.
$pythonVersion = & $python --version 2>&1

if ($pythonVersion -notmatch '^Python 3\.(11|12)\.') {
    throw "Python 3.11 or 3.12 x64 is required; found '$pythonVersion'. Install a supported 64-bit Python and retry."
}

$pythonArch = & $python -c "import struct; print(struct.calcsize('P') * 8)" 2>&1

if ($LASTEXITCODE -ne 0 -or "$pythonArch".Trim() -ne "64") {
    throw "A 64-bit Python installation is required; detected architecture: '$pythonArch'."
}

New-Item -ItemType Directory -Path $WorkRoot | Out-Null

try {
    $source = Join-Path $WorkRoot "source"

    # Fetch only the pinned revision, then verify the checked-out commit.
    Invoke-Checked $git @("init", $source)
    Invoke-Checked $git @("-C", $source, "remote", "add", "origin", $Repo)
    Invoke-Checked $git @("-C", $source, "fetch", "--depth", "1", "origin", $PinnedCommit)
    Invoke-Checked $git @("-C", $source, "checkout", "--detach", "FETCH_HEAD")

    $actual = (& $git -C $source rev-parse HEAD).Trim().ToLowerInvariant()

    if ($LASTEXITCODE -ne 0 -or $actual -ne $PinnedCommit) {
        throw "Source revision verification failed. Expected $PinnedCommit; got $actual. Refusing to build."
    }

    # Create an isolated Python environment for the build.
    $venv = Join-Path $source ".venv-build"
    Invoke-Checked $python @("-m", "venv", $venv)

    $python = Join-Path $venv "Scripts\python.exe"

    Invoke-Checked $python @(
        "-m", "pip", "install",
        "--disable-pip-version-check",
        "--upgrade", "pip"
    )

    Invoke-Checked $python @(
        "-m", "pip", "install",
        ".[gui]",
        "pyinstaller==6.16.0"
    )

    # Build the desktop application in windowed mode as defined by the spec.
    Invoke-Checked $python @(
        "-m", "PyInstaller",
        "packaging/windows/Peke.spec",
        "--clean",
        "--noconfirm"
    )

    $exe = Join-Path $source "dist\Peke\Peke.exe"

    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
        throw "PyInstaller did not produce dist\Peke\Peke.exe."
    }

    # Compile the Windows installer locally.
    Invoke-Checked $iscc @(
        "/DAppVersion=$AppVersion",
        (Join-Path $source "packaging\windows\Peke.iss")
    )

    $setup = Join-Path $source "dist-installer\Peke-Setup-$AppVersion-x64.exe"

    if (-not (Test-Path -LiteralPath $setup -PathType Leaf)) {
        throw "Inno Setup did not produce the expected setup executable."
    }

    # Optionally save the setup executable without installing or launching.
    if ($NoLaunch) {
        $savedSetup = Join-Path (Get-Location).Path "Peke-Setup-$AppVersion-x64.exe"
        Copy-Item -LiteralPath $setup -Destination $savedSetup -Force
        Write-Host "Build complete: $savedSetup"
        return
    }

    # Run the generated installer silently.
    $installArgs = @(
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/DIR=$InstallRoot"
    )

    $proc = Start-Process -FilePath $setup -ArgumentList $installArgs -Wait -PassThru

    if ($proc.ExitCode -ne 0) {
        throw "Peke Setup exited with code $($proc.ExitCode)."
    }

    $installedExe = Join-Path $InstallRoot "Peke.exe"

    if (-not (Test-Path -LiteralPath $installedExe -PathType Leaf)) {
        throw "Installation completed but Peke.exe was not found at $installedExe."
    }

    Write-Host "Peke installed to $InstallRoot. Launching the desktop app..."
    Start-Process -FilePath $installedExe -WorkingDirectory $InstallRoot
}
finally {
    # Remove temporary source and build files.
    Remove-Item -LiteralPath $WorkRoot -Recurse -Force -ErrorAction SilentlyContinue
}
