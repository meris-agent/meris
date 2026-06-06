# 仓库架构（Meris 本仓库）

## 包与入口

| 路径 | 说明 |
|------|------|
| `meris/cli.py` | CLI 入口（Typer） |
| `meris/loop.py` | Agent 主循环 |
| `meris/harness/` | Harness：settings、guides、sessions、ratchet |
| `meris/tools/` | 内置工具 + MCP |
| `meris/provider/` | LLM 多厂商与路由 |
| `meris-rs/` | 可选 Rust 核心（context、permissions） |

## 根目录文档

| 路径 | 说明 |
|------|------|
| `README.md` | 对外说明（**cwd 在本仓库时不要用 `meris/README.md`**） |
| `AGENTS.md` | Agent 地图（本目录的索引） |
| `PROGRESS.md` | 跨会话进度 |
| `VISION.md` / `ROADMAP.md` | 产品宗旨与路线 |

## 路径与 import

- Python 源码一律在 `meris/` 包下。
- import：`from meris.xxx import ...`（不要用已废弃的包名或父目录假路径）。
- 改 Obsidian vault 笔记时 cwd 在 vault 根，见 `.meris/rules/workspace.md`。

## 扩展 CLI

1. 在 `meris/cli.py` 或子 `Typer` 注册命令  
2. 业务逻辑放 `meris/harness/` 或对应模块  
3. 测试放 `tests/test_*.py`  
4. 用户文档更新 `README.md` 或 `docs/`
