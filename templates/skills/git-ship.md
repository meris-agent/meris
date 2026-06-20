---
name: git-ship
description: Stage, commit, and optionally open PR for task-scope repos — human approves, default no push.
---

# Git Ship（任务范围内提交）

在 **Task scope** 勾选的项目内完成改动后，用本 Skill 走 Review → Ship 流程。

## 四层模型

| 层 | 含义 | UI / CLI |
|----|------|----------|
| Work | Agent 在 scope 内读写 | 左侧 ☑ 项目 |
| Isolate | 并行 run 用 worktree | Parallel + `--isolate` |
| Review | 看 diff、逐 hunk apply | Review / 改动面板 |
| Ship | Stage → Commit（**默认不 push**） | 改动面板 Stage / Commit |

## 流程

1. 确认左侧 **项目 ☑** 与 **主项目** 正确。
2. 打开 **改动** 面板，按仓库查看 `git status` 摘要。
3. 每个仓库：**Stage** → 编辑 commit message → **Commit**。
4. 多仓库：用 **提交全部**（仅 scope 内脏仓库，启发式 message）。
5. 需要 PR 时由用户明确说「创建 PR」再 `gh pr create`；不要自动 push。

## 约束

- 不要 `git push --force`。
- 不要提交 `.env`、密钥文件。
- 没有 staged 改动时不要 `git commit`。
- 多仓库时每个仓库独立 commit，message 写清「为什么」。

## 相关

- [docs/harness/git-workflow.md](../../../docs/harness/git-workflow.md)
- [docs/harness/multi-repo.md](../../../docs/harness/multi-repo.md)
