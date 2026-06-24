#!/usr/bin/env bash
# Point this repo at .githooks/ (pre-commit runs meris harness commit-check).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
chmod +x .githooks/pre-commit
git config core.hooksPath .githooks
echo "OK: core.hooksPath=.githooks (pre-commit → meris harness commit-check --cached)"
