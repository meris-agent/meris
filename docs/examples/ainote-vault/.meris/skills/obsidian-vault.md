# Skill: Obsidian Vault 写作

## wikilink

- 链接已有笔记：`[[笔记标题]]`
- 带别名：`[[Articles/MyCodingAgent-架构设计|架构设计]]`
- 新建笔记前先用 `glob` / `grep` 查是否已有同名

## Frontmatter 模板

```yaml
---
title: 标题
created: YYYY-MM-DD
tags:
  - AI
related:
  - "[[相关笔记]]"
---
```

## 与 Meris 的关系

- Meris Agent 源码在 `meris/` 子目录，有独立 `AGENTS.md`
- 在 vault 根 cwd 下工作时，只编辑 `Articles/` 等 Markdown，不要改 `meris/` 代码
