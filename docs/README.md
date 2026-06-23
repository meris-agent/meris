# Meris documentation

Public docs for **Meris Agent** users and contributors.

| Language | Start here |
|----------|------------|
| **English** | [README](../README.md) — install, quick start, command table |
| **中文** | [USER_SETUP.md](USER_SETUP.md) — 安装、API Key、Harness 初始化 |

---

## Choose your path

```text
New user                    Power user                 Contributor
    │                           │                          │
    ▼                           ▼                          ▼
README / USER_SETUP          Harness docs              CONTRIBUTING
    │                           │                          │
    ├─ MODELS.md               ├─ concepts.md             ├─ LOCAL_SETUP
    ├─ init-harness            ├─ plan-format             ├─ testing.md
    └─ doctor                  ├─ sandbox / events        └─ architecture.md
                               └─ RATCHET_DESIGN
```

---

## For users

### First 10 minutes

1. `pip install meris-agent`
2. Set `MERIS_PROVIDER` + API key — [MODELS.md](MODELS.md)
3. `cd your-repo && meris init-harness . && meris doctor`
4. `meris ask "…"` → `meris plan "…"` → `meris run --approve "…"`

Detailed walkthrough (中文): [USER_SETUP.md](USER_SETUP.md)

### Everyday reference

| Doc | When to read |
|-----|--------------|
| [MODELS.md](MODELS.md) | Switch LLM vendor, local/Ollama, team model templates |
| [harness/plan-format.md](harness/plan-format.md) | Plan mode checkbox tasks |
| [harness/sandbox.md](harness/sandbox.md) | Bash permissions and presets |
| [harness/routing.md](harness/routing.md) | Model routing in `settings.yaml` |
| [examples/ainote-vault/](examples/ainote-vault/) | Optional: Markdown vault + nested code repo |

### Optional components

| Component | Doc |
|-----------|-----|
| Rust core (`meris-rs`) | [NATIVE_BINARY.md](NATIVE_BINARY.md) |
| VS Code extension | [extensions/vscode-meris/](../extensions/vscode-meris/) |
| Ratchet (Harness learning) | [RATCHET_DESIGN.md](RATCHET_DESIGN.md) · commands in [README](../README.md) |

---

## Harness deep dive

Index: [harness/README.md](harness/README.md)

| Doc | Audience | Topic |
|-----|----------|-------|
| [concepts.md](harness/concepts.md) | UI / Harness authors | Workspace, project, Skill, MCP boundaries |
| [multi-repo.md](harness/multi-repo.md) | Multi-repo workflows | Task scope, ask → plan → run |
| [git-workflow.md](harness/git-workflow.md) | IDE users | Agent Window changes & commit |
| [events.md](harness/events.md) | Automation | JSONL event stream, `meris exec --json` |
| [PLATFORM_MATRIX.md](harness/PLATFORM_MATRIX.md) | Ops | OS sandbox capability matrix |
| [SEATBELT_DESIGN.md](harness/SEATBELT_DESIGN.md) | macOS | Seatbelt policy design |

---

## For contributors

| Doc | Topic |
|-----|-------|
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | PR process, DoD, code style |
| [LOCAL_SETUP.md](LOCAL_SETUP.md) | Windows dev: extension, Rust build |
| [harness/architecture.md](harness/architecture.md) | Package layout, CLI extension |
| [harness/testing.md](harness/testing.md) | pytest, benchmark, release check |

---

## Meris Cloud

**Meris Cloud** (browser SaaS) is **proprietary** and not in this repo. Local agent: docs above. Hosted product: [CLOUD.md](../CLOUD.md).

---

## Naming

- **Meris** · CLI `meris` · PyPI `meris-agent` · env `MERIS_*` · Harness dir `.meris/`
- **North star**: a self-evolving coding agent — evolution lives in the Harness (rules, skills, sensors), not in hoping the model remembers. See [README](../README.md).
