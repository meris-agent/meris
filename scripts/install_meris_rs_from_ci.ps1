# Meris — install meris-rs from GitHub Actions release workflow artifacts
# 用法:
#   gh auth login
#   powershell -ExecutionPolicy Bypass -File scripts\install_meris_rs_from_ci.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\install_meris_rs_from_ci.ps1 -RunId 123456789
param(
    [string]$Repo = "meris-agent/meris",
    [string]$Workflow = "release.yml",
    [ValidateSet(
        "x86_64-pc-windows-msvc",
        "x86_64-unknown-linux-gnu",
        "x86_64-apple-darwin",
        "aarch64-apple-darwin"
    )]
    [string]$Target = $(if ($IsWindows -or $env:OS -match "Windows") {
        "x86_64-pc-windows-msvc"
    } elseif ($IsMacOS) {
        "aarch64-apple-darwin"
    } else {
        "x86_64-unknown-linux-gnu"
    }),
    [string]$RunId = "",
    [switch]$CleanDebug,
    [switch]$SkipVerify
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "gh not found. Install: winget install GitHub.cli"
}

function Invoke-Gh {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & gh @Args
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    if ($code -ne 0) {
        throw "gh $($Args -join ' ') failed (exit $code)"
    }
}

function Get-ReleaseRunId {
    param([string]$Id)
    if ($Id) {
        return $Id
    }
    $json = Invoke-Gh run list `
        --repo $Repo `
        --workflow $Workflow `
        --status success `
        --limit 1 `
        --json databaseId
    $runs = $json | ConvertFrom-Json
    if (-not $runs -or $runs.Count -eq 0) {
        throw "No successful '$Workflow' runs found. Trigger one: Actions -> release -> Run workflow"
    }
    return [string]$runs[0].databaseId
}

function Get-ArtifactFileName {
    param([string]$RustTarget)
    switch ($RustTarget) {
        "x86_64-pc-windows-msvc" { return "meris-rs-x86_64-pc-windows-msvc.exe" }
        default { return "meris-rs-$RustTarget" }
    }
}

function Get-InstallPath {
    param([string]$RustTarget)
    $releaseDir = Join-Path $Root "meris-rs\target\release"
    if ($RustTarget -eq "x86_64-pc-windows-msvc") {
        return Join-Path $releaseDir "meris-rs.exe"
    }
    return Join-Path $releaseDir "meris-rs"
}

Push-Location $Root
try {
    try {
        Invoke-Gh auth status | Out-Null
    } catch {
        Write-Host "Run first: gh auth login" -ForegroundColor Yellow
        Invoke-Gh auth login --hostname github.com --git-protocol ssh --web
    }

    $runId = Get-ReleaseRunId -Id $RunId
    $artifactName = "meris-rs-$Target"
    $artifactFile = Get-ArtifactFileName -RustTarget $Target
    $installPath = Get-InstallPath -RustTarget $Target
    $downloadDir = Join-Path $env:TEMP "meris-rs-ci-$runId-$Target"

    Write-Step "Download artifact '$artifactName' from run $runId"
    if (Test-Path $downloadDir) {
        Remove-Item -Recurse -Force $downloadDir
    }
    New-Item -ItemType Directory -Path $downloadDir | Out-Null

    Invoke-Gh run download $runId `
        --repo $Repo `
        --name $artifactName `
        --dir $downloadDir

    $src = Join-Path $downloadDir $artifactFile
    if (-not (Test-Path $src)) {
        $found = @(Get-ChildItem -Path $downloadDir -Recurse -File | Where-Object {
            $_.Name -like "meris-rs*"
        })
        if ($found.Count -eq 1) {
            $src = $found[0].FullName
        } else {
            throw "Expected '$artifactFile' under $downloadDir"
        }
    }

    Write-Step "Install to $installPath"
    $releaseDir = Split-Path -Parent $installPath
    New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null
    Copy-Item -Force $src $installPath

    if ($CleanDebug) {
        $debugBin = Join-Path $Root "meris-rs\target\debug\meris-rs.exe"
        if (Test-Path $debugBin) {
            Remove-Item -Force $debugBin
            Write-Host "Removed stale debug binary: $debugBin" -ForegroundColor DarkGray
        }
    }

    if (-not $SkipVerify) {
        Write-Step "Verify meris-rs"
        $help = & $installPath --help 2>&1 | Out-String
        foreach ($cmd in @("provider", "tools", "agent", "sandbox")) {
            if ($help -notmatch $cmd) {
                throw "Installed binary looks outdated (missing '$cmd' subcommand). Re-run release workflow on main."
            }
        }
        & $installPath version
        if ($LASTEXITCODE -ne 0) {
            throw "meris-rs version failed"
        }

        if (Get-Command python -ErrorAction SilentlyContinue) {
            python -m meris native status
        }
    }

    Write-Host "`nDone. Installed meris-rs from CI run $runId -> $installPath" -ForegroundColor Green
    Write-Host "Recommended: add MERIS_NATIVE_LOOP=auto to .env" -ForegroundColor Cyan
} finally {
    Pop-Location
}
