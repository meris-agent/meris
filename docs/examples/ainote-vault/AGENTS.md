# AGENTS.md — Obsidian Vault（示例）

## 项目说明

- **类型**：Obsidian 知识库（Markdown + wikilink）
- **主要内容**：`Articles/` 等技术文章
- **子目录 `meris/`**（若存在）：Meris Agent git 仓库（Python 包在 `meris/meris/`）

## 两个工作区（重要）

| 任务 | 正确 cwd |
|------|----------|
| 改 Meris 代码 / README / pytest | Meris git 仓库根（例如 `<vault>/meris`） |
| 改 Obsidian 笔记 | vault 根 |

## 禁止操作

- 不要修改 `meris/meris/`、`meris/meris-rs/`、`meris/tests/`（若 vault 内含 Meris 子目录）
- 不要改 `.obsidian/`
