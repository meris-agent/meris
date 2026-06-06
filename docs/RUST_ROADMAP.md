# Meris Agent — Rust 移植路线

> 阶段 D1 交付物说明 · 与 Python 版并行演进

## 为什么要 Rust？

| 目标 | Python 现状 | Rust 方向 |
|------|------------|-----------|
| 冷启动 | import + 依赖加载，数百 ms～秒级 | 单二进制，目标 <1s |
| 分发 | 需要 Python 3.11+ 与 pip | 一个 `meris-rs.exe` / `meris` 可执行文件 |
| Harness 热路径 | 纯 Python 足够 | context 压缩、permissions 可 native 加速 |
| 迭代速度 | 快，改 Harness 方便 | 编译慢，适合稳定核心 |

**结论**：Rust 不是「更聪明」，而是「更快、更 lean、更好分发」。Agent 智力仍取决于 LLM。

## 当前架构（0.6.0）

```
┌─────────────────────────────────────────┐
│  Cursor 扩展 / meris CLI / meris tui     │  ← 用户入口
├─────────────────────────────────────────┤
│  Python meris (loop, tools, MCP, TUI)   │  ← Agent 主循环
├─────────────────────────────────────────┤
│  meris-rs (context, permissions, JSON)  │  ← 可选 MERIS_NATIVE=1
└─────────────────────────────────────────┘
```

Python 通过 `meris.native` 模块发现 `meris-rs/target/release/meris-rs`，子进程调用 `context compress` 等子命令。

## 已移植模块

| 模块 | Python | Rust | 验收 |
|------|--------|------|------|
| Token 估算 | `harness/context.py` | `meris-rs/src/context.rs` | 单元测试 + 行为对齐 |
| Message 压缩 | 同上 | 同上 | `MERIS_NATIVE=1` 可切换 |
| Permissions | `harness/permissions.py` | `meris-rs/src/permissions.rs` | `meris-rs permissions check` |
| Settings 加载 | `harness/settings.py` | `meris-rs/src/settings.rs` | JSON 解析 |

## 路线图

### ✅ P5-MVP（v0.6.0 — 已完成）

- [x] `meris-rs` crate + `cargo test`
- [x] CLI：`context`, `permissions`, `sandbox`, `version`, `run`（委托 Python）
- [x] `meris native status|build`
- [x] `MERIS_NATIVE` auto when binary present（`MERIS_NATIVE=0` opt out）
- [x] CI：`cargo test` + `cargo build --release` + bubblewrap + parity script

### 🔜 P5-1 — Harness 默认 native（小步）

- [x] permissions / sandbox 走 `meris-rs` when native enabled
- [x] Python ↔ Rust parity 测试（`tests/test_native_parity.py` + `fixtures/parity.json`）
- [x] `scripts/check_native_parity.py` in CI
- [ ] 发布预编译 `meris-rs` GitHub Release（workflow 已有，待 tag）

### 🔜 P5-2 — Provider 层

- [x] Rust：`reqwest` + OpenAI-compatible `provider chat` / `provider probe`
- [x] 环境变量：`MERIS_BASE_URL`, `OPENAI_API_KEY` / `DEEPSEEK_API_KEY` 等
- [x] Python loop：`RustOpenAIProvider` when `native_provider_enabled()`（继承 `MERIS_NATIVE` auto）

### 🔜 P5-3 — Tools 子集

- [x] `read_file`, `glob`, `grep`（`meris-rs tools run` + Python native 回退）
- [x] `bash`（`tools run` + sandbox；Python `_native_or` 回退）
- [x] JSON schema 与 Python `ToolRegistry` 对齐（`tools schemas` + `check_tool_schemas_parity.py`）

### 🔜 P5-4 — 完整 Agent loop

- [x] **M1** — `agent run` + session 持久化 + read-only native loop（见 [PLAN_P5_4.md](PLAN_P5_4.md)）
- [x] **M2** — `run` 模式 write_file/edit_file + postEdit + on-complete 桥
- [x] **M3** — MCP JSONL 桥（`meris mcp serve`）+ native loop
- [x] **M4** — hooks / EventStream / plan 模式
- [ ] **M5** — 单二进制默认入口

## 何时继续下一 phase？

建议在以下信号出现时再投入 P5-2+：

1. **Dogfood 频率高**，Python 冷启动成为明显痛点
2. **需要给无 Python 环境的同事**分发工具
3. **context/permissions parity 测试**稳定，无 drift

若主要在自己机器 `pip install -e .` 开发，**维持 P5-MVP 即可**，不必急于全量移植。

## 开发命令

```bash
# 本机构建（Windows 需 MSVC）
meris native build
meris native status

# 直接 cargo
cd meris-rs && cargo test && cargo build --release

# 启用 native 压缩
set MERIS_NATIVE=1
meris run "your task"
```

## 参考

- 设计文档：Obsidian `Articles/MyCodingAgent-架构设计.md` § AtomCode 对比
- 本机步骤：[LOCAL_SETUP.md](LOCAL_SETUP.md)
