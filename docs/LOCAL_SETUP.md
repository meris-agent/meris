# 本机环境配置记录

> 适用于 **Windows + Cursor** 开发机。记录扩展安装、Rust 工具链与 `meris-rs` 构建步骤。  
> 更新日期：2026-05-30

## 当前本机状态（已配置）

| 组件 | 状态 | 路径 / 说明 |
|------|------|-------------|
| Python `meris` CLI | ✅ | `%LOCALAPPDATA%\Programs\Python\Python314\Scripts\meris.exe` |
| Cursor 扩展 | ✅ | 目录联接 → 见下方 |
| Rust (rustup) | ✅ | `%USERPROFILE%\.cargo\bin` |
| VS Build Tools 2022 | ✅ | MSVC 链接器（`link.exe`） |
| `meris-rs` release | ✅ | `meris/meris-rs/target/release/meris-rs.exe` |

### Cursor 扩展安装位置

```
C:\Users\yangy\.cursor\extensions\meris-agent-vscode
  └── (联接) → d:\personal\obsidian\AINote\meris\extensions\vscode-meris
```

**生效方式**：在 Cursor 中执行 **Developer: Reload Window**（或重启 Cursor），然后在命令面板搜索 `Meris:`。

### 启用原生 context 压缩（可选）

在用户环境变量或项目 `.env` 中：

```powershell
setx MERIS_NATIVE 1
```

验证：

```powershell
cd d:\personal\obsidian\AINote\meris
meris native status
# available=True, version=meris-rs 0.6.0
```

---

## 一、Cursor / VS Code 扩展

扩展是 CLI 的 IDE 入口，不 bundled Python 运行时。

### 方式 A：目录联接（推荐，改代码即生效）

在 **管理员或普通 PowerShell** 中（路径按你的仓库位置调整）：

```powershell
$src = "d:\personal\obsidian\AINote\meris\extensions\vscode-meris"
$dst = "$env:USERPROFILE\.cursor\extensions\meris-agent-vscode"
if (Test-Path $dst) { Remove-Item $dst -Force -Recurse }
cmd /c mklink /J "$dst" "$src"
```

VS Code 用户将 `$dst` 改为：

```powershell
$dst = "$env:USERPROFILE\.vscode\extensions\meris-agent-vscode"
```

### 方式 B：打包安装

```bash
cd extensions/vscode-meris
npx @vscode/vsce package
# Cursor: Extensions → Install from VSIX
```

### 可用命令

| 命令面板 | 终端等价 |
|----------|----------|
| Meris: Ask | `meris ask "..."` |
| Meris: Plan | `meris plan "..."` |
| Meris: Run Agent | `meris run "..."` |
| Meris: Run (approve) | `meris run "..." --approve` |
| Meris: Doctor | `meris doctor` |
| Meris: Open TUI | `meris tui` |

**前提**：工作区已打开文件夹，且 `meris` 在 PATH 中（`pip install -e .`）。

---

## 二、Rust 工具链与 meris-rs

### 依赖（Windows）

1. **Rust**：`winget install Rustlang.Rustup` 或 [rustup.rs](https://rustup.rs)
2. **MSVC 链接器**：`winget install Microsoft.VisualStudio.2022.BuildTools`  
   安装时需包含 **「使用 C++ 的桌面开发」/ VC Tools**（提供 `link.exe`）

新开终端后确认：

```powershell
rustc --version
cargo --version
```

### 构建

**方式 1 — Python 封装**（日常推荐）：

```powershell
cd d:\personal\obsidian\AINote\meris
meris native build
meris native status
```

**方式 2 — 直接 cargo**（需 MSVC 环境）：

```powershell
# 若 cargo build 报 link.exe not found，先进入 VS 开发者环境：
cmd /c "`"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat`" && cd /d d:\personal\obsidian\AINote\meris\meris-rs && cargo build --release"
```

产物：`meris-rs/target/release/meris-rs.exe`

### 可选：加入 PATH

```powershell
setx PATH "$env:PATH;d:\personal\obsidian\AINote\meris\meris-rs\target\release"
```

不加入 PATH 也可：`meris native status` 会自动发现 `target/release/` 下的二进制。

### 常用 meris-rs 命令

```powershell
meris-rs version
meris-rs context tokens "hello"
meris-rs permissions check --workspace . --tool read_file --args "{}"
meris-rs run doctor    # 委托给 Python meris
```

### MERIS_NATIVE 行为

当 `MERIS_NATIVE=1` 时，Agent 循环中的 **context 压缩** 优先走 Rust 实现（与 Python 逻辑对齐），失败时自动回退 Python。

---

## 三、一键脚本

仓库提供 `scripts/setup-local.ps1`，可重复执行：

```powershell
cd d:\personal\obsidian\AINote\meris
powershell -ExecutionPolicy Bypass -File scripts\setup-local.ps1
```

参数：

- `-SkipRust` — 只装 Cursor 扩展联接
- `-SkipExtension` — 只构建 meris-rs
- `-InstallToolchain` — 尝试 winget 安装 rustup + Build Tools（耗时较长）

---

## 四、Rust 移植路线（摘要）

完整说明见 [RUST_ROADMAP.md](RUST_ROADMAP.md)。

| 阶段 | 内容 | 状态 |
|------|------|------|
| P5-MVP (0.6.0) | context / permissions / settings + CLI | ✅ 本机已构建 |
| P5-1 | 将 permissions 检查默认走 native | 可选 |
| P5-2 | Provider HTTP 客户端（OpenAI compat） | 待做 |
| P5-3 | 内置 tools（read/write/bash） | 待做 |
| P5-4 | 完整 Agent loop，Python 仅作插件层 | 长期 |

---

## 五、故障排查

| 现象 | 处理 |
|------|------|
| 命令面板无 Meris 命令 | Reload Window；检查扩展目录联接是否存在 |
| `meris` 不是内部或外部命令 | `pip install -e .`，确认 Scripts 在 PATH |
| `link.exe not found` | 安装 VS Build Tools + VC Tools，用 vcvars64 再 cargo build |
| `meris native status` → available=False | 运行 `meris native build` |
| 扩展跑起来但 Agent 无响应 | `meris doctor`；检查 API key |

---

## 相关文档

- [RUST_ROADMAP.md](RUST_ROADMAP.md) — Rust 移植阶段规划
- [../meris-rs/README.md](../meris-rs/README.md) — crate 说明
- [../extensions/vscode-meris/README.md](../extensions/vscode-meris/README.md) — 扩展详情
- [../README.md](../README.md) — 项目总览
