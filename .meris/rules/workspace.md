# 工作区 cwd

| 任务 | cwd |
|------|-----|
| 改 Meris 代码、README、跑 pytest | Meris **git 仓库根**（clone 后的目录，含 `pyproject.toml`） |
| 改 Obsidian 笔记 `Articles/` | **vault 根**（Meris 的父目录或独立笔记库） |

Meris 仓库作为 vault 子目录时：在 vault 根跑 `meris run` 改 README 会变成 `meris/README.md` 且可能被 block。**改 Meris 请先 `cd` 到 Meris 仓库根。**
