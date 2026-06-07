## Meris Agent v0.0.2 — Phase G + Route B ready

First **recommended** public install. Includes Codex CLI sandbox parity (presets, allowlist, platform docs) and Route B native-loop defaults.

> Note: tag `v0.0.1` points to an earlier commit; use **v0.0.2** for Phase G features.

### Highlights

- **Phase G1** — Codex-style `sandbox.preset` (`workspace-write` default, network isolated)
- **Phase G2** — `sandbox.networkAllowlist` (command-level + bwrap share-net)
- **Phase G3** — [Platform matrix](harness/PLATFORM_MATRIX.md) + doctor Codex preset hints
- **Phase G4** — `MERIS_NATIVE_LOOP=auto` in templates; live benchmark 3-task Route B standard
- Native agent loop: `MERIS_NATIVE_LOOP=auto` · `meris-rs run ask|plan|run|review`
- CLI: `ask`, `plan`, `run`, `tui`, `doctor`, `init-harness`, `review`, `exec`, `ratchet`
- Linux bubblewrap OS sandbox · Windows WSL guidance

### Install

```bash
pip install meris-agent==0.0.2
# or from tag:
pip install git+https://github.com/meris-agent/meris.git@v0.0.2
```

Requires Python 3.11+. Bring your own LLM API key.

### Quick start

```bash
cp .env.example .env   # set API key + MERIS_NATIVE_LOOP=auto
cd your-project
meris init-harness .
meris doctor
meris run --approve "your task"
```

### Release checklist (maintainers)

```bash
meris release check
python scripts/run_benchmark_live.py   # 3/3 with API key
git tag v0.0.2 && git push origin v0.0.2
# GitHub Actions: Release + PyPI (needs PYPI_API_TOKEN secret)
```

See [ROUTE_B_COMPLETION.md](ROUTE_B_COMPLETION.md) · [E0_RELEASE_CHECKLIST.md](E0_RELEASE_CHECKLIST.md)

### Docs

- [README](https://github.com/meris-agent/meris#readme)
- [USER_SETUP](https://github.com/meris-agent/meris/blob/main/docs/USER_SETUP.md)
- [PLAN_PHASE_G](https://github.com/meris-agent/meris/blob/main/docs/PLAN_PHASE_G.md)
