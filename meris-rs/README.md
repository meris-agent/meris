# meris-rs

Native Rust core for [Meris Agent](../README.md) — fast harness primitives with optional Python delegation.

## Build

```bash
# from repo root (meris/)
meris native build
# or
cd meris-rs && cargo build --release
```

Requires [Rust](https://rustup.rs) 1.70+.

## Commands

```bash
meris-rs version
meris-rs context tokens "hello world"
meris-rs context compress --max-tokens 3000 < messages.json
meris-rs permissions --workspace . --tool bash --args '{"command":"git status"}'
meris-rs sandbox check --workspace . --command "pwd" --mode strict
meris-rs sandbox run --workspace . --timeout 120 -- pytest tests/ -q
meris-rs sandbox probe --workspace .   # bubblewrap availability (Linux)
meris-rs provider probe                # LLM env (base URL, model, key set)
meris-rs tools list
meris-rs tools schemas --read-only
meris-rs tools run --workspace . --tool read_file --args '{"path":"README.md","limit":5}'
meris-rs tools run --workspace . --tool bash --args '{"command":"git status -s"}'
meris-rs agent run --workspace . --mode ask --task "Summarize README" --max-turns 5
meris-rs agent session list --workspace .
meris-rs run doctor          # delegates to Python `meris`
```

## Python integration

```bash
set MERIS_NATIVE=1           # native compress, permissions, sandbox, tools
set MERIS_NATIVE_LOOP=1      # ask/plan/review via meris-rs agent run
meris native status
```

## Scope

| Module | Status |
|--------|--------|
| `context` | Token estimate + compress |
| `permissions` | allow/deny check |
| `sandbox` | policy + bubblewrap run |
| `provider` | OpenAI-compatible chat |
| `tools` | read_file / glob / grep / write_file / edit_file / bash + schemas |
| `sensors` | postEdit (settings) + on-complete bridge via `meris harness` |
| `agent` | M1/M2 loop + session (read-only + run modes) |
| MCP / full run mode | Python `meris` (see [PLAN_P5_4.md](../docs/PLAN_P5_4.md)) |

**Docs**: [../docs/LOCAL_SETUP.md](../docs/LOCAL_SETUP.md) · [../docs/RUST_ROADMAP.md](../docs/RUST_ROADMAP.md) · [../docs/PLAN_P5_4.md](../docs/PLAN_P5_4.md)
