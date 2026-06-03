## Meris Agent v0.0.1 — First public release

Harness-first, model-agnostic terminal coding agent (Python + optional Rust).

### Highlights

- CLI: `ask`, `plan`, `run`, `tui`, `doctor`, `init-harness`
- Harness: `AGENTS.md`, `.meris/settings.json`, permissions, hooks, DoD sensors
- Session persistence, MCP client, parallel sessions, skills, subagent
- Optional `meris-rs` for native context compression (`MERIS_NATIVE=1`)
- VS Code / Cursor extension in `extensions/vscode-meris/`

### Install

```bash
pip install git+https://github.com/meris-agent/meris.git@v0.0.1
# or from source:
git clone https://github.com/meris-agent/meris.git && cd meris && pip install -e .
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

### Docs

- [README](https://github.com/meris-agent/meris#readme)
- [ROADMAP](https://github.com/meris-agent/meris/blob/main/ROADMAP.md)
- [Local setup (extension + Rust)](https://github.com/meris-agent/meris/blob/main/docs/LOCAL_SETUP.md)
