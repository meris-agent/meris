# Meris Harness 深度文档

> **AGENTS.md 是目录**；细节按需 `read_file` 本目录下的文件。

| 文档 | 何时读 |
|------|--------|
| [concepts.md](concepts.md) | **工作区 / 项目 / Skill / MCP 边界**（改 UI 或 Harness 前必读） |
| [multi-repo.md](multi-repo.md) | **多仓库 task scope**、ask → plan → run 流程 |
| [architecture.md](architecture.md) | 改包结构、找模块、加 CLI 子命令 |
| [testing.md](testing.md) | 跑测试、DoD、benchmark |
| [routing.md](routing.md) | 模型路由、`settings.yaml` / local 覆盖 |
| [plan-format.md](plan-format.md) | `meris plan`、checkbox 任务清单 |
| [sandbox.md](sandbox.md) | bash 沙箱 mode、超时、平台说明 |
| [events.md](events.md) | Loop JSONL 事件、`meris exec --json` |
| [git-workflow.md](git-workflow.md) | Agent Window 改动面板与 Commit |
| [PLATFORM_MATRIX.md](PLATFORM_MATRIX.md) | 各 OS 沙箱矩阵（Codex 对照） |
| [SEATBELT_DESIGN.md](SEATBELT_DESIGN.md) | macOS Seatbelt 程序化策略 |

自动注入的短规则仍在 `.meris/rules/*.md`（`inject: always`）。其它 rules 见 system prompt 里的 **Rules index**。
