# Meris 7 天 Dogfood 清单

> 目标：用 Meris 做真实小事，每次失败改 Harness（Ratchet），而不是只改 Agent 输出。  
> **项目 1（代码）**：`D:\personal\obsidian\AINote\meris`  
> **项目 2（笔记库）**：`D:\personal\obsidian\AINote`（Obsidian vault，见 [examples/ainote-vault](examples/ainote-vault/)）

## 每天开始前（2 分钟）

```powershell
cd D:\personal\obsidian\AINote\meris
meris doctor
pytest tests/ -m "not integration" -q
```

---

## Day 1 — 熟悉三模式 + TUI

| 项 | 内容 |
|----|------|
| **任务** | `meris ask "meris 的 agent loop 在哪个文件？"` |
| **任务** | `meris tui --cwd . --mode ask`，输入「列出 builtin 工具有哪些」 |
| **验收** | 日志出现 `>>>` 且有回答；TUI Enter / Ctrl+Enter 能发送 |
| **若失败改** | 无输出 → 查 API / TUI；乱改文件 → `.meris/settings.json` permissions |

---

## Day 2 — Plan → 只写计划不改代码

| 项 | 内容 |
|----|------|
| **任务** | `meris plan "为 meris session 增加 prune 子命令，3 条 checkbox"` |
| **验收** | 生成 `.meris/plan/tasks.md`，打开确认结构合理 |
| **若失败改** | 计划太虚 → `AGENTS.md` 补充「plan 输出格式」；写错目录 → `meris/harness/plan.py` 或 AGENTS |

---

## Day 3 — Run + approve（修 Meris 自身）

| 项 | 内容 |
|----|------|
| **任务** | `meris run --approve "在 README Quick start 加一行 meris version 示例"` |
| **验收** | README 有改动；`pytest -m "not integration"` 仍绿 |
| **若失败改** | 没跑测试 → `AGENTS.md` DoD；乱 commit → 加 permission deny `git commit` 或 hook |

---

## Day 4 — Benchmark 量化

| 项 | 内容 |
|----|------|
| **任务** | `meris benchmark list` → `meris benchmark run` |
| **验收** | 记录通过率（expect 命中数 / 任务数）到 `PROGRESS.md` |
| **若失败改** | 某类任务总失败 → 改 `scripts/benchmark/tasks.json` 或 AGENTS 对应章节 |

---

## Day 5 — Session 中断与恢复

| 项 | 内容 |
|----|------|
| **任务** | `meris run "阅读 meris/harness/sessions.py 并总结 session 字段"`，中途 Ctrl+C |
| **任务** | `meris session list` → `meris session resume <id>` 或 TUI 左侧 Enter |
| **验收** | 能续跑或至少 PROGRESS / session JSON 有断点 |
| **若失败改** | 失忆 → `AGENTS.md`「会话约定」；TUI 列表空 → 查 `.meris/sessions/` |

---

## Day 6 — 第二项目（Obsidian vault）

| 项 | 内容 |
|----|------|
| **cwd** | `cd D:\personal\obsidian\AINote` |
| **任务** | `meris ask "Articles 里有哪些与 Coding Agent 相关的笔记？只读"` |
| **任务** | `meris plan "更新 MyCodingAgent 架构设计.md 的 Phase 进度表"` |
| **验收** | 只碰 `Articles/`、`*.md`；不删 `.obsidian/` |
| **若失败改** | 改了 `meris/` 代码 → vault 的 `.meris/settings.json` `blockedPaths`；wikilink 格式错 → vault `AGENTS.md` |

---

## Day 7 — Ratchet 复盘 + 定日常习惯

| 项 | 内容 |
|----|------|
| **任务** | 回顾 7 天：列出 Agent 犯过的 3 类错误，各改一处 Harness |
| **任务** | 写进两个项目的 `PROGRESS.md`；meris 仓库 commit |
| **验收** | 能回答：Meris 比裸 Cursor Chat 多给了什么（permissions / DoD / session / plan） |
| **选定日常入口** | 建议：**终端 `meris run --approve`** 为主，扩展为辅 |

---

## Ratchet 速查

| 失败类型 | 改哪里 |
|----------|--------|
| 不知道规则 | `AGENTS.md` |
| 知道但违反 | `.meris/settings.json` hooks / deny |
| 缺领域知识 | `.meris/skills/*.md` |
| 跨会话失忆 | `PROGRESS.md` + session |
| 改完没验证 | `AGENTS.md` DoD sensors |

---

## 7 天后可选下一步

- [ ] GitHub Release `v0.8.x` + 附 `meris-rs.exe`
- [ ] PyPI 发布 `meris-agent`
- [ ] `MERIS_NATIVE=1` 默认开启（P5-1）
- [ ] 第三个常驻 repo（你的业务项目）`meris init-harness`
