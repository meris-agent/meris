# 项目进度

## 已完成
- [x] P1–P4 + 阶段 A（doctor、permissions、plan、interrupt、git_commit、CI）
- [x] **阶段 B（v0.4.0）** — spec、session、hooks、benchmark
- [x] **阶段 C（v0.5.0）** — token 压缩、Anthropic、MCP extras、TUI 面板
- [x] **阶段 D（v0.6.0）** — meris-rs、BRAND、VS Code/Cursor 扩展
- [x] **Ratchet** — scan/analyze + digest/insights（`575d619`）
- [x] **Phase E（E1–E6）** — 见 [docs/PLAN_PHASE_E.md](docs/PLAN_PHASE_E.md)

## 线路 B — Dogfood（当前）

见 [docs/ROUTE_B_DOGFOOD.md](docs/ROUTE_B_DOGFOOD.md) · `.env.example` 推荐 `MERIS_NATIVE_LOOP=auto`

- [x] release workflow 验证 + `install_meris_rs_from_ci.ps1`
- [x] env 就绪（`MERIS_NATIVE_LOOP=auto` · native status 全 True · doctor 全绿）
- [x] live benchmark Route B 3 task 标准（`read_hello` + `docs_smoke` + `list_tools`）
- [ ] 日常真实任务 dogfood（1–2 周）
- [x] Ratchet 30 分钟闭环（2026-06-07 · 见下方）

## Phase G — Codex CLI 对标（✅ 完成）

见 [docs/PLAN_PHASE_G.md](docs/PLAN_PHASE_G.md) · 发版 [docs/RELEASE_v0.0.2.md](docs/RELEASE_v0.0.2.md)

- [x] **G1** — Codex 风格 `sandbox.preset`（workspace-write 默认 · network isolated）
- [x] **G2** — network allowlist（命令级 + bwrap share-net）
- [x] **G3** — 平台矩阵 + doctor Codex preset 提示
- [x] **G4** — Route B 完成标准（`.env` 默认 auto · live 3 task · doctor native loop）
- [x] **G5** — E0 发版 `v0.0.2`（Phase G 完整 · Route B 就绪）
- [x] **G6** — macOS Seatbelt spike + **G6.2 MVP**（`sandbox-exec` · read-only / workspace-write）

## Phase I — Vibe Coding 对标（✅ I1–I8 + I+）

见 [docs/PLAN_PHASE_I.md](docs/PLAN_PHASE_I.md) · 扩展 `v0.3.0`

- [x] Plan 勾选智能回写（`meris plan-sync` · 保留标题/正文）
- [x] Parallel 多任务 JSONL 事件流 + UI 分栏
- [x] 功能优先级三问 → `.meris/rules/feature-prioritization.md`

## 进行中
- [x] Linux bubblewrap OS 沙箱（`sandbox.osSandbox: auto|require`）
- [x] 网络隔离（`network: isolated`）+ `.env` 遮罩（`maskSecrets`）
- [x] Windows `doctor` WSL/bwrap 检测
- [x] **Live benchmark** — `run_benchmark_live.py` + GitHub workflow_dispatch
- [x] **E0 发布准备** — `meris release check` 全绿（不打 tag）
- [x] **E0 发布** — tag `v0.0.2` · [RELEASE_v0.0.2.md](docs/RELEASE_v0.0.2.md)
- [x] **P5-3** — Rust tools + schemas + bash native
- [x] **P5-4 M1** — Rust agent loop（read-only）+ [PLAN_P5_4.md](docs/PLAN_P5_4.md)
- [x] **P5-4 M2** — run 模式写工具 + postEdit/onComplete sensors
- [x] **P5-4 M3** — MCP JSONL 桥 + native loop 工具合并
- [x] **P5-4 M4** — hooks / EventStream / plan 模式
- [x] **P5-4 M5** — system-prompt 桥 + `meris-rs run` 原生入口
- [x] **Phase F** — native 稳定化与发布准备（F1–F4 + F3-M2 ✅；F5 tag 暂缓）· [PLAN_PHASE_F.md](docs/PLAN_PHASE_F.md)

## 近期落地（E0 / P5-1）
- [x] `settings.local` 文档（[USER_SETUP.md](docs/USER_SETUP.md)）
- [x] `MERIS_NATIVE` 二进制存在时自动启用（`MERIS_NATIVE=0` 关闭）
- [x] TUI Ratchet apply/reject（Enter → a/r）
- [x] VS Code：`review` / `exec --json` / `run --event-stream`
- [x] GitHub Release workflow + 多平台 `meris-rs` 二进制

## Phase E 摘要

| 阶段 | 交付 |
|------|------|
| E1 | `docs/harness/`、rules 按需注入、`meris harness check` |
| E2 | DoD 解析、Ratchet `L-harness-check`、benchmark local/reject |
| E3 | sandbox warn/strict、bubblewrap（Linux）、`meris-rs sandbox run/check/probe` |
| E4 | JSONL 事件流、`--event-stream`、`meris exec --json`、TUI 事件 |
| E5 | `meris review`、`review` 路由 |
| E6 | `user-prefs.md`、TUI Ratchet 面板、rules 按 name 合并 |

## Dogfood 复盘

| # | 错误类型 | Harness 改动 |
|---|----------|----------------|
| 1 | 路径规范 | `.meris/rules/paths.md` |
| 2 | Plan 格式 | `.meris/skills/plan-format.md` + benchmark |
| 3 | cwd 错误 | `.meris/rules/workspace.md` |
| 4 | bash 乱用 | `.meris/rules/bash-permissions.md` |

## 常用命令

```bash
pytest tests/ -m "not integration" -q
meris harness check
python scripts/run_benchmark_mock.py
python scripts/run_benchmark_mock.py --native-only   # native bridge smokes
python scripts/run_benchmark_mock.py --native        # mock + native (11 tasks)
python scripts/run_benchmark_live.py    # 需 API
meris benchmark run --local-only
meris release check                     # E0 发布前自检
# 详见 docs/E0_RELEASE_CHECKLIST.md
meris doctor
meris run "…" --event-stream .meris/events/run.jsonl
meris exec "…" --json
meris review --staged
meris ratchet digest
```

## Ratchet 摘要

- [L-bash-verify] pytest 用 `pytest tests/ -m "not integration" -q`；禁止 find/pwd/`/workspace` bash。
- [L-path] 路径/命名不规范（meris/README、错误包目录前缀等）

## Ratchet 闭环 @2026-06-07

**基线**

- pytest: 232 passed
- benchmark: 7/8（`harness_paths_smoke` fail · 曾误写嵌套 README 路径，已 reject）
- pending: 0 → benchmark 自动生成 `ratchet-20260607-120350-f0d0bc`

**Applied**

- `ratchet-20260607-120350-f0d0bc` → `.meris/rules/paths.md`（L-path · append `<!-- ratchet:L-path -->`）
- 手动迭代：`L-path-answer` — 路径问答只答一行 `README.md`，禁止对比句（否则 benchmark reject 误杀）

**After benchmark**

- `harness_paths_smoke`: fail → **pass**
- 全量 benchmark: **8/8 (100%)**
- `meris ratchet status`: pending 0

**第二次同类任务预期**：问根 README 路径时 agent 只输出 `README.md`，不再写「不是 meris/README.md」。

## Session note (2026-06-07 02:42 UTC)
- **Task**: Reply with exactly: pong
- **Status**: dod_failed


## Session note (2026-06-07 02:48 UTC)
- **Task**: List top-level files in meris/ as bullet points
- **Status**: dod_failed
