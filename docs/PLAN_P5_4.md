# P5-4 — Rust 全量 Agent Loop

> 规划文档 · 与 [RUST_ROADMAP.md](RUST_ROADMAP.md) 衔接 · **不打 tag 前可并行 dogfood**

## 目标

将 Python `meris/loop.py` 的主循环逐步迁入 `meris-rs`，最终支持：

- 单二进制冷启动（无 Python import）
- 会话 JSON 与 Python 100% 互操作（`.meris/sessions/`）
- MCP / hooks / sensors 可选降级或插件化

**智力仍取决于 LLM**；Rust 负责 orchestration 与 harness 热路径。

## 当前架构（P5-4 M1 落地后）

```
┌──────────────────────────────────────────────┐
│  meris CLI / TUI / 扩展                       │
├──────────────────────────────────────────────┤
│  Python loop（run 模式、MCP、hooks、sensors）   │  ← 默认
├──────────────────────────────────────────────┤
│  meris-rs agent run（ask/plan/review + native）│  ← MERIS_NATIVE_LOOP=1|auto
├──────────────────────────────────────────────┤
│  meris-rs：context, permissions, sandbox,     │
│            provider, tools, session           │
└──────────────────────────────────────────────┘
```

## 里程碑

| 阶段 | 交付 | 验收 |
|------|------|------|
| **M1** ✅ | `agent run` + session 读写 + read-only 工具链 | `cargo test` + `test_rust_agent.py` + CI smoke |
| **M2** ✅ | `run` 模式 write/edit + postEdit + on-complete 桥 | mock benchmark + schema parity |
| **M3** ✅ | MCP JSONL 桥（`meris mcp serve`）+ native loop schema 合并 | `test_mcp_bridge.py` |
| **M4** ✅ | hooks 桥 + EventStream JSONL + plan 保存 | `test_hooks_bridge.py` |
| **M5** | TUI/CLI 默认 native loop；Python 仅插件 | 冷启动 <1s；Release 二进制 |

## M1 范围（已实现）

- `meris-rs/src/session.rs` — 与 `meris.harness.sessions.SessionRecord` 同字段 JSON
- `meris-rs/src/agent.rs` — compress → provider.chat → permissions → tools → 持久化
- CLI：`agent run`、`agent session list|show`
- Python：`MERIS_NATIVE_LOOP=1|auto`，`ask/plan/review` 且未指定 provider 时走 native
- 工具集：read_file / glob / grep（+ run 模式 bash 经 tools，loop M1 仍 read-only）

## M2 范围（已实现）

1. Rust `write_file` / `edit_file` + schemas parity（6 tools in run mode）
2. `agent run --mode run` + `--require-approval`（`@meris-approve` stdin 协议）
3. postEdit：Rust 直接跑 `sensors.postEdit`；onComplete：`meris harness on-complete --json`
4. Python：`MERIS_NATIVE_LOOP` 支持 `run` 模式；`write_file`/`edit_file` native 回退

## M3 范围（已实现）

1. `meris mcp serve` — JSONL 长连接桥（schemas / call / close）
2. `meris mcp schemas --json` / `meris mcp call --json` — 一次性调用
3. `meris-rs` 启动 agent 时合并 builtin + MCP schemas；`mcp_*` 工具走桥
4. 审批：`MCPManager.tool_read_only_flags` 与 Python loop 对齐

## M4 范围（已实现）

1. `meris harness hook pre|post|on-save --json` — PreToolUse / PostToolUse / onSave 桥
2. `meris harness ratchet-record --json` — permission_denied 等事件
3. `meris-rs agent run --event-stream` — JSONL 与 Python EventStream 对齐
4. `--save-plan` / `--plan-output` — plan 模式写入 `.meris/plan/tasks.md`

## M5 / 长期

- `meris-rs run` 成为默认入口（现仍委托 Python）
- GitHub Release 预编译 + pip 包可选 bundled binary
- 删除重复 Python harness 热路径

## 环境变量

| 变量 | 含义 |
|------|------|
| `MERIS_NATIVE_LOOP=1` | ask/plan/review 走 Rust loop |
| `MERIS_NATIVE_LOOP=auto` | 与 `MERIS_NATIVE` 同时启用时走 Rust loop |
| `MERIS_NATIVE_LOOP=0` | 强制 Python loop |

## 开发命令

```bash
cd meris-rs && cargo test && cargo build --release

# 只读 native loop（需 API key）
set MERIS_NATIVE_LOOP=1
meris ask "List top-level py files"

# 会话
meris-rs agent session list --workspace .
meris-rs agent session show --workspace . --id <id>
```

## 风险与约束

- Windows 本地 `cargo build` 可能被 App Control 拦截 — 依赖 Linux CI
- M1 不含 MCP — `run` 模式仍必须 Python
- Provider 错误 / 429 重试 — M2 对齐 Python factory

## 参考

- Python loop：`meris/loop.py`
- Sessions：`meris/harness/sessions.py`
- P5-3 tools：`meris-rs/src/tools.rs`
