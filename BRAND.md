# Meris Agent — 品牌说明

> 正式品牌名：**Meris** · 版本 **0.7.0**（自 Forge 更名）

## 标识

| 项 | 值 |
|---|---|
| **品牌** | **Meris** |
| **CLI** | `meris`（`forge` 为兼容别名，后续版本移除） |
| **Python 包** | `meris-agent` |
| **Rust 核心** | `meris-rs` |
| **Harness 目录** | `.meris/`（仍可读 legacy `.forge/`） |
| **环境变量** | `MERIS_*`（仍可读 legacy `FORGE_*`） |

## 定位语

> Harness-first · Model-agnostic · Yours to shape

## 更名记录

| 日期 | 变更 |
|------|------|
| 2026-05 | 代号 Forge → 正式名 **Meris** |
| 2026-05 | Haltr / forCode 等候选不再采用 |

## 迁移说明

已有仓库若仍使用 `.forge/settings.json`，Meris 会自动识别；新仓库请 `meris init-harness` 生成 `.meris/`。

Hook 环境变量请改用 `MERIS_TOOL_NAME`、`MERIS_HOOK_PHASE` 等；旧 `FORGE_*` 变量在文档中标记为 deprecated。

## 相关文档

- [docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md) — 本机扩展与 Rust 配置
- [docs/RUST_ROADMAP.md](docs/RUST_ROADMAP.md) — Rust 移植路线
