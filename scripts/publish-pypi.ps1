# Meris Agent — build & upload to PyPI / TestPyPI
# 用法:
#   powershell -ExecutionPolicy Bypass -File scripts\publish-pypi.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\publish-pypi.ps1 -TestPyPI
#   powershell -ExecutionPolicy Bypass -File scripts\publish-pypi.ps1 -SkipTests
#
# 凭证（不要写进仓库）:
#   $env:TWINE_USERNAME = "__token__"
#   $env:TWINE_PASSWORD = "pypi-..."
param(
    [switch]$TestPyPI,
    [switch]$SkipTests,
    [switch]$SkipUpload,
    [switch]$SkipClean
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

Push-Location $Root
try {
    Write-Step "Check tools"
    foreach ($cmd in @("python", "pip")) {
        if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
            throw "$cmd not found on PATH"
        }
    }

    python -m pip install -q --upgrade build twine
    $version = python -c "import meris; print(meris.__version__)"
    Write-Host "Package: meris-agent $version" -ForegroundColor Green

    if (-not $SkipTests) {
        Write-Step "Run tests"
        python -m pytest tests/ -m "not integration" -q
    }

    if (-not $SkipClean) {
        Write-Step "Clean dist/"
        if (Test-Path dist) { Remove-Item dist -Recurse -Force }
    }

    Write-Step "Build wheel + sdist"
    python -m build
    Get-ChildItem dist | ForEach-Object { Write-Host "  $($_.Name)" -ForegroundColor Gray }

    if ($SkipUpload) {
        Write-Host "`nSkipUpload set — artifacts in dist/" -ForegroundColor Yellow
        return
    }

    if (-not $env:TWINE_PASSWORD) {
        Write-Host @"

Set API token before upload (token is never stored in this repo):

  `$env:TWINE_USERNAME = "__token__"
  `$env:TWINE_PASSWORD = "pypi-..."

Create token: https://pypi.org/manage/account/token/
TestPyPI token: https://test.pypi.org/manage/account/token/

Then re-run this script.
"@ -ForegroundColor Yellow
        exit 1
    }

    if (-not $env:TWINE_USERNAME) {
        $env:TWINE_USERNAME = "__token__"
    }

    Write-Step "Upload to $(if ($TestPyPI) { 'TestPyPI' } else { 'PyPI' })"
    if ($TestPyPI) {
        python -m twine upload --repository testpypi dist/*
        Write-Host @"

Test install:
  pip install -i https://test.pypi.org/simple/ meris-agent==$version
  meris version
"@ -ForegroundColor Green
    } else {
        python -m twine upload dist/*
        Write-Host @"

Live install:
  pip install meris-agent==$version
  meris version
"@ -ForegroundColor Green
    }
} finally {
    Pop-Location
}
