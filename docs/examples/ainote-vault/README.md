# 第二常驻项目：Obsidian Vault（AINote）

## 为什么选它

| 项目 | 路径 | 用途 |
|------|------|------|
| **Meris（代码）** | `D:\personal\obsidian\AINote\meris` | Agent 开发、pytest DoD |
| **AINote（笔记）** | `D:\personal\obsidian\AINote` | 架构文档、Articles、Obsidian 知识库 |

Meris 子目录有自己的 Harness；vault 根目录单独一套，避免改笔记时误伤 Python 代码。

## 一键初始化（已生成可跳过）

```powershell
cd D:\personal\obsidian\AINote
meris init-harness .
# 再按需覆盖 AGENTS.md / settings.json（本目录为推荐模板）
```

## 本目录文件

| 文件 | 说明 |
|------|------|
| `AGENTS.md` | Obsidian / Markdown 约定 |
| `PROGRESS.md` | vault 级进度 |
| `.meris/settings.json` | 只读为主，禁止改 `meris/` 源码 |
| `.meris/skills/obsidian-vault.md` | wikilink、frontmatter 技能 |

复制到 vault 根目录即可，或对照修改已有文件。
