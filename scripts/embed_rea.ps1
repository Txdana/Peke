<#
Stages a private Node.js runtime and the pinned REA package (rea-agents) so Peke ships with REA built in.
Output layout:  <Destination>\node\node.exe   and   <Destination>\app\node_modules\rea-agents\scripts\rea.mjs
Nothing touches PATH or the registry. Requires network access at BUILD time only.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Destination,
    [string]$ReaVersion = '6.7.0',
    [string]$NodeMajor = '24',
    [string]$MinNode = '24.22.1'
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$work = Join-Path ([IO.Path]::GetTempPath()) ('peke-rea-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path $work -Force | Out-Null
try {
    $index = Invoke-RestMethod 'https://nodejs.org/dist/index.json'
    $pick = $index | Where-Object { $_.version -like "v$NodeMajor.*" -and $_.lts -and ([version]($_.version.TrimStart('v')) -ge [version]$MinNode) } | Select-Object -First 1
    if (-not $pick) { throw "No Node $NodeMajor LTS release >= $MinNode found on nodejs.org." }
    $ver = $pick.version
    $zipName = "node-$ver-win-x64.zip"
    $base = "https://nodejs.org/dist/$ver"
    Write-Host "Embedding Node $ver and rea-agents@$ReaVersion"

    $zip = Join-Path $work $zipName
    Invoke-WebRequest "$base/$zipName" -OutFile $zip
    $sums = (Invoke-WebRequest "$base/SHASUMS256.txt").Content
    $expected = ($sums -split "`n" | Where-Object { $_ -match [regex]::Escape($zipName) + '\s*$' } | Select-Object -First 1) -split '\s+' | Select-Object -First 1
    $actual = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant()
    if (-not $expected -or $actual -ne $expected.ToLowerInvariant()) { throw "Node download failed SHA-256 verification." }

    Expand-Archive $zip -DestinationPath $work -Force
    $nodeSrc = Join-Path $work "node-$ver-win-x64"

    if (Test-Path $Destination) { Remove-Item $Destination -Recurse -Force }
    $nodeDst = Join-Path $Destination 'node'
    New-Item -ItemType Directory -Path $nodeDst -Force | Out-Null
    Copy-Item (Join-Path $nodeSrc 'node.exe') $nodeDst
    Copy-Item (Join-Path $nodeSrc 'LICENSE') $nodeDst -ErrorAction SilentlyContinue

    $app = Join-Path $Destination 'app'
    New-Item -ItemType Directory -Path $app -Force | Out-Null
    Set-Content (Join-Path $app 'package.json') '{"name":"peke-rea-host","private":true}' -Encoding ascii
    $env:PATH = "$nodeSrc;$env:PATH"
    $npmCli = Join-Path $nodeSrc 'node_modules\npm\bin\npm-cli.js'
    & (Join-Path $nodeSrc 'node.exe') $npmCli install "rea-agents@$ReaVersion" --omit=dev --no-audit --no-fund --prefix $app
    if ($LASTEXITCODE -ne 0) { throw "npm install rea-agents@$ReaVersion failed (exit $LASTEXITCODE)." }

    $entry = Join-Path $app 'node_modules\rea-agents\scripts\rea.mjs'
    if (-not (Test-Path $entry)) { throw "rea.mjs missing after install: $entry" }
    $dist = Join-Path $app 'node_modules\rea-agents\dist\cli-runtime\cli.js'
    if (-not (Test-Path $dist)) { throw "REA compiled runtime missing: $dist" }
    & (Join-Path $nodeDst 'node.exe') $entry --version
    if ($LASTEXITCODE -ne 0) { throw "Embedded REA failed its smoke test (rea --version)." }
    Write-Host "REA embedded at $Destination"
}
finally {
    Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
}
