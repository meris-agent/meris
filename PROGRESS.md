# 项目进度

## 已完成
- [x] P1–P4 + 阶段 A（doctor、permissions、plan、interrupt、git_commit、CI）
- [x] **阶段 B（v0.4.0）** — spec、session、hooks、benchmark
- [x] **阶段 C（v0.5.0）** — token 压缩、Anthropic、MCP extras、TUI 面板
- [x] **阶段 D（v0.6.0）**
  - [x] D1 `meris-rs` + `meris native`
  - [x] D2 `BRAND.md`
  - [x] D3 VS Code/Cursor 扩展
  - [x] **本机配置**：Cursor 扩展联接 + Rust/MSVC + `meris-rs` release（见 [docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md)）
- [x] **品牌 Meris（v0.7.0+）** — CLI / 包 / Harness 统一为 Meris
- [x] **TUI 提交修复（v0.8.1）** — `_task_busy`；7 天 dogfood 文档
- [x] **7 天 dogfood Ratchet + 开源整理** — 见下方「Dogfood 复盘」
- [x] **首个公开版本 v0.0.1** — 对外 tag 从 0.0.1 起计

## 进行中
- [ ] Benchmark 持续跟踪（`meris benchmark run`）
- [ ] meris-rs 全量 Agent loop 移植（P5 后续）

## Dogfood 复盘（7 天 · Ratchet）

| # | 错误类型 | 典型表现 | Harness 改动 |
|---|----------|----------|----------------|
| 1 | **不知道路径规范** | plan 路径写错；README 写成 `meris/README.md` | `AGENTS.md` 仓库布局 + `.meris/rules/paths.md` |
| 2 | **输出格式不对** | plan 无 `- [ ]`，benchmark `plan_smoke` fail | `AGENTS.md` Plan 节 + `.meris/skills/plan-format.md` + `benchmark.py` 判题 |
| 3 | **工作区 cwd 搞错** | 在 vault 根跑 run，README 被 block | `.meris/rules/workspace.md` + vault `AGENTS.md` 双 cwd 表 |
| 4 | **bash 乱用 / 路径假** | `cd /workspace`、`find`、`pwd` 被拒；pytest 没跑成 | `.meris/rules/bash-permissions.md`（`L-bash-verify`） |

**代码层修复（非 Harness）**：TUI `_task_busy`；context `sanitize_messages_for_api`（tool 消息 400）。

**Meris 比裸 Chat 多什么**：permissions/block、DoD sensor、session 持久化、Plan 落盘、Ratchet 可沉淀规则。

## 阶段 D 命令
```bash
# Rust 核心
meris native status
meris native build
set MERIS_NATIVE=1
meris-rs context compress --max-tokens 3000 < msgs.json

# IDE（见 extensions/vscode-meris/README.md）
# Command Palette → Meris: Run Agent
```

## 阶段 C 命令
```bash
set MERIS_PROVIDER=anthropic
pip install meris-agent[anthropic]
meris tui
meris mcp list
```

## 阶段 B 命令
```bash
meris spec init "my feature"
meris benchmark run
meris session prune --keep 10

# Ratchet：被动（失败）+ 主动（习惯）
meris ratchet scan
meris ratchet digest
meris ratchet insights review
```

## Ratchet 摘要

- [L-bash-verify] 跑测试用 `pytest tests/ -m "not integration" -q`；禁止 `/workspace` 与 find/pwd bash；探索用 glob/read_file。
