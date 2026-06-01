# AGENTS.md — AINote Obsidian Vault

## 项目说明

- **类型**：Obsidian 知识库（Markdown + wikilink）
- **主要内容**：`Articles/` 技术文章、Meris 架构笔记、AI/Coding 主题
- **子项目**：`meris/` 为 Meris Agent 源码（**本 vault 任务默认不改此目录**）
- **编辑器配置**：`.obsidian/` 勿手动改 JSON，除非用户明确要求

## Markdown 约定

- 保留 YAML frontmatter（`title`、`tags`、`related`、`aliases`）
- wikilink 格式：`[[笔记标题]]` 或 `[[路径/笔记|显示名]]`
- 中文为主；代码块注明语言
- 不批量重命名 `Articles/` 下已有文件

## 禁止操作

- 不要修改 `meris/` 下 Python/Rust 源码（代码任务请 cd 到 meris 目录）
- 不要删除或覆盖 `.obsidian/` 配置
- 不要自动 `git push`（vault 可能未纳入 git）
- 不要改动 `**/.meris/sessions/**` 会话文件

## 会话约定

- 新会话先读 vault 根目录 `PROGRESS.md`
- 长任务更新 `PROGRESS.md` 断点

## 完成定义 (Definition of Done)

笔记类任务完成 = 以下全部满足：

- 修改的文件 Markdown 可正常渲染（frontmatter 合法）
- 若改了 wikilink，相关链接格式正确
- 未触碰 `meris/` 与 `.obsidian/`（除非任务明确要求）
