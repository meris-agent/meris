# Meris Agent

Model-agnostic terminal coding agent — **Harness-first**, inspired by AtomCode, Claude Code, Codex, Cursor, and Kiro.

## Philosophy

```
Agent = Model + Harness
```

- **Built lean** — minimal deps, fast startup (Python MVP → optional Rust later)
- **Model-agnostic** — OpenAI-compatible API or native Anthropic (`MERIS_PROVIDER=anthropic`)
- **Yours to shape** — approve mode, PROGRESS checkpoints, interrupt-safe
- **Harness-first** — AGENTS.md, permissions, hooks, DoD sensors

## Quick start

```bash
cd meris
pip install -e .

# Set your model (OpenAI-compatible)
set OPENAI_API_KEY=sk-...
set MERIS_BASE_URL=https://api.deepseek.com/v1
set MERIS_MODEL=deepseek-chat

# Init harness in your project
meris init-harness /path/to/your/repo

# Ask (read-only)
meris ask "where is auth handled?"

# Plan (writes tasks, no code)
meris plan "add rate limiting to /api/users"

# Run agent
meris run "fix the failing test in tests/test_auth.py"

# Approve mode — confirm each write/edit/bash
meris run --approve "refactor loop.py"

# Skip DoD sensors
meris run --no-sensor "explore codebase structure"
```

## Project layout

```
meris/
├── meris/              # Python agent package
├── meris-rs/           # Rust harness core (P5 MVP)
├── extensions/
│   └── vscode-meris/   # VS Code / Cursor plugin
├── templates/
└── tests/
```

## Harness files (in target repo)

| File | Subsystem | From |
|------|-----------|------|
| `AGENTS.md` | Instructions | Codex / 新智元 |
| `.meris/settings.json` | Tools (permissions) | Claude Code |
| `PROGRESS.md` | State | Anthropic / 新智元 |
| `.meris/spec/*.md` | Spec workflow | Kiro (optional) |

## Design doc

See `Articles/MyCodingAgent-架构设计.md` in the Obsidian vault.

**Dogfood（7 天）**：见 [docs/DOGFOOD_7DAY.md](docs/DOGFOOD_7DAY.md)

## Roadmap

- [x] P1: Loop + tools + provider + harness loaders
- [x] P2: Context compression, post-edit sensors, guardrails, git tools, approve mode
- [x] P3: MCP client, Textual TUI, config-driven hooks
- [x] P4: Session persistence, parallel sessions, skills, subagent, MCP SSE
- [x] P5: Rust core MVP (`meris-rs` — context, permissions; full loop still Python)

## Phase D (v0.6.0)

**本机配置（扩展 + Rust）**：见 [docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md) · Rust 路线见 [docs/RUST_ROADMAP.md](docs/RUST_ROADMAP.md)

一键脚本（Windows）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup-local.ps1
```

**Native Rust core** (`meris-rs/`):

```bash
meris native build              # requires Rust: https://rustup.rs
meris native status
set MERIS_NATIVE=1              # optional native context compression
meris-rs run doctor             # delegates to Python meris
```

**Brand**: see [BRAND.md](BRAND.md) — **Meris** (PyPI: `meris-agent`).

**IDE extension** (VS Code / Cursor): `extensions/vscode-meris/` — 本机已联接至 `%USERPROFILE%\.cursor\extensions\meris-agent-vscode`，Reload Window 后命令面板搜 **Meris:**。

## Phase C (v0.5.0)

**Token budget** — `.meris/settings.json`:

```json
"context": { "maxMessages": 48, "maxTokens": 32000, "maxToolTokens": 2000 }
```

**Anthropic native**:

```bash
pip install meris-agent[anthropic]
set MERIS_PROVIDER=anthropic
set ANTHROPIC_API_KEY=sk-ant-...
meris doctor
```

**Extra tools**: `fetch_url` (HTTP GET), `lint_file` (ruff check).

**MCP resources/prompts**: auto-registered as `mcp_{server}_read_resource` / `mcp_{server}_get_prompt`.

**TUI session panel**: `meris tui` — left sidebar lists sessions; Enter to resume, Ctrl+S refresh.

## Phase A

```bash
meris doctor                    # env + harness + API probe
meris plan "add feature"        # saves .meris/plan/tasks.md
meris run --from-plan "go"      # implement saved plan
```

See [ROADMAP.md](ROADMAP.md) for full plan.

## Spec workflow (Phase B)

```bash
meris spec init "rate limiting"
meris spec status
meris spec next --note "REST API only"
meris run --from-spec "implement checklist"
```

## Event hooks

```json
{
  "hooks": {
    "onSave": [
      { "matcher": "*.py", "command": "python -m ruff check $MERIS_SAVED_PATH" }
    ],
    "onCommit": [
      { "command": "pytest tests/ -q" }
    ]
  }
}
```

## Benchmark

```bash
meris benchmark list
meris benchmark run
```

## MCP (external tools)

Configure servers in `.meris/settings.json`:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"]
    }
  }
}
```

```bash
pip install meris-agent[mcp]
meris mcp list
```

Tools appear as `mcp_{server}_{tool}` in the agent registry. Resources and prompts are exposed as `mcp_{server}_read_resource` and `mcp_{server}_get_prompt`.

## TUI

```bash
pip install meris-agent[tui]
meris tui --cwd . --mode run --approve
```

Interactive log + task input. Left **Sessions** panel — Enter to resume, Ctrl+R latest, Ctrl+S refresh. Ctrl+L clears log.

## Hooks (settings.json)

Shell hooks run before/after tools (Claude Code–style):

```json
{
  "hooks": {
    "preToolUse": [
      { "matcher": "bash", "command": "echo pre $MERIS_TOOL_NAME" }
    ],
    "postToolUse": [
      { "matcher": "write_file|edit_file", "command": "echo post" }
    ]
  }
}
```

Env vars: `MERIS_TOOL_NAME`, `MERIS_TOOL_ARGS`, `MERIS_TOOL_RESULT`, `MERIS_HOOK_PHASE`.

## Sessions (persist & resume)

Every run auto-saves to `.meris/sessions/{id}.json`. Resume after interrupt:

```bash
meris session list
meris session show abc123
meris session resume abc123
meris run "task" --session-id my-id   # optional fixed id
```

## Parallel sessions

```bash
meris parallel "explain auth" "explain db layer" --mode ask -j 2
meris parallel "fix test A" "fix test B" --mode run --isolate   # git worktree each
```

## Skills

Place markdown in `.meris/skills/{name}.md`. Agent sees index in prompt; call `load_skill` to fetch full doc.

## Subagent

In `run` mode, agent can call `subagent_run` to delegate read-only exploration with isolated context.

## MCP SSE transport

```json
{
  "mcpServers": {
    "remote": {
      "transport": "sse",
      "url": "http://localhost:8080/sse"
    }
  }
}
```
