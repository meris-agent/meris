## Meris Agent v0.0.1 — First public release

Harness-first, model-agnostic terminal coding agent (Python + optional Rust).

### Highlights

- CLI: `ask`, `plan`, `run`, `tui`, `doctor`, `init-harness`, `review`, `exec`, `harness check`
- Harness: `AGENTS.md`, `.meris/settings.yaml`, permissions, sandbox (warn/strict + Linux bubblewrap)
- Phase E: event stream, Ratchet TUI, offline benchmark mock, CI
- Session persistence, MCP client, parallel sessions, skills, subagent
- Optional `meris-rs` (auto when binary present; `MERIS_NATIVE=0` to disable)
- VS Code / Cursor extension in `extensions/vscode-meris/`

### Install

```bash
pip install meris-agent==0.0.1
# or from tag:
pip install git+https://github.com/meris-agent/meris.git@v0.0.1
```

Requires Python 3.11+. Bring your own LLM API key.

### Quick start

```bash
export OPENAI_API_KEY=sk-...
export MERIS_BASE_URL=https://api.deepseek.com/v1
export MERIS_MODEL=deepseek-chat

cd your-project
meris init-harness .
meris doctor
meris run --approve "your task"
```

### Release checklist (before tagging)

```bash
meris release check          # pytest + mock benchmark + harness + cargo (no tag/PyPI)
python -m build              # optional: wheel in dist/
# then: git tag v0.0.1 && git push origin v0.0.1
# PyPI: TWINE_* + scripts/publish-pypi.ps1
```

### Docs

- [README](https://github.com/meris-agent/meris#readme)
- [ROADMAP](https://github.com/meris-agent/meris/blob/main/ROADMAP.md)
- [Local setup (extension + Rust)](https://github.com/meris-agent/meris/blob/main/docs/LOCAL_SETUP.md)
