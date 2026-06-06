# 项目进度

## 已完成
- [x] P1–P4 + 阶段 A（doctor、permissions、plan、interrupt、git_commit、CI）
- [x] **阶段 B（v0.4.0）** — spec、session、hooks、benchmark
- [x] **阶段 C（v0.5.0）** — token 压缩、Anthropic、MCP extras、TUI 面板
- [x] **阶段 D（v0.6.0）** — meris-rs、BRAND、VS Code/Cursor 扩展
- [x] **Ratchet** — scan/analyze + digest/insights（`575d619`）
- [x] **Phase E（E1–E6）** — 见 [docs/PLAN_PHASE_E.md](docs/PLAN_PHASE_E.md)

## 进行中
- [ ] **E0 发布** — PyPI / GitHub Release + `meris-rs` 二进制（可选）
- [ ] **P5** — meris-rs 全量 Agent loop（长期）
- [ ] **Live benchmark** — 定期 `meris benchmark run`（需 API）

## Phase E 摘要

| 阶段 | 交付 |
|------|------|
| E1 | `docs/harness/`、rules 按需注入、`meris harness check` |
| E2 | DoD 解析、Ratchet `L-harness-check`、benchmark local/reject |
| E3 | sandbox warn/strict、`meris-rs sandbox run/check`、native parity |
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
meris doctor
meris run "…" --event-stream .meris/events/run.jsonl
meris exec "…" --json
meris review --staged
meris ratchet digest
```

## Ratchet 摘要

- [L-bash-verify] pytest 用 `pytest tests/ -m "not integration" -q`；禁止 find/pwd/`/workspace` bash。
