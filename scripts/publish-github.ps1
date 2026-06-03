# Meris — GitHub repo About + Release (requires gh auth)
# 用法:
#   gh auth login
#   powershell -ExecutionPolicy Bypass -File scripts\publish-github.ps1
param(
    [string]$Tag = "v0.0.1",
    [switch]$SkipAbout,
    [switch]$SkipRelease
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "gh not found. Install: winget install GitHub.cli"
}

gh auth status 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Run first: gh auth login" -ForegroundColor Yellow
    gh auth login --hostname github.com --git-protocol ssh --web
}

Push-Location $Root
try {
    if (-not $SkipAbout) {
        Write-Step "Update repo About + topics"
        gh repo edit meris-agent/meris `
            --description "Harness-first, model-agnostic terminal coding agent (Python + optional Rust)" `
            --homepage "https://github.com/meris-agent/meris#readme" `
            --add-topic coding-agent `
            --add-topic llm `
            --add-topic harness `
            --add-topic cli `
            --add-topic python `
            --add-topic terminal-agent `
            --add-topic mcp
    }

    if (-not $SkipRelease) {
        $notes = Join-Path $Root "docs\RELEASE_v0.0.1.md"
        if (-not (Test-Path $notes)) { throw "Missing $notes" }

        Write-Step "Create GitHub Release $Tag"
        $existing = gh release view $Tag 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Release $Tag already exists — skip" -ForegroundColor Yellow
        } else {
            gh release create $Tag `
                --title "$Tag — First public release" `
                --notes-file $notes
        }
    }

    Write-Host "`nDone: https://github.com/meris-agent/meris/releases/tag/$Tag" -ForegroundColor Green
} finally {
    Pop-Location
}
