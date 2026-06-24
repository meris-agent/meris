# Changelog

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
