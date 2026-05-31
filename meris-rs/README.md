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
meris-rs permissions check --workspace . --tool bash --args '{"command":"git status"}'
meris-rs run doctor          # delegates to Python `meris`
```

## Python integration

```bash
set MERIS_NATIVE=1           # use native context compression in agent loop
meris native status
```

## Scope (P5 MVP)

| Module | Status |
|--------|--------|
| `context` | Token estimate + compress (parity with Python) |
| `permissions` | allow/deny check |
| `settings` | Load `.meris/settings.json` |
| Agent loop / tools / MCP | Python `meris` (delegate via `meris-rs run`) |

Full Rust port of the agent loop is **out of scope** for 0.6.0; this crate is the lean binary foundation.

**Docs**: [../docs/LOCAL_SETUP.md](../docs/LOCAL_SETUP.md) · [../docs/RUST_ROADMAP.md](../docs/RUST_ROADMAP.md)
