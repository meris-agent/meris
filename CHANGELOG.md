# Changelog

## 0.1.0 (2026-06-24)

**Open-source launch** — single clean git history; Meris Cloud remains proprietary ([CLOUD.md](CLOUD.md)).

### Added

- Harness entropy scan: `meris harness gc`
- Session handoff: `.meris/handoff.md` on failed / max-turns runs
- Ratchet verify gate on apply; failure clustering (`meris ratchet cluster`)
- Benchmark regression vs `.meris/benchmark/baseline.json` (`meris benchmark regression`)
- Environment contracts: `.meris/environments/*.yaml`, `init-harness` seeds defaults
- Cloud template contract docs: [docs/cloud/template-contract.md](docs/cloud/template-contract.md)

### Install

```bash
pip install meris-agent==0.1.0
```

## 0.0.2 (2026-06-21)

First PyPI release after **Meris Cloud split** from the open-source monorepo.

### Changed

- Meris Cloud (API, Worker, Web, SaaS) moved to the private `meris-cloud` repository — see [CLOUD.md](CLOUD.md).
- Removed `meris cloud` CLI subcommand and `[cloud]` optional extra from this package.

### Added

- `CLOUD.md` — pointer for users looking for hosted Cloud.
- Harness modules used by Cloud worker (`meris.harness.git_summary`, etc.) remain in Agent.

### Install

```bash
pip install meris-agent==0.0.2
```

PyPI ships both **sdist** and **wheel** (`meris_agent-0.0.2-py3-none-any.whl`).

## 0.0.1

Initial public preview on PyPI (monorepo era, included Cloud extras).
