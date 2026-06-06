# 项目进度

## 已完成
- [x] P1–P4 + 阶段 A（doctor、permissions、plan、interrupt、git_commit、CI）
- [x] **阶段 B（v0.4.0）** — spec、session、hooks、benchmark
- [x] **阶段 C（v0.5.0）** — token 压缩、Anthropic、MCP extras、TUI 面板
- [x] **阶段 D（v0.6.0）** — meris-rs、BRAND、VS Code/Cursor 扩展
- [x] **Ratchet** — scan/analyze + digest/insights（`575d619`）
- [x] **Phase E（E1–E6）** — 见 [docs/PLAN_PHASE_E.md](docs/PLAN_PHASE_E.md)

## 进行中
- [x] Linux bubblewrap OS 沙箱（`sandbox.osSandbox: auto|require`）
- [x] 网络隔离（`network: isolated`）+ `.env` 遮罩（`maskSecrets`）
- [x] Windows `doctor` WSL/bwrap 检测
- [x] **Live benchmark** — `run_benchmark_live.py` + GitHub workflow_dispatch
- [x] **E0 发布准备** — `meris release check`（不打 tag）
- [ ] **E0 发布** — 打 tag `v0.0.1`（暂缓）
- [x] **P5-3** — Rust tools + schemas + bash native
- [x] **P5-4 M1** — Rust agent loop（read-only）+ [PLAN_P5_4.md](docs/PLAN_P5_4.md)
- [x] **P5-4 M2** — run 模式写工具 + postEdit/onComplete sensors
- [ ] **P5-4 M3–M5** — MCP / hooks / 单二进制

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
python scripts/run_benchmark_live.py    # 需 API
meris benchmark run --local-only
meris release check                     # E0 发布前自检
meris doctor
meris run "…" --event-stream .meris/events/run.jsonl
meris exec "…" --json
meris review --staged
meris ratchet digest
```

## Ratchet 摘要

- [L-bash-verify] pytest 用 `pytest tests/ -m "not integration" -q`；禁止 find/pwd/`/workspace` bash。
