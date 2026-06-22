# Meris 日常环境就绪检查
# 用法: powershell -ExecutionPolicy Bypass -File scripts\dogfood-daily.ps1

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Push-Location $Root
try {
    Write-Host "`n== Meris readiness check ==" -ForegroundColor Cyan
    Write-Host "cwd: $Root`n"

    if (-not (Get-Command meris -ErrorAction SilentlyContinue)) {
        Write-Host "[xx] meris CLI not on PATH — pip install -e ." -ForegroundColor Red
        exit 1
    }

    $env:PYTHONPATH = $Root
    meris dogfood
    $code = $LASTEXITCODE

    Write-Host ""
    if ($code -eq 0) {
        Write-Host "Optional: meris doctor --no-probe" -ForegroundColor DarkGray
    }
    Write-Host "Next: pick 1 real task today (see docs/README.md)`n" -ForegroundColor Cyan
    exit $code
} finally {
    Pop-Location
}
