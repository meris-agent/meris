---
inject: always
---

# 路径规范（Meris 仓库 cwd）

- Python **包**在 `meris/` 目录：`meris/cli.py`、`meris/harness/`、`meris/tools/`
- 本仓库 **根目录**文档：`README.md`、`PROGRESS.md`、`AGENTS.md`（不要写成 `meris/README.md`）
- import 一律 `from meris.xxx import ...`
- 仅在 **vault 根** cwd、且 Meris 是子目录时，才用 `meris/README.md` 这类带前缀路径

<!-- ratchet:L-path -->

## Ratchet (auto)

- 仓库根文档用 `README.md`，不要写成 `meris/README.md`（除非 cwd 在父目录且项目是子文件夹）。
- 不要使用与本仓库布局不符的路径前缀（以 AGENTS.md 为准）。

<!-- ratchet:L-path-answer -->

## 路径问答（单行）

- benchmark / ask 问「根 README 路径」时：**只答一行** `README.md`。
- **不要**写「不是 `meris/README.md`」等对比句（输出含该子串会被 benchmark reject）。
