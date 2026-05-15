$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

python -m PyInstaller `
  --noconfirm `
  --clean `
  .\packaging\windows\VBarrido.spec

if ($LASTEXITCODE -ne 0) {
  throw "PyInstaller finalizó con código $LASTEXITCODE"
}

Write-Host ""
Write-Host "Build completado:"
Write-Host "  $projectRoot\dist\VBarrido.exe"
