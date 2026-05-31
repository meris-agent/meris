# Meris Agent 开发规划

> 基于 2026-05-31 缺口审计 · 优先级驱动

## 阶段 A — 可用性基线

| # | 任务 | 验收 | 状态 |
|---|------|------|------|
| A1 | `meris doctor` 环境诊断 | 检查 key/url/model + 探活 | ✅ |
| A2 | `permissions.allow` 强制执行 | allow/deny 单测 | ✅ |
| A3 | Plan → `tasks.md` 落盘 | `meris plan --out` | ✅ |
| A4 | Ctrl+C 优雅中断 | session 存为 cancelled | ✅ |
| A5 | `git_commit` 工具 | approve 模式可拦截 | ✅ |
| A6 | GitHub Actions CI | push PR 跑 pytest | ✅ |
| A7 | 日常 dogfood | parallel + run 全绿 | ⏳ 需有效 API |

## 阶段 B — 工作流深度

| # | 任务 | 验收 | 状态 |
|---|------|------|------|
| B1 | Spec 工作流 | `meris spec next`、模板三件套 | ✅ |
| B2 | Plan → Run 衔接 | `meris run --from-plan/spec` | ✅ |
| B3 | Session 管理 | delete、prune、TUI 恢复 | ✅ |
| B4 | 事件 Hooks | onSave / onCommit | ✅ |
| B5 | Benchmark 集 | `meris benchmark run` | ✅ |

## 阶段 C — 差异化能力

| # | 任务 | 验收 | 状态 |
|---|------|------|------|
| C1 | Token 级 context 压缩 | 超预算自动裁剪 | ✅ |
| C2 | MCP resources/prompts | 注册到 Agent | ✅ |
| C3 | 多 Provider | Anthropic 原生 | ✅ |
| C4 | Browser / LSP 工具 | fetch_url + lint_file | ✅ |
| C5 | TUI 增强 | session 面板 | ✅ |

## 阶段 D — 长期（可选）

| # | 任务 | 验收 | 状态 |
|---|------|------|------|
| D1 | Rust 移植（P5） | `meris-rs` + `meris native` | ✅ MVP |
| D2 | 品牌定名 | BRAND.md，包名暂不改 | ✅ |
| D3 | IDE 插件 | VS Code/Cursor 扩展 | ✅ |

## Dogfood 原则（Ratchet）

1. 用 Meris 修 Forge
2. Agent 犯错 → 改 AGENTS.md / hook / sensor，不是只改输出
3. 每完成一阶段 → 跑 `pytest` + `meris doctor`

## 命令速查

```bash
meris doctor
meris native status                   # meris-rs 是否可用
meris native build                    # cargo build --release
set MERIS_NATIVE=1                    # 原生 context 压缩

# VS Code / Cursor: 见 docs/LOCAL_SETUP.md

meris plan "add auth" --out .meris/plan/tasks.md
meris run "implement plan" --approve
meris mcp list
meris tui
```
