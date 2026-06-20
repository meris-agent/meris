# Git workflow — Agent Window

四层：**Work**（scope 写入）→ **Isolate**（worktree）→ **Review**（diff）→ **Ship**（commit，人工确认，默认不 push）。

## UI 映射

| 控件 | 含义 |
|------|------|
| 主项目 | `cwd`：shell、pytest、`meris run` 默认根 |
| 项目 ☑ | Task scope：Agent 读写边界 |
| 文件树 | 仅 scope 内项目 |
| **改动** | 各 scope 仓库 `git status` 摘要 |
| Stage / Commit | 单仓库暂存与提交 |
| 提交全部 | scope 内全部脏仓库 Stage + Commit（启发式 message） |
| Parallel **隔离 worktree** | `meris parallel … --isolate`（run 模式） |

## API

- `GET /api/git/summary?roots[]=…` — 摘要 + `scopeCommits`
- `/api/cmd`：`getGitSummary` · `gitStage` · `gitCommit` · `gitSuggestMessage` · `gitShipScope`

## 持久化

- `~/.meris/ui/git-scope-log.json` — 最近 scope 内提交记录（G4）

## Skill

安装模板：`templates/skills/git-ship.md` → 项目 `.meris/skills/` 或全局 skills。

## 实现

- `meris/harness/git_summary.py` — status 解析、stage、commit、suggest
- `extensions/vscode-meris/media/git-ui.js` — 左栏改动面板
