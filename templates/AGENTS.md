# AGENTS.md — Harness 目录（模板）

> 细节放在 `docs/harness/`；Agent 按需 `read_file`。

## 项目说明

- 包管理器：（pip / pnpm / cargo …）
- 测试命令：见 [docs/harness/testing.md](docs/harness/testing.md)
- 源码包目录：（如 `meris/` 或 `src/`）

## 深度文档

| 主题 | 路径 |
|------|------|
| 架构与目录 | [docs/harness/architecture.md](docs/harness/architecture.md) |
| 测试与 DoD | [docs/harness/testing.md](docs/harness/testing.md) |

## Plan 模式（摘要）

- `- [ ]` checkbox，至少 3 条 — 见 `docs/harness/plan-format.md` 或 `.meris/skills/plan-format.md`

## 禁止操作

- 不要改 `**/generated/**`
- 不要自动 `git push`

## 会话约定

- 新会话读 `PROGRESS.md`

## Definition of Done

<!-- 按项目修改 docs/harness/testing.md -->
- `echo "configure DoD in docs/harness/testing.md"`
