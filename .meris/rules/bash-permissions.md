---
inject: always
---

# Bash 与验证（Meris 仓库 cwd）

<!-- ratchet:L-bash-verify -->

## cwd

- Agent 的 cwd **已是** Meris git 仓库根（含 `pyproject.toml`）。
- **禁止**使用 `/workspace`、`cd /workspace` 或其它容器/假路径。
- 需要确认根目录时：用 `glob({"pattern": "pyproject.toml"})`，不要用 `pwd` / `find` / `ls` bash。

## 允许的 bash（与 `.meris/settings.yaml` 一致）

仅下列模式会通过权限检查；其它 bash **会被拒绝**：

| 用途 | 命令示例 |
|------|----------|
| 跑测试 | `pytest tests/ -m "not integration" -q` |
| Python 小脚本 | `python -m pytest ...`（需匹配 `python*`） |
| Git 只读/暂存 | `git status`、`git diff`、`git add ...` |

**不要**用 bash 做：`find`、`pwd`、`ls`、`cd`（探索仓库用 **glob / read_file / grep / git_status**）。

## 跑 pytest

- 用户要求「改完跑 pytest」或 DoD 时，**直接**执行：

  ```bash
  pytest tests/ -m "not integration" -q
  ```

- 不要前缀 `cd ... &&`（除非 cwd 明确不对；本仓库默认 cwd 已对）。
- 若 bash 被拒：先检查命令是否以 `pytest` 开头；仍失败则说明限制，并提示用户在终端手动跑上述命令。

## 纯文档改动

- 只改 `*.md` 等文档时，postEdit sensor 仍可能跑 pytest；Agent 应用 **同上** 的 pytest 命令验证，不要用 generic bash 探路。
