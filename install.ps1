[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$NoLaunch,
    [switch]$NoBootstrap,
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'Programs\Peke')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Repo = 'https://github.com/Txdana/Peke.git'
# Pin to the reviewed source commit. Never replace this with "main" or a tag.
$PinnedCommit = '2428f7918a45450914efce05ae249b03c217bee1'
$AppName = 'Peke'
# Keep the build root short: PySide6 ships deeply nested Qt/QML files that can
# exceed legacy Windows path limits when built below the default TEMP directory.
$BuildBase = if (-not [string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
    $env:USERPROFILE
} else {
    [IO.Path]::GetTempPath()
}
$WorkRoot = Join-Path $BuildBase ('pbuild-' + [guid]::NewGuid().ToString('N').Substring(0, 8))

function Assert-ValidPin {
    if ($PinnedCommit -notmatch '^[0-9a-f]{40}$') {
        throw 'Installer source revision is invalid. PinnedCommit must be a full 40-character lowercase Git commit SHA.'
    }
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$File,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [string]$WorkingDirectory
    )

    $oldErrorActionPreference = $ErrorActionPreference
    $pushedLocation = $false
    $exitCode = -1
    try {
        if (-not [string]::IsNullOrWhiteSpace($WorkingDirectory)) {
            if (-not (Test-Path -LiteralPath $WorkingDirectory -PathType Container)) {
                throw "Working directory does not exist: $WorkingDirectory"
            }
            Push-Location -LiteralPath $WorkingDirectory
            $pushedLocation = $true
        }

        # Windows PowerShell 5.1 may surface native stderr as PowerShell errors.
        # Continue long enough to capture the process exit code, then fail clearly.
        $ErrorActionPreference = 'Continue'
        & $File @Arguments
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $oldErrorActionPreference
        if ($pushedLocation) {
            Pop-Location
        }
    }

    if ($exitCode -ne 0) {
        throw "Command failed with exit code ${exitCode}: '$File $($Arguments -join ' ')'"
    }
}

function Find-ToolPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [string[]]$Candidates = @()
    )

    $command = Get-Command -Name $Name -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($command -and $command.Source -and (Test-Path -LiteralPath $command.Source -PathType Leaf)) {
        return (Resolve-Path -LiteralPath $command.Source).Path
    }

    foreach ($candidate in $Candidates) {
        if (-not [string]::IsNullOrWhiteSpace($candidate) -and
            (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    return $null
}

function Test-PythonExecutable {
    param([Parameter(Mandatory = $true)][string]$Candidate)

    if (-not (Test-Path -LiteralPath $Candidate -PathType Leaf)) {
        return $false
    }

    $oldErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $versionOutput = & $Candidate --version 2>&1
        $versionExitCode = $LASTEXITCODE
        $versionText = (@($versionOutput) -join "`n").Trim()
        if ($versionExitCode -ne 0 -or $versionText -notmatch '^Python 3\.(11|12)\.') {
            return $false
        }

        $architectureOutput = & $Candidate -c "import struct; print(struct.calcsize('P') * 8)" 2>&1
        $architectureExitCode = $LASTEXITCODE
        $architectureText = (@($architectureOutput) -join "`n").Trim()
        if ($architectureExitCode -ne 0 -or $architectureText -ne '64') {
            return $false
        }

        return $true
    }
    catch {
        return $false
    }
    finally {
        $ErrorActionPreference = $oldErrorActionPreference
    }
}

function Find-PythonExecutable {
    $candidates = @()
    $localAppData = $env:LOCALAPPDATA
    $programFiles = $env:ProgramFiles
    $programFilesX86 = ${env:ProgramFiles(x86)}

    foreach ($version in @('Python311', 'Python312')) {
        if ($localAppData) {
            $candidates += (Join-Path $localAppData "Programs\Python\$version\python.exe")
        }
        if ($programFiles) {
            $candidates += (Join-Path $programFiles "$version\python.exe")
        }
        if ($programFilesX86) {
            $candidates += (Join-Path $programFilesX86 "$version\python.exe")
        }
    }

    # Use the Python launcher when installed, even if PATH has not refreshed.
    $launcher = Get-Command -Name 'py.exe' -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($launcher -and $launcher.Source) {
        foreach ($version in @('3.12', '3.11')) {
            $oldErrorActionPreference = $ErrorActionPreference
            try {
                $ErrorActionPreference = 'Continue'
                $launcherOutput = & $launcher.Source "-$version" '-c' 'import sys; print(sys.executable)' 2>$null
                $launcherExitCode = $LASTEXITCODE
                $launcherPath = (@($launcherOutput) -join '').Trim()
                if ($launcherExitCode -eq 0 -and $launcherPath) {
                    $candidates += $launcherPath
                }
            }
            finally {
                $ErrorActionPreference = $oldErrorActionPreference
            }
        }
    }

    $pythonCommand = Get-Command -Name 'python.exe' -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($pythonCommand -and $pythonCommand.Source -and
        $pythonCommand.Source -notmatch '\\Microsoft\\WindowsApps\\python\.exe$') {
        $candidates += $pythonCommand.Source
    }

    foreach ($candidate in ($candidates | Where-Object { $_ } | Select-Object -Unique)) {
        if (Test-PythonExecutable -Candidate $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    return $null
}

function Find-InnoCompiler {
    $command = Get-Command -Name 'ISCC.exe' -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($command -and $command.Source -and (Test-Path -LiteralPath $command.Source -PathType Leaf)) {
        return (Resolve-Path -LiteralPath $command.Source).Path
    }

    $programFiles = $env:ProgramFiles
    $programFilesX86 = ${env:ProgramFiles(x86)}
    $localAppData = $env:LOCALAPPDATA
    $candidates = @()

    foreach ($base in @($programFilesX86, $programFiles)) {
        if ($base) {
            $candidates += (Join-Path $base 'Inno Setup 6\ISCC.exe')
        }
    }
    if ($localAppData) {
        $candidates += (Join-Path $localAppData 'Programs\Inno Setup 6\ISCC.exe')
        $candidates += (Join-Path $localAppData 'Programs (x86)\Inno Setup 6\ISCC.exe')
    }

    # Registry uninstall entries have inconsistent property sets. Inspect
    # PSObject.Properties before reading them under StrictMode.
    $registryKeys = @(
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKCU:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )

    foreach ($key in $registryKeys) {
        $entries = Get-ItemProperty -Path $key -ErrorAction SilentlyContinue
        foreach ($entry in $entries) {
            $displayNameProperty = $entry.PSObject.Properties['DisplayName']
            $displayName = if ($displayNameProperty) { [string]$displayNameProperty.Value } else { '' }
            if ($displayName -notlike 'Inno Setup 6*') {
                continue
            }

            $installLocationProperty = $entry.PSObject.Properties['InstallLocation']
            $installLocation = if ($installLocationProperty) { [string]$installLocationProperty.Value } else { '' }
            if (-not [string]::IsNullOrWhiteSpace($installLocation)) {
                $installLocation = $installLocation.Trim('"')
                $candidates += (Join-Path $installLocation 'ISCC.exe')
            }

            $displayIconProperty = $entry.PSObject.Properties['DisplayIcon']
            $displayIcon = if ($displayIconProperty) { [string]$displayIconProperty.Value } else { '' }
            if (-not [string]::IsNullOrWhiteSpace($displayIcon)) {
                $iconPath = ($displayIcon -replace ',\s*-?\d+\s*$', '').Trim('"')
                if ((Split-Path -Leaf $iconPath) -ieq 'ISCC.exe') {
                    $candidates += $iconPath
                }
                elseif ($iconPath -and (Test-Path -LiteralPath $iconPath -PathType Leaf)) {
                    $candidates += (Join-Path (Split-Path -Parent $iconPath) 'ISCC.exe')
                }
            }
        }
    }

    foreach ($candidate in ($candidates | Where-Object { $_ } | Select-Object -Unique)) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    # WinGet can use per-user locations not represented in the standard paths.
    if ($localAppData) {
        $wingetPackages = Join-Path $localAppData 'Microsoft\WinGet\Packages'
        if (Test-Path -LiteralPath $wingetPackages -PathType Container) {
            $match = Get-ChildItem -LiteralPath $wingetPackages -Filter 'ISCC.exe' -File -Recurse -ErrorAction SilentlyContinue |
                Select-Object -First 1
            if ($match) {
                return $match.FullName
            }
        }
    }

    return $null
}

function Install-WingetPackage {
    param([Parameter(Mandatory = $true)][string]$Id)

    $winget = Get-Command -Name 'winget.exe' -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $winget -or -not $winget.Source) {
        throw "winget is unavailable. Install Microsoft App Installer or install '$Id' manually, then retry."
    }

    Write-Host "Installing prerequisite '$Id' with winget..."
    Invoke-Checked -File $winget.Source -Arguments @(
        'install', '--id', $Id, '--exact', '--silent',
        '--accept-package-agreements', '--accept-source-agreements'
    )
}

function Assert-RequiredSourceFiles {
    param([Parameter(Mandatory = $true)][string]$Root)

    $requiredFiles = @(
        'pyproject.toml',
        'README.md',
        'LICENSE',
        'NOTICE',
        'THIRD_PARTY_NOTICES.md',
        'packaging\windows\Peke.spec',
        'packaging\windows\Peke.iss',
        'src\peke\desktop\launcher.py',
        'src\peke\gui\assets\peke.ico'
    )

    foreach ($relativePath in $requiredFiles) {
        $fullPath = Join-Path $Root $relativePath
        if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
            throw "The pinned source is missing required build file '$relativePath'. Refusing to continue."
        }
    }
}

if ($env:OS -ne 'Windows_NT') {
    throw 'This installer can only build and install Peke on Windows.'
}
if (-not [Environment]::Is64BitOperatingSystem) {
    throw 'Peke desktop packaging currently requires 64-bit Windows.'
}
if ([string]::IsNullOrWhiteSpace($InstallRoot)) {
    throw 'InstallRoot cannot be empty.'
}
try {
    $InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
}
catch {
    throw "InstallRoot is not a valid path: $InstallRoot"
}

Assert-ValidPin

Write-Host "$AppName source-build installer"
Write-Host "Pinned source revision: $PinnedCommit"
Write-Host 'No installer binary is hosted in the repository; the setup EXE is compiled locally from pinned source, and model weights are not downloaded.'

if ($DryRun) {
    Write-Host "DRY RUN: would ensure Git, Python 3.11/3.12 x64, and Inno Setup 6 are available (using winget when needed), fetch and verify $PinnedCommit, build the windowed GUI, compile a local setup EXE, and install it to '$InstallRoot'."
    return
}

$gitCandidates = @()
foreach ($base in @($env:ProgramFiles, ${env:ProgramFiles(x86)})) {
    if ($base) {
        $gitCandidates += (Join-Path $base 'Git\cmd\git.exe')
        $gitCandidates += (Join-Path $base 'Git\bin\git.exe')
    }
}
if ($env:LOCALAPPDATA) {
    $gitCandidates += (Join-Path $env:LOCALAPPDATA 'Programs\Git\cmd\git.exe')
    $gitCandidates += (Join-Path $env:LOCALAPPDATA 'Programs\Git\bin\git.exe')
}

$git = Find-ToolPath -Name 'git.exe' -Candidates $gitCandidates
$python = Find-PythonExecutable
$iscc = Find-InnoCompiler

if (-not $NoBootstrap) {
    if (-not $git) {
        Install-WingetPackage -Id 'Git.Git'
    }
    if (-not $python) {
        Install-WingetPackage -Id 'Python.Python.3.11'
    }
    if (-not $iscc) {
        Install-WingetPackage -Id 'JRSoftware.InnoSetup'
    }

    # Re-discover tools after WinGet; its installers may not refresh PATH.
    $git = Find-ToolPath -Name 'git.exe' -Candidates $gitCandidates
    $python = Find-PythonExecutable
    $iscc = Find-InnoCompiler
}

if (-not $git) {
    throw 'Git for Windows was not found after prerequisite setup. Install Git and retry.'
}
if (-not $python) {
    throw 'Python 3.11 or 3.12 x64 was not found after prerequisite setup. Install a supported 64-bit Python and retry.'
}
if (-not $iscc) {
    throw 'Inno Setup 6 compiler (ISCC.exe) was not found after prerequisite setup. Install Inno Setup 6 and retry.'
}

$gitVersion = & $git --version 2>&1
if ($LASTEXITCODE -ne 0 -or (@($gitVersion) -join ' ') -notmatch '^git version ') {
    throw "Git was found but failed its version check: $git"
}
Write-Host "Using Git: $((@($gitVersion) -join ' ').Trim())"
Write-Host "Using Python: $python"
Write-Host "Using Inno Setup compiler: $iscc"

$oldTemp = $env:TEMP
$oldTmp = $env:TMP
New-Item -ItemType Directory -Path $WorkRoot -Force | Out-Null
try {
    # Keep pip, wheel extraction, and Qt build temporaries on the same short path.
    $shortTemp = Join-Path $WorkRoot 'tmp'
    New-Item -ItemType Directory -Path $shortTemp -Force | Out-Null
    $env:TEMP = $shortTemp
    $env:TMP = $shortTemp

    $source = Join-Path $WorkRoot 'src'

    # Each argument is passed as a separate native argument. Use named
    # parameters to avoid PowerShell parsing array expressions as splatting.
    Invoke-Checked -File $git -Arguments @('init', $source)
    Invoke-Checked -File $git -Arguments @('-C', $source, 'remote', 'add', 'origin', $Repo)
    Invoke-Checked -File $git -Arguments @('-C', $source, 'fetch', '--depth', '1', 'origin', $PinnedCommit)
    Invoke-Checked -File $git -Arguments @('-C', $source, 'checkout', '--detach', 'FETCH_HEAD')

    $oldErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $actualOutput = & $git -C $source 'rev-parse' 'HEAD' 2>&1
        $actualExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $oldErrorActionPreference
    }
    $actualCommit = (@($actualOutput) -join '').Trim().ToLowerInvariant()
    if ($actualExitCode -ne 0 -or $actualCommit -ne $PinnedCommit) {
        throw "Source revision verification failed. Expected '$PinnedCommit'; got '$actualCommit'. Refusing to build."
    }
    Write-Host "Verified source revision: $actualCommit"

    Assert-RequiredSourceFiles -Root $source

    # Keep the setup version aligned with the pinned package's own metadata.
    $pyprojectText = Get-Content -LiteralPath (Join-Path $source 'pyproject.toml') -Raw
    $versionMatch = [regex]::Match($pyprojectText, '(?m)^\s*version\s*=\s*"([^"]+)"')
    if (-not $versionMatch.Success) {
        throw 'Could not read the project version from pyproject.toml.'
    }
    $AppVersion = $versionMatch.Groups[1].Value
    if ($AppVersion -notmatch '^\d+\.\d+\.\d+(?:[.-][0-9A-Za-z.-]+)?$') {
        throw "Unsupported project version '$AppVersion' for the Windows installer."
    }
    Write-Host "Building Peke version $AppVersion"

    $venv = Join-Path $source '.venv-build'
    Invoke-Checked -File $python -Arguments @('-m', 'venv', $venv) -WorkingDirectory $source

    $buildPython = Join-Path $venv 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $buildPython -PathType Leaf)) {
        throw "Python virtual environment was not created at '$buildPython'."
    }

    Invoke-Checked -File $buildPython -Arguments @(
        '-m', 'pip', 'install', '--disable-pip-version-check', '--upgrade', 'pip'
    ) -WorkingDirectory $source

    Invoke-Checked -File $buildPython -Arguments @(
        '-m', 'pip', 'install', '.[gui]', 'pyinstaller==6.16.0'
    ) -WorkingDirectory $source

    Invoke-Checked -File $buildPython -Arguments @(
        '-m', 'pip', 'check'
    ) -WorkingDirectory $source

    # The PyInstaller spec resolves input paths relative to the repository root.
    Invoke-Checked -File $buildPython -Arguments @(
        '-m', 'PyInstaller', 'packaging/windows/Peke.spec', '--clean', '--noconfirm'
    ) -WorkingDirectory $source

    $exe = Join-Path $source 'dist\Peke\Peke.exe'
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
        throw "PyInstaller did not produce '$exe'. Review the first build error above."
    }

    # Ensure the compiler output directory exists on a clean checkout.
    $installerOutputDirectory = Join-Path $source 'dist-installer'
    New-Item -ItemType Directory -Path $installerOutputDirectory -Force | Out-Null

    $issPath = Join-Path $source 'packaging\windows\Peke.iss'
    Invoke-Checked -File $iscc -Arguments @(
        "/DAppVersion=$AppVersion", $issPath
    ) -WorkingDirectory $source

    $setup = Join-Path $source "dist-installer\Peke-Setup-$AppVersion-x64.exe"
    if (-not (Test-Path -LiteralPath $setup -PathType Leaf)) {
        throw "Inno Setup did not produce '$setup'."
    }
    $setupInfo = Get-Item -LiteralPath $setup
    if ($setupInfo.Length -lt 1000000) {
        throw "Generated setup executable is unexpectedly small ($($setupInfo.Length) bytes). Refusing to continue."
    }

    if ($NoLaunch) {
        $savedSetup = Join-Path (Get-Location).Path "Peke-Setup-$AppVersion-x64.exe"
        Copy-Item -LiteralPath $setup -Destination $savedSetup -Force
        Write-Host "Build complete. Setup executable saved to: $savedSetup"
        return
    }

    # Inno Setup expects /DIR="path" when the install path contains spaces.
    $installDirArgument = '/DIR="' + $InstallRoot + '"'
    $installArguments = @(
        '/VERYSILENT',
        '/SUPPRESSMSGBOXES',
        '/NORESTART',
        $installDirArgument
    )

    $installerProcess = Start-Process -FilePath $setup -ArgumentList $installArguments -Wait -PassThru
    if ($installerProcess.ExitCode -ne 0) {
        throw "Peke Setup exited with code $($installerProcess.ExitCode)."
    }

    $installedExe = Join-Path $InstallRoot 'Peke.exe'
    if (-not (Test-Path -LiteralPath $installedExe -PathType Leaf)) {
        throw "Setup returned success, but Peke.exe was not found at '$installedExe'."
    }

    Write-Host "Peke installed to '$InstallRoot'. Launching the desktop app..."
    Start-Process -FilePath $installedExe -WorkingDirectory $InstallRoot
}
finally {
    if ($null -eq $oldTemp) {
        Remove-Item Env:TEMP -ErrorAction SilentlyContinue
    } else {
        $env:TEMP = $oldTemp
    }
    if ($null -eq $oldTmp) {
        Remove-Item Env:TMP -ErrorAction SilentlyContinue
    } else {
        $env:TMP = $oldTmp
    }
    Remove-Item -LiteralPath $WorkRoot -Recurse -Force -ErrorAction SilentlyContinue
}
