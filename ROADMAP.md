# Meris Agent — Roadmap

> Development history and plans. User-facing docs: [README.md](README.md).

## Product milestones (P1–P5)

| Phase | Scope | Status |
|-------|--------|--------|
| **P1** | Agent loop, tools, provider, harness loaders | ✅ |
| **P2** | Context compression, post-edit sensors, guardrails, git tools, approve mode | ✅ |
| **P3** | MCP client, Textual TUI, config-driven hooks | ✅ |
| **P4** | Session persistence, parallel sessions, skills, subagent, MCP SSE | ✅ |
| **P5** | Rust core MVP → full agent loop (`meris-rs`) | ✅ P5-4 M1–M5 |

## Release phases (Phase A–D)

Historical batch labels used during development. Public version starts at **v0.0.1**.

| Phase | Focus | Highlights |
|-------|--------|------------|
| **A** | Usability baseline | `doctor`, permissions, plan → disk, interrupt-safe sessions, `git_commit`, CI |
| **B** | Workflow depth | Spec workflow, `run --from-plan/spec`, session prune, event hooks, benchmark |
| **C** | Differentiation | Token budget, Anthropic provider, `fetch_url` / `lint_file`, TUI session panel, MCP resources |
| **D** | Distribution | `meris-rs`, VS Code/Cursor extension, Meris rebrand, PyPI packaging |

### Phase A — 可用性基线

| # | 任务 | 验收 | 状态 |
|---|------|------|------|
| A1 | `meris doctor` 环境诊断 | 检查 key/url/model + 探活 | ✅ |
| A2 | `permissions.allow` 强制执行 | allow/deny 单测 | ✅ |
| A3 | Plan → `tasks.md` 落盘 | `meris plan --out` | ✅ |
| A4 | Ctrl+C 优雅中断 | session 存为 cancelled | ✅ |
| A5 | `git_commit` 工具 | approve 模式可拦截 | ✅ |
| A6 | GitHub Actions CI | push PR 跑 pytest | ✅ |
| A7 | 日常 dogfood | parallel + run 全绿 | ⏳ 需有效 API |

### Phase B — 工作流深度

| # | 任务 | 验收 | 状态 |
|---|------|------|------|
| B1 | Spec 工作流 | `meris spec next`、模板三件套 | ✅ |
| B2 | Plan → Run 衔接 | `meris run --from-plan/spec` | ✅ |
| B3 | Session 管理 | delete、prune、TUI 恢复 | ✅ |
| B4 | 事件 Hooks | onSave / onCommit | ✅ |
| B5 | Benchmark 集 | `meris benchmark run` | ✅ |

### Phase C — 差异化能力

| # | 任务 | 验收 | 状态 |
|---|------|------|------|
| C1 | Token 级 context 压缩 | 超预算自动裁剪 | ✅ |
| C2 | MCP resources/prompts | 注册到 Agent | ✅ |
| C3 | 多 Provider | Anthropic 原生 | ✅ |
| C4 | Browser / LSP 工具 | fetch_url + lint_file | ✅ |
| C5 | TUI 增强 | session 面板 | ✅ |

### Phase D — 分发与长期

| # | 任务 | 验收 | 状态 |
|---|------|------|------|
| D1 | Rust 移植（P5） | `meris-rs` + `meris native` | ✅ MVP |
| D2 | 品牌 Meris | BRAND.md · PyPI `meris-agent` | ✅ |
| D3 | IDE 插件 | VS Code/Cursor 扩展 | ✅ |
| D4 | PyPI 发布脚本 | `scripts/publish-pypi.ps1` | ✅ |

## Next (post v0.0.1)

- [x] **`meris ratchet` MVP** — 见 [docs/RATCHET_DESIGN.md](docs/RATCHET_DESIGN.md)
- [x] **`meris ratchet digest` + `insights`** — 主动习惯挖掘（与 scan/analyze 并存）
- [x] **Phase E — Harness 强化（E1–E6）** — 见 [docs/PLAN_PHASE_E.md](docs/PLAN_PHASE_E.md)
- [x] **P5-4 — Rust agent loop（M1–M5）** — 见 [docs/PLAN_P5_4.md](docs/PLAN_P5_4.md)
- [x] **Phase F — Native 稳定化** — 见 [docs/PLAN_PHASE_F.md](docs/PLAN_PHASE_F.md)（F1–F4 + F3-M2 ✅；F5 tag 暂缓）
- [x] GitHub Release workflow + `meris-rs` artifacts（`workflow_dispatch` 可手动构建；正式 Release 页待 tag）
- [ ] PyPI publish `meris-agent==0.0.1`（tag `v0.0.1` + `PYPI_API_TOKEN`，**暂缓**）
- [ ] **Phase G — Codex CLI 对标** — 见 [docs/PLAN_PHASE_G.md](docs/PLAN_PHASE_G.md)（G1–G3 ✅；G4–G6 进行中）
- [x] `MERIS_NATIVE` auto when `meris-rs` available（`MERIS_NATIVE=0` opt out）
- [x] Full agent loop in Rust (P5-4 M1–M5; Python 仍负责 TUI/MCP 配置/动态路由)

## Dogfood 原则（Ratchet）

1. 用 Meris 修 Meris（dogfood）
2. Agent 犯错 → 改 AGENTS.md / hook / sensor，不是只改输出
3. 每完成一阶段 → 跑 `pytest` + `meris doctor`

见 [docs/DOGFOOD_7DAY.md](docs/DOGFOOD_7DAY.md)。

## Maintainer commands

```bash
meris doctor
meris native status
meris native build
set MERIS_NATIVE=1

meris benchmark run
pytest tests/ -m "not integration" -q
```

**Publish PyPI** (Windows):

```powershell
$env:TWINE_USERNAME = "__token__"
$env:TWINE_PASSWORD = "pypi-..."
powershell -ExecutionPolicy Bypass -File scripts\publish-pypi.ps1 -TestPyPI
powershell -ExecutionPolicy Bypass -File scripts\publish-pypi.ps1
```

**Local dev**: [docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md) · **Rust**: [docs/RUST_ROADMAP.md](docs/RUST_ROADMAP.md)
