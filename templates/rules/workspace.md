# 工作区 cwd

| 任务 | cwd |
|------|-----|
| 改本项目代码、README、测试 | 本项目 **git 仓库根**（含 `pyproject.toml` 或等价标识） |
| 改笔记 / 文档库 | 对应 vault 或文档仓库根 |

在父目录 cwd 运行 agent 时，子目录里的文件路径需带正确前缀，且可能触发 permissions block。
