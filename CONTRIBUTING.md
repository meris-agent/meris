# Contributing to Meris

Thank you for your interest in Meris. This repo is the open-source **Meris Agent** (CLI + Harness). **Meris Cloud** (hosted SaaS) is proprietary and lives elsewhere — see [CLOUD.md](CLOUD.md).

## Quick links

| Topic | Doc |
|-------|-----|
| Install & first run | [README.md](README.md) · [docs/USER_SETUP.md](docs/USER_SETUP.md) |
| Dev environment (Rust, VS Code) | [docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md) |
| Architecture & modules | [docs/harness/architecture.md](docs/harness/architecture.md) |
| Tests & Definition of Done | [docs/harness/testing.md](docs/harness/testing.md) |
| Full doc index | [docs/README.md](docs/README.md) |

## Development setup

```bash
git clone https://github.com/meris-agent/meris.git
cd meris
pip install -e ".[dev]"
meris version
```

Optional: Rust core, VS Code extension — [docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md).

Windows one-shot: `powershell -ExecutionPolicy Bypass -File scripts\setup-local.ps1`

## Before you open a PR

Run the project Definition of Done:

```bash
pytest tests/ -m "not integration" -q
meris harness check
```

Both must pass. Integration tests may need API keys — see [docs/harness/testing.md](docs/harness/testing.md).

## Code style

- Python **3.11+**
- [Ruff](https://docs.astral.sh/ruff/) — line length **100** (see `pyproject.toml`)
- Match existing module layout under `meris/`
- **Minimal diffs** — prefer extending existing helpers over new abstractions
- Do not edit `**/generated/**`
- Do not delete existing migrations

Harness conventions for this repo: [AGENTS.md](AGENTS.md).

## Pull requests

1. **Fork** and create a branch from `main`.
2. **Describe the change** — what problem it solves and how you tested it.
3. **Keep scope focused** — one logical change per PR when possible.
4. **Update docs** if user-visible behavior or CLI flags change.
5. **No secrets** — never commit `.env`, API keys, or personal `settings.local.yaml`.

We review PRs as time allows. Be patient; smaller, well-tested PRs merge faster.

## Issues

- **Bug reports**: include OS, Python version, `meris version`, steps to reproduce, and redacted logs if possible.
- **Feature requests**: explain the user workflow and why Harness (rules/skills/sensors) cannot solve it today.
- **Questions**: use GitHub Discussions if enabled, or open an issue labeled `question`.

## Security

Report vulnerabilities privately — see [SECURITY.md](SECURITY.md). Do not open public issues for security bugs.

## License

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
