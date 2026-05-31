# Meris Agent — 品牌说明

> 正式品牌名：**Meris** · 版本 **0.8.0**（自 Forge 更名，v0.8.0 起移除全部 Forge 兼容层）

## 标识

| 项 | 值 |
|---|---|
| **品牌** | **Meris** |
| **CLI** | `meris` |
| **Python 包** | `meris-agent` |
| **Rust 核心** | `meris-rs` |
| **Harness 目录** | `.meris/` |
| **环境变量** | `MERIS_*` |

## 定位语

> Harness-first · Model-agnostic · Yours to shape

## 更名记录

| 日期 | 变更 |
|------|------|
| 2026-05 | 代号 Forge → 正式名 **Meris** |
| 2026-05 | v0.8.0 移除 `forge` CLI、`.forge/`、`FORGE_*` 兼容 |
| 2026-05 | Haltr / forCode 等候选不再采用 |

## 迁移说明

若仓库仍使用 `.forge/` 或 `FORGE_*`，请手动迁移：

1. 重命名 `.forge/` → `.meris/`
2. 环境变量 `FORGE_*` → `MERIS_*`
3. 重新 `pip install -e .`（仅安装 `meris` 命令）

新仓库请 `meris init-harness` 生成 `.meris/`。

Hook 环境变量：`MERIS_TOOL_NAME`、`MERIS_HOOK_PHASE` 等。

## 相关文档

- [docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md) — 本机扩展与 Rust 配置
- [docs/RUST_ROADMAP.md](docs/RUST_ROADMAP.md) — Rust 移植路线
