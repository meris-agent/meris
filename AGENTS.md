# AGENTS.md — Meris Harness（目录，非百科全书）

> Inspired by OpenAI Codex AGENTS.md · 细节见 [docs/harness/README.md](docs/harness/README.md)

## 产品宗旨

Meris 是**会自我进化的 coding agent**：进化写在 Harness（本文件、`.meris/`、各项目根目录 `PROGRESS.md`），不是只改模型输出。

## 快速参考

| 主题 | 文档 |
|------|------|
| **工作区 / 项目 / Skill / MCP** | [docs/harness/concepts.md](docs/harness/concepts.md) |
| 功能优先级三问 | `.meris/rules/feature-prioritization.md` |
| 包布局、CLI 扩展 | [docs/harness/architecture.md](docs/harness/architecture.md) |
| pytest、DoD、benchmark | [docs/harness/testing.md](docs/harness/testing.md) |
| 模型路由、local 覆盖 | [docs/harness/routing.md](docs/harness/routing.md) |
| Plan `- [ ]` 格式 | [docs/harness/plan-format.md](docs/harness/plan-format.md) |
| Bash 沙箱 warn/strict | [docs/harness/sandbox.md](docs/harness/sandbox.md) |
| 事件流 JSONL | [docs/harness/events.md](docs/harness/events.md) |

**不确定时**：先 `read_file` 上表路径，再改代码。

## 项目说明

- 包管理：pip（`pyproject.toml` + hatchling）
- Python 包目录：`meris/`（import 用 `from meris....`）
- 根目录文档：`README.md`、`AGENTS.md`；维护者进度在私有知识库，仓库内 `PROGRESS.md` 仅为摘要

## Plan 模式（摘要）

- 输出 `- [ ]` checkbox 任务清单，至少 3 条；不改代码  
- 完整规则：[docs/harness/plan-format.md](docs/harness/plan-format.md)

## 代码风格

- Python 3.11+，ruff line-length 100  
- 最小 diff，匹配现有结构  

## 禁止操作

- 不要改 `**/generated/**`  
- 不要自动 `git push`  
- 不要删已有 migration  

## 会话约定

- 新会话先读 `PROGRESS.md`（用户项目）或私有知识库 `Meris-开发进度`（维护 Meris 仓库时）；断点变化时更新  
- cwd / bash / pytest：见 `.meris/rules/`（已注入的短规则）

## Definition of Done

```bash
pytest tests/ -m "not integration" -q
meris harness check
```

任一失败则任务未完成。详见 [docs/harness/testing.md](docs/harness/testing.md)。
