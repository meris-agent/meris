# Meris Agent — 本机一键配置 (Windows)
# 用法: powershell -ExecutionPolicy Bypass -File scripts\setup-local.ps1
param(
    [switch]$SkipExtension,
    [switch]$SkipRust,
    [switch]$InstallToolchain
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ExtSrc = Join-Path $Root "extensions\vscode-meris"
$ExtDstCursor = Join-Path $env:USERPROFILE ".cursor\extensions\meris-agent-vscode"
$MerisRs = Join-Path $Root "meris-rs"
$VcVars = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

if (-not $SkipExtension) {
    Write-Step "Link Cursor extension"
    if (-not (Test-Path $ExtSrc)) { throw "Extension source missing: $ExtSrc" }
    if (Test-Path $ExtDstCursor) { Remove-Item $ExtDstCursor -Force -Recurse }
    cmd /c mklink /J "$ExtDstCursor" "$ExtSrc" | Out-Null
    Write-Host "Linked: $ExtDstCursor -> $ExtSrc" -ForegroundColor Green
    Write-Host "Reload Cursor window (Developer: Reload Window)" -ForegroundColor Yellow
}

if (-not $SkipRust) {
    if ($InstallToolchain) {
        Write-Step "Install Rust (winget)"
        winget install Rustlang.Rustup --accept-package-agreements --accept-source-agreements 2>$null
        Write-Step "Install VS Build Tools (winget, may take several minutes)"
        winget install Microsoft.VisualStudio.2022.BuildTools --accept-package-agreements --accept-source-agreements --override "--wait --passive --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended" 2>$null
    }

    $env:Path = "$env:USERPROFILE\.cargo\bin;" + $env:Path
    if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
        Write-Host "cargo not found. Re-run with -InstallToolchain or install from https://rustup.rs" -ForegroundColor Red
        exit 1
    }

    Write-Step "Build meris-rs (release)"
    if (Test-Path $VcVars) {
        cmd /c "`"$VcVars`" && cd /d `"$MerisRs`" && cargo test && cargo build --release"
    } else {
        Push-Location $MerisRs
        cargo test
        cargo build --release
        Pop-Location
    }

    Write-Step "meris native status"
    Push-Location $Root
    python -m meris.cli native status
    Pop-Location
    Write-Host "`nOptional: setx MERIS_NATIVE 1" -ForegroundColor Yellow
}

Write-Host "`nDone. See docs/LOCAL_SETUP.md" -ForegroundColor Green
