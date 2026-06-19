# Phase I — Vibe Coding 对标补齐

> 承接 Agent Window H1–H12 与市面 vibe coding 差距分析。

## 阶段总览

| 阶段 | 交付 | 优先级 |
|------|------|--------|
| I1 | @ 文件/选区上下文注入 | P0 |
| I2 | 内嵌终端流（stdout/stderr） | P0 |
| I3 | 模型 / 路由状态条 | P1 |
| I4 | Plan 面板（`- [ ]` checkbox） | P1 |
| I5 | Hunk 级 diff Accept/Reject | P1 |
| I6 | Session 搜索过滤 | P2 |
| I7 | Live Preview（HTML iframe） | P2 |
| I8 | 多任务并行 UI（`meris parallel`） | P3 |

## I1 — @ 上下文

- Composer `@` 按钮 + 文件搜索下拉
- VS Code：工作区文件列表 + 当前选区
- `meris ui`：`/api/files` + `/api/file`
- 提交时拼入 task 前缀

## I2 — 终端

- spawn 进程 stdout/stderr → `terminal` postMessage
- 主栏底部可折叠 Terminal 面板

## I3 — 模型条

- `session_start.model` + `thinking` 路由行 → `#model-bar`

## I4 — Plan

- `plan` JSONL 事件（`items[]` checkbox）
- 右栏或浮层 Plan 面板，可勾选（写回 `tasks.md`）

## I5 — Diff hunks

- 解析 `diff_preview` 为 hunk 卡片
- 每 hunk Accept → `git apply` / 写文件

## I6 — Session 搜索

- Sessions 顶栏 filter input

## I7 — Preview

- `file_change` 对 `.html` 显示 Preview
- iframe `srcdoc` 或 `/api/preview`

## I8 — Parallel

- Parallel 面板：多行任务 → `meris parallel`

## DoD

```bash
pytest tests/ -m "not integration" -q
node --check extensions/vscode-meris/media/agent.js
node --check extensions/vscode-meris/media/phase-i.js
```

- [x] I1–I8 已实现（扩展 v0.3.0 + `meris ui`）
- [x] I+ Plan 回写 · Parallel 事件流 · 优先级规则
