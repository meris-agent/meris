# Meris Agent

Model-agnostic terminal coding agent — **Harness-first**, inspired by AtomCode, Claude Code, Codex, Cursor, and Kiro.

```
Agent = Model + Harness
```

**North star**: a **self-evolving** coding agent — the more you use it in a project, the better it fits your repo and habits. Evolution lives in the Harness (rules, skills, sessions), not in hoping the model remembers. See [VISION.md](VISION.md).

Meris ships a lean CLI (`meris`) plus a **Harness** layer you control: `AGENTS.md`, permissions, hooks, and Definition-of-Done sensors. Bring your own LLM (OpenAI-compatible or Anthropic).

## Install

**From PyPI:**

```bash
pip install meris-agent
pip install "meris-agent[tui]"        # Textual TUI
pip install "meris-agent[anthropic]"  # native Anthropic provider
pip install "meris-agent[mcp]"        # MCP client
pip install "meris-agent[full]"       # all optional deps
```

**From source:**

```bash
git clone https://github.com/meris-agent/meris.git
cd meris
pip install -e .
```

Requires **Python 3.11+**. Meris does not bundle a model — set an API key (see below).

## Quick start

```bash
cd your-project

meris version

# Pick a provider preset (OpenAI, DeepSeek, Gemini, GLM, Qwen, Groq, Anthropic, Ollama, …)
export MERIS_PROVIDER=deepseek   # or: openai | gemini | glm | moonshot | qwen | anthropic | ollama
export DEEPSEEK_API_KEY=sk-...   # env name depends on provider — run: meris models show deepseek

meris models list                # all presets + current env
meris init-harness .
meris doctor

meris ask "where is auth handled?"
meris plan "add rate limiting to /api/users"
meris run --approve "fix the failing test in tests/test_auth.py"
```

On Windows, use `set VAR=value` instead of `export`. Copy [.env.example](.env.example) to `.env` for local overrides. Full vendor table: [docs/MODELS.md](docs/MODELS.md). **Hand this to new users:** [docs/USER_SETUP.md](docs/USER_SETUP.md).

## Commands

| Command | What it does |
|---------|----------------|
| `meris ask "…"` | Read-only Q&A over your repo |
| `meris plan "…"` | Write a task list to `.meris/plan/tasks.md` (no code changes) |
| `meris run "…"` | Full agent: read / edit / bash / git tools |
| `meris run --approve "…"` | Same as run, but confirm each write/bash |
| `meris run --from-plan "…"` | Implement the saved plan |
| `meris run --no-sensor "…"` | Skip post-edit DoD sensors |
| `meris models list` | Show all provider presets + current env |
| `meris models show <provider>` | Show model & env details for a provider |
| `meris doctor` | Check API key, model, and harness files |
| `meris init-harness .` | Scaffold `AGENTS.md`, `.meris/settings.yaml`, `PROGRESS.md` |

## Harness (your project)

After `meris init-harness`, these files steer the agent in **your** repo:

| File | Role |
|------|------|
| `AGENTS.md` | Project rules, layout, DoD |
| `.meris/settings.yaml` | Tool permissions, sensors, hooks, MCP, models |
| `PROGRESS.md` | Cross-session progress notes |
| `.meris/skills/*.md` | Optional domain skills |
| `.meris/spec/*.md` | Optional spec workflow (Kiro-style) |

Templates live in [`templates/`](templates/). Example vault harness: [`docs/examples/ainote-vault/`](docs/examples/ainote-vault/).

## Configuration

End-user onboarding (install → API key → `init-harness` → `doctor`): **[docs/USER_SETUP.md](docs/USER_SETUP.md)**.

**Environment variables** (common):

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` / `LLM_API_KEY` | API key (OpenAI-compatible) |
| `MERIS_BASE_URL` | API base URL |
| `MERIS_MODEL` | Model name |
| `MERIS_PROVIDER=anthropic` | Use native Anthropic (`ANTHROPIC_API_KEY`) |
| `MERIS_NATIVE=1` | Prefer Rust context compression (optional) |

**Context budget** in `.meris/settings.yaml`:

```json
"context": { "maxMessages": 48, "maxTokens": 32000, "maxToolTokens": 2000 }
```

**Permissions** — allow/deny tool patterns (bash globs, path blocks). See [`templates/settings.example.yaml`](templates/settings.example.yaml).

## Workflows

**Plan → run**

```bash
meris plan "add session prune command"
meris run --from-plan "implement the plan" --approve
```

**Spec checklist**

```bash
meris spec init "rate limiting"
meris spec status
meris spec next --note "REST API only"
meris run --from-spec "implement checklist"
```

**Benchmark** (harness regression)

```bash
meris benchmark list
meris benchmark run
```

**Ratchet** (learn from failures → update harness)

```bash
meris init-harness .
meris ratchet learn --init             # project layout → proposals

meris run --ratchet "your task"        # after run: profile + scan proposals
meris benchmark run                    # failures → events.jsonl; may auto-scan
meris ratchet profile --show           # habits from approve_denied events
meris ratchet analyze --last-fail      # LLM proposals (needs API)
meris ratchet analyze --dry-run        # preview prompt only
meris ratchet review                   # apply or reject interactively
```

## TUI

```bash
pip install "meris-agent[tui]"
meris tui --cwd . --mode run --approve
```

Interactive log + task input. **Sessions** panel on the left — Enter to resume, Ctrl+R latest, Ctrl+S refresh, Ctrl+L clear log. Enter or Ctrl+Enter sends a message.

## MCP (external tools)

Add servers in `.meris/settings.json`:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"]
    },
    "remote": {
      "transport": "sse",
      "url": "http://localhost:8080/sse"
    }
  }
}
```

```bash
pip install "meris-agent[mcp]"
meris mcp list
```

Tools register as `mcp_{server}_{tool}`; resources and prompts as `mcp_{server}_read_resource` / `mcp_{server}_get_prompt`.

## Sessions & parallel

Every run saves to `.meris/sessions/{id}.json`:

```bash
meris session list
meris session show abc123
meris session resume abc123
meris run "task" --session-id my-id
meris session prune --keep 10
```

Run multiple tasks:

```bash
meris parallel "explain auth" "explain db layer" --mode ask -j 2
meris parallel "fix test A" "fix test B" --mode run --isolate
```

In `run` mode, the agent can call `subagent_run` for read-only sub-tasks with isolated context.

## Hooks & skills

**Tool hooks** (Claude Code–style) in `settings.json`:

```json
{
  "hooks": {
    "preToolUse": [
      { "matcher": "bash", "command": "echo pre $MERIS_TOOL_NAME" }
    ],
    "postToolUse": [
      { "matcher": "write_file|edit_file", "command": "echo post" }
    ],
    "onSave": [
      { "matcher": "*.py", "command": "python -m ruff check $MERIS_SAVED_PATH" }
    ],
    "onCommit": [
      { "command": "pytest tests/ -q" }
    ]
  }
}
```

Env: `MERIS_TOOL_NAME`, `MERIS_TOOL_ARGS`, `MERIS_TOOL_RESULT`, `MERIS_HOOK_PHASE`.

**Skills** — add `.meris/skills/{name}.md`; the agent loads them via `load_skill`.

## Optional: IDE & Rust

| Component | Docs |
|-----------|------|
| VS Code / Cursor extension | [`extensions/vscode-meris/`](extensions/vscode-meris/) · [LOCAL_SETUP](docs/LOCAL_SETUP.md) |
| Rust core (`meris-rs`) | [RUST_ROADMAP](docs/RUST_ROADMAP.md) · `meris native build` / `MERIS_NATIVE=1` |

Windows one-shot dev setup: `powershell -ExecutionPolicy Bypass -File scripts\setup-local.ps1`

## Contributing & development

| Topic | Link |
|-------|------|
| **Vision — self-evolving agent** | [VISION.md](VISION.md) |
| **Ratchet (`meris ratchet scan`)** | [docs/RATCHET_DESIGN.md](docs/RATCHET_DESIGN.md) |
| Roadmap & release phases (P1–P5, Phase A–D) | [ROADMAP.md](ROADMAP.md) |
| Brand & naming | [BRAND.md](BRAND.md) |
| 7-day dogfood / Ratchet | [docs/DOGFOOD_7DAY.md](docs/DOGFOOD_7DAY.md) |
| Publish to PyPI | `scripts/publish-pypi.ps1` |

**Repo layout:**

```
meris/
├── meris/              # Python agent package
├── meris-rs/           # Optional Rust harness core
├── extensions/vscode-meris/
├── templates/
└── tests/
```

## License

MIT — see [LICENSE](LICENSE).
