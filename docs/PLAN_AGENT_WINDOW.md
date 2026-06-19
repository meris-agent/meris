# Phase H — Agent Window（类 Cursor 可视化）

> 知识库：`Articles/Meris-Agent-Window-规划.md`

## 目标

VS Code / Cursor Webview 消费 `--event-stream` JSONL，对标 Cursor Agent Window，保留 Meris 差异化（Ratchet、DoD、Harness）。

## 阶段总览（H1–H8 ✅）

| 阶段 | 交付 |
|------|------|
| H1 | Webview MVP + JSONL tail |
| H2 | 工具卡片 args + Session 侧栏 |
| H3 | 审批文件通道 + file_change |
| H4 | 常驻侧栏 + Ratchet 右栏 + token 分块 |
| H5 | diff_preview + git 回退 |
| H6 | OpenAI 真流式 + thinking + Markdown/diff 高亮 |
| H7 | Native loop token 分块 + thinking · Anthropic 流式 |
| H8 | Webview 状态持久化 + Ratchet scan + 错误条 |

## H7 — Native + Anthropic 流式 ✅

| # | 任务 | 验收 |
|---|------|------|
| H7.1 | `meris-rs` token 320 字分块 | ✅ 替代 800 字截断 |
| H7.2 | `meris-rs` thinking（压缩） | ✅ compress 后 emit |
| H7.3 | `AnthropicProvider.chat_stream` | ✅ 与 loop 桥接 |

## H8 — 体验收尾 ✅

| # | 任务 | 验收 |
|---|------|------|
| H8.1 | Webview `getState` 草稿持久化 | ✅ task 输入恢复 |
| H8.2 | Ratchet **Scan** 按钮 | ✅ `meris ratchet scan` |
| H8.3 | 错误状态条 | ✅ stderr 横幅 |

## DoD（Phase H 完成）

```bash
pytest tests/ -m "not integration" -q
meris harness check
```

- [x] H1–H8 验收表全绿
- [x] `extensions/vscode-meris` v0.1.0
- [x] vault 笔记 Phase 1–8 已更新

## 阶段总览（H9–H12 ✅）

| 阶段 | 交付 |
|------|------|
| H9 | Rust native HTTP SSE 真流式（替代响应后分块） |
| H10 | 独立 `meris ui` Web 应用（Path B） |
| H11 | 流式过程实时 Markdown 渲染 |
| H12 | `reasoning` 事件 + 专用推理 UI |

## H9 — Rust SSE 真流式

| # | 任务 | 验收 |
|---|------|------|
| H9.1 | `chat_completions_stream` SSE 解析 | ✅ token 逐 delta |
| H9.2 | `agent.rs` 有 event_stream 时走流式 | ✅ 不再 post-hoc chunk |
| H9.3 | provider 单元测试（SSE 行解析） | ✅ |

## H10 — `meris ui`（Path B）

| # | 任务 | 验收 |
|---|------|------|
| H10.1 | `meris ui` CLI + HTTP 服务 | ✅ 默认 :8765 |
| H10.2 | SSE `/api/events` tail JSONL | ✅ |
| H10.3 | REST run/stop/sessions/ratchet/approve | ✅ |
| H10.4 | 浏览器端 Agent UI（复用样式） | ✅ |

## H11 — 流式 Markdown

| # | 任务 | 验收 |
|---|------|------|
| H11.1 | token 流中 `requestAnimationFrame` 增量渲染 | ✅ |
| H11.2 | 工具调用前 finalize 不变 | ✅ |

## H12 — Reasoning UI

| # | 任务 | 验收 |
|---|------|------|
| H12.1 | OpenAI-compat `reasoning_content` delta | ✅ `reasoning` kind |
| H12.2 | `loop.py` 桥接 `reasoning` 事件 | ✅ |
| H12.3 | Webview 可折叠 reasoning 卡片 | ✅ 与 thinking 区分 |
| H12.4 | Rust SSE `reasoning_content` delta | ✅ |

## DoD（Phase H 完成）

```bash
pytest tests/ -m "not integration" -q
meris harness check
cargo test -q  # meris-rs
```

- [x] H1–H12 验收表全绿
- [x] `extensions/vscode-meris` v0.2.0
- [x] `meris ui` standalone
- [x] vault 笔记 Phase 1–12 已更新
