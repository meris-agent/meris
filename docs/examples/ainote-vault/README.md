# 示例：Obsidian Vault 作为第二常驻项目

Meris 仓库内自带 Harness；若你还有 Obsidian 笔记库，可复制本目录模板到 **vault 根**。

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
