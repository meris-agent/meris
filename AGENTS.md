# AGENTS.md — Meris Harness (Instructions subsystem)
# Inspired by: OpenAI Codex AGENTS.md + Claude Code CLAUDE.md

## 项目说明

- 包管理器：pip（`pyproject.toml` + hatchling）
- 测试命令：`pytest tests/ -m "not integration"`

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

## 完成定义 (Definition of Done)

任务完成 = 以下命令全部退出码为 0：

- `pytest tests/ -m "not integration" -q`

任何一项失败，任务不算完成。
