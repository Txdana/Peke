[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$SourceDir,
    [switch]$Clean
)
$ErrorActionPreference = 'Stop'
$source = (Resolve-Path -LiteralPath $SourceDir).Path
if (-not (Test-Path (Join-Path $source 'CMakeLists.txt'))) {
    throw "SourceDir must point to the extracted llama.cpp source root (CMakeLists.txt not found)."
}
if (-not (Get-Command cmake -ErrorAction SilentlyContinue)) {
    throw 'CMake is required for this explicit developer build. Normal Peke installation does not compile llama.cpp.'
}
$build = Join-Path $source 'build-peke-cpu'
if ($Clean -and (Test-Path $build)) { Remove-Item -LiteralPath $build -Recurse -Force }
cmake -S $source -B $build -DGGML_NATIVE=OFF -DGGML_CUDA=OFF -DGGML_VULKAN=OFF -DLLAMA_BUILD_SERVER=ON -DCMAKE_BUILD_TYPE=Release
if ($LASTEXITCODE -ne 0) { throw "llama.cpp CMake configure failed ($LASTEXITCODE)." }
cmake --build $build --config Release --target llama-server --parallel
if ($LASTEXITCODE -ne 0) { throw "llama-server build failed ($LASTEXITCODE)." }
$candidates = @(
    (Join-Path $build 'bin/llama-server.exe'),
    (Join-Path $build 'bin/Release/llama-server.exe'),
    (Join-Path $build 'bin/llama-server')
)
$binary = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $binary) { throw 'Build finished but llama-server executable was not found in expected output paths.' }
$runtime = Join-Path $env:LOCALAPPDATA 'Peke/runtime'
New-Item -ItemType Directory -Path $runtime -Force | Out-Null
$destination = Join-Path $runtime ([IO.Path]::GetFileName($binary))
Copy-Item -LiteralPath $binary -Destination $destination -Force
& $destination --version
if ($LASTEXITCODE -ne 0) { throw 'Built llama-server failed its version check.' }
Write-Host "Installed CPU llama-server runtime to: $destination"
Write-Host 'Set LLAMA_SERVER_PATH to this path if automatic runtime discovery does not find it.'
