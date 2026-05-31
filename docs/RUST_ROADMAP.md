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
- [x] CLI：`context`, `permissions`, `version`, `run`（委托 Python）
- [x] `meris native status|build`
- [x] `MERIS_NATIVE` 环境变量
- [x] CI：`cargo test` + `cargo build --release`

### 🔜 P5-1 — Harness 默认 native（小步）

- [ ] Loop 内 permissions 检查可选走 `meris-rs permissions check`（减少重复实现 drift）
- [ ] Python ↔ Rust  parity 集成测试（同一 fixtures JSON）
- [ ] 发布预编译 `meris-rs` GitHub Release（Windows/Linux）

### 🔜 P5-2 — Provider 层

- [ ] Rust：`reqwest` + OpenAI-compatible chat completions
- [ ] 环境变量：`MERIS_PROVIDER`, `MERIS_BASE_URL`, `LLM_API_KEY`
- [ ] Python loop 可切换 `ProviderBackend::RustOpenAI`

### 🔜 P5-3 — Tools 子集

- [ ] `read_file`, `glob`, `grep`（只读工具先行）
- [ ] `bash`（subprocess，权限仍走 harness）
- [ ] JSON schema 与 Python `ToolRegistry` 对齐

### 🔜 P5-4 — 完整 Agent loop

- [ ] Rust 主循环 + 会话持久化
- [ ] MCP client（`rmcp` 或 stdio 自实现）
- [ ] Python 降级为「插件 / 脚本 hooks」层
- [ ] 单二进制 `meris` 替换 `pip install` 路径（长期）

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
