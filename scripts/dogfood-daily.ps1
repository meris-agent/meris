# Meris 日常 Dogfood 环境检查
# 用法: powershell -ExecutionPolicy Bypass -File scripts\dogfood-daily.ps1

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Push-Location $Root
try {
    Write-Host "`n== Meris dogfood daily check ==" -ForegroundColor Cyan
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
    Write-Host "Next: pick 1 real task today (see docs/DOGFOOD_DAILY.md)`n" -ForegroundColor Cyan
    exit $code
} finally {
    Pop-Location
}
