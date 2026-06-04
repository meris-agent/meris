# AGENTS.md — Meris Harness (Instructions subsystem)
# Inspired by: OpenAI Codex AGENTS.md + Claude Code CLAUDE.md

## 产品宗旨（North star）

Meris 是**会自我进化的 coding agent**：越用越顺手，自动贴合当前项目与用户习惯。进化写在 Harness（本文件、`.meris/skills`、`.meris/rules`、`PROGRESS.md`、session），不是只改模型输出。见 [VISION.md](VISION.md)。

## 项目说明

- 包管理器：pip（`pyproject.toml` + hatchling）
- 测试命令：`pytest tests/ -m "not integration"`

## 仓库布局

| 路径 | 说明 |
|------|------|
| `README.md` | 仓库根目录说明（**cwd 在本仓库时路径为 `README.md`，不是 `meris/README.md`**） |
| `meris/cli.py` | CLI 入口 |
| `meris/loop.py` | Agent 主循环 |
| `meris/harness/` | Harness 子系统 |
| `meris/tools/` | 工具注册 |
| `meris/provider/` | LLM Provider |

计划与代码中的路径、import 一律使用 `meris/` 包前缀（如 `from meris.harness.sessions import ...`）。

## Plan 模式（`meris plan`）

输出 **Markdown 任务清单**，格式必须严格遵守：

- 每条任务一行，使用 **未完成 checkbox**：`- [ ] 描述`（中括号内必须有空格）
- 至少 3 条 `- [ ]` 任务（用户要求 N 条时按 N 条）
- 不要用纯数字列表 `1.` 代替 checkbox
- 文件路径用 `meris/...`（如 `meris/cli.py`），README 在本仓库 cwd 下为 `README.md`
- 只输出计划，不改代码

示例：

```markdown
- [ ] 在 meris/harness/sessions.py 添加 prune 函数
- [ ] 在 meris/cli.py 添加 session prune 子命令
- [ ] 更新 PROGRESS.md 并跑 pytest
```

## 代码风格
- Python 3.11+，ruff line-length 100
- 最小 diff，匹配现有命名与结构

## 禁止操作
- 不要修改 `**/generated/**` 下的文件
- 不要自动 `git push`
- 不要删除 `migrations/` 下已有 migration

## 会话约定
- 新会话第一件事：读 `PROGRESS.md`
- 任务完成或断点变化：更新 `PROGRESS.md`
- Plan 任务可 `load_skill plan-format`；路径/ cwd 见 `.meris/rules/`

## 完成定义 (Definition of Done)

任务完成 = 以下命令全部退出码为 0：

- `pytest tests/ -m "not integration" -q`

任何一项失败，任务不算完成。
