# 项目进度

## 已完成
- [x] P1–P4 + 阶段 A（doctor、permissions、plan、interrupt、git_commit、CI）
- [x] **阶段 B（v0.4.0）** — spec、session、hooks、benchmark
- [x] **阶段 C（v0.5.0）** — token 压缩、Anthropic、MCP extras、TUI 面板
- [x] **阶段 D（v0.6.0）**
  - [x] D1 `meris-rs` + `meris native`
  - [x] D2 `BRAND.md`
  - [x] D3 VS Code/Cursor 扩展
  - [x] **本机配置**：Cursor 扩展联接 + Rust/MSVC + `meris-rs` release（见 [docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md)）
- [x] **品牌更名 Meris（v0.7.0）** — 自 Forge 全面改名
- [x] **移除 Forge 兼容层（v0.8.0）** — 仅 `meris` CLI、`.meris/`、`MERIS_*`

## 进行中
- [ ] Benchmark dogfood（需有效 API）
- [ ] meris-rs 全量 Agent loop 移植（P5 后续，非 0.6.0 范围）

## 阶段 D 命令
```bash
# Rust 核心
meris native status
meris native build
set MERIS_NATIVE=1
meris-rs context compress --max-tokens 3000 < msgs.json

# IDE（见 extensions/vscode-meris/README.md）
# Command Palette → Meris: Run Agent
```

## 阶段 C 命令
```bash
set MERIS_PROVIDER=anthropic
pip install meris-agent[anthropic]
meris tui
meris mcp list
```

## 阶段 B 命令
```bash
meris spec init "my feature"
meris benchmark run
meris session prune --keep 10
```
