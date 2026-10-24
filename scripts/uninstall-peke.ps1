<#
.SYNOPSIS  Completely removes the Peke app and everything it created for the current Windows user.
.NOTES     Does NOT delete your own git clone / source folder. Use -Yes to skip the confirmation.
           Edited third-party config files are backed up to %TEMP%\peke-removal-backup first.
#>
[CmdletBinding()]
param([switch]$Yes, [switch]$KeepModels)
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'

$home_ = $env:USERPROFILE
$install = Join-Path $env:LOCALAPPDATA 'Programs\Peke'
$appId = '{F3B87F4B-5D6A-4A42-9F0C-3E7E1B2C8A10}_is1'
$backup = Join-Path $env:TEMP 'peke-removal-backup'

$dirs = @(
    $install,
    (Join-Path $env:LOCALAPPDATA 'Peke'),                 # config, logs, icons, bundled SearXNG state
    (Join-Path $env:APPDATA 'Peke'),
    (Join-Path $home_ '.claude\skills\peke'),
    (Join-Path $home_ '.local\pipx\venvs\peke'),
    (Join-Path $home_ 'pipx\venvs\peke')
)
if (-not $KeepModels) { $dirs += (Join-Path $home_ '.peke') }
if ($env:PEKE_HOME) { $dirs += $env:PEKE_HOME }
$dirs += (Get-ChildItem $home_ -Directory -Filter 'pbuild-*' -ErrorAction SilentlyContinue | ForEach-Object FullName)
$dirs += (Get-ChildItem $env:TEMP -Directory -Filter 'peke-*' -ErrorAction SilentlyContinue |
          Where-Object { $_.Name -ne 'peke-removal-backup' } | ForEach-Object FullName)
$files = @(
    (Join-Path $home_ '.local\bin\peke.exe'),
    (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Peke.lnk'),
    (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Peke.lnk'),
    (Join-Path ([Environment]::GetFolderPath('CommonDesktopDirectory')) 'Peke.lnk')
)
$dirs += (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Peke')

Write-Host "`nThis will permanently delete Peke and all its data for user $env:USERNAME:" -ForegroundColor Yellow
($dirs + $files) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object { Write-Host "  $_" }
Write-Host "  + registry keys (HKCU\Software\Peke, uninstall entry), Credential Manager entries (PekeWorkbench),"
Write-Host "  + 'peke' entries in Claude / Cursor / Gemini / VS Code / Windsurf / Codex MCP configs"
if (-not $Yes) {
    if ((Read-Host "`nType DELETE to continue") -ne 'DELETE') { Write-Host 'Cancelled.'; return }
}

# 1. Stop everything Peke started (GUI, bundled SearXNG, MCP server, embedded REA/node)
$roots = @($install) + (Get-ChildItem $home_ -Directory -Filter 'pbuild-*' -ErrorAction SilentlyContinue | ForEach-Object FullName)
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $cmd = "$($_.ExecutablePath) $($_.CommandLine)"
    ($roots | Where-Object { $cmd -like "*$_*" }) -or $cmd -match 'searx\.webapp' -or $cmd -match '\\Peke\\.*peke\.exe' -or $_.Name -ieq 'Peke.exe'
} | Where-Object { $_.ProcessId -ne $PID } | ForEach-Object {
    Write-Host "Stopping $($_.Name) ($($_.ProcessId))"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Milliseconds 800

# 2. Official uninstaller, then force-remove whatever is left
$unins = Join-Path $install 'unins000.exe'
if (Test-Path -LiteralPath $unins) {
    Start-Process $unins -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART' -Wait
}
if (Get-Command pipx -ErrorAction SilentlyContinue) { & pipx uninstall peke 2>$null | Out-Null }
if (Get-Command python -ErrorAction SilentlyContinue) { & python -m pip uninstall -y peke 2>$null | Out-Null }

# 3. Third-party MCP configs: remove only the "peke" entry (backup first)
New-Item -ItemType Directory -Path $backup -Force | Out-Null
$json = @(
    (Join-Path $home_ '.claude.json'),
    (Join-Path $env:APPDATA 'Claude\claude_desktop_config.json'),
    (Join-Path $home_ '.cursor\mcp.json'),
    (Join-Path $home_ '.gemini\settings.json'),
    (Join-Path $home_ '.vscode\mcp.json'),
    (Join-Path $home_ '.codeium\windsurf\mcp_config.json')
)
foreach ($f in $json) {
    if (-not (Test-Path -LiteralPath $f)) { continue }
    try {
        $raw = Get-Content -LiteralPath $f -Raw -Encoding UTF8
        $obj = $raw | ConvertFrom-Json
        $changed = $false
        foreach ($key in 'mcpServers', 'servers') {
            if ($obj.PSObject.Properties[$key] -and $obj.$key.PSObject.Properties['peke']) {
                $obj.$key.PSObject.Properties.Remove('peke'); $changed = $true
            }
        }
        if ($changed) {
            Copy-Item -LiteralPath $f -Destination (Join-Path $backup (($f -replace '[:\\]', '_') + '.bak')) -Force
            [IO.File]::WriteAllText($f, ($obj | ConvertTo-Json -Depth 100), (New-Object Text.UTF8Encoding $false))
            Write-Host "Removed Peke from $f"
        }
    } catch { Write-Warning "Could not edit $f : $($_.Exception.Message)" }
}
$codex = Join-Path $home_ '.codex\config.toml'
if (Test-Path -LiteralPath $codex) {
    $t = Get-Content -LiteralPath $codex -Raw -Encoding UTF8
    $n = [regex]::Replace($t, '(?ms)^\[mcp_servers\.peke(\.[^\]]+)?\]\r?\n.*?(?=^\[|\z)', '')
    if ($n -ne $t) {
        Copy-Item -LiteralPath $codex -Destination (Join-Path $backup 'codex-config.toml.bak') -Force
        [IO.File]::WriteAllText($codex, $n, (New-Object Text.UTF8Encoding $false)); Write-Host "Removed Peke from $codex"
    }
}

# 4. Files and folders
foreach ($d in ($dirs | Select-Object -Unique)) {
    if (Test-Path -LiteralPath $d) {
        Remove-Item -LiteralPath $d -Recurse -Force -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $d) { Write-Warning "Could not fully delete $d (in use? reboot and re-run)." } else { Write-Host "Deleted $d" }
    }
}
foreach ($f in $files) { if (Test-Path -LiteralPath $f) { Remove-Item -LiteralPath $f -Force -ErrorAction SilentlyContinue; Write-Host "Deleted $f" } }

# 5. Registry (Qt settings, Inno uninstall entry) and saved API keys
foreach ($k in "HKCU:\Software\Peke", "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$appId") {
    if (Test-Path $k) { Remove-Item $k -Recurse -Force; Write-Host "Deleted registry key $k" }
}
cmdkey /list 2>$null | Select-String -Pattern 'Target:\s*(.*PekeWorkbench.*)' | ForEach-Object {
    $target = $_.Matches[0].Groups[1].Value.Trim()
    cmdkey /delete:$target | Out-Null; Write-Host "Deleted saved credential $target"
}

# 6. Verify
$left = @($install, "$env:LOCALAPPDATA\Peke", "$home_\.local\bin\peke.exe") | Where-Object { Test-Path -LiteralPath $_ }
if ($left) { Write-Warning "Still present: $($left -join ', ')" } else { Write-Host "`nPeke has been completely removed." -ForegroundColor Green }
Write-Host "Config backups (if any): $backup  - delete that folder too if you want zero traces."
