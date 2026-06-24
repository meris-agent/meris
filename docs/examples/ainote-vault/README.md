# 示例：Markdown 笔记库 + 嵌套代码仓库

若你有一个**外层文档/笔记根目录**，内嵌独立的 **git 代码仓库**，可复制本模板到外层根目录作为 Harness 起点（Obsidian 可选）。

## 典型布局

```
your-vault/          ← vault 根 cwd（改笔记）
├── Articles/
├── .meris/          ← 从本模板复制
├── AGENTS.md
└── meris/           ← Meris git 仓库 clone（改代码时 cd 进此目录）
    ├── README.md
    └── meris/       ← Python 包
```

## 一键初始化

```powershell
cd <your-vault>
meris init-harness .
# 再按需覆盖 AGENTS.md / settings.json（本目录为推荐模板）
```

## 本目录文件

| 文件 | 说明 |
|------|------|
| `AGENTS.md` | Obsidian / Markdown 约定 |
| `PROGRESS.md` | vault 级进度 |
| `.meris/settings.json` | 只读为主，禁止改 Meris 源码目录 |
| `.meris/skills/obsidian-vault.md` | wikilink、frontmatter 技能 |
