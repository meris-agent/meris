---
inject: always
---

# 路径规范（Meris 仓库 cwd）

- Python **包**在 `meris/` 目录：`meris/cli.py`、`meris/harness/`、`meris/tools/`
- 本仓库 **根目录**文档：`README.md`、`PROGRESS.md`、`AGENTS.md`（不要写成 `meris/README.md`）
- import 一律 `from meris.xxx import ...`
- 仅在 **vault 根** cwd、且 Meris 是子目录时，才用 `meris/README.md` 这类带前缀路径
