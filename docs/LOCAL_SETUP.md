# 本机环境配置

> 适用于 **Windows + VS Code** 开发机：扩展安装、Rust 工具链与 `meris-rs` 构建。  
> 路径请按你的 clone 位置替换 `<repo>`（Meris git 仓库根目录）。

## 前置检查

| 组件 | 说明 |
|------|------|
| Python `meris` CLI | `pip install -e .` 后 `meris version` |
| VS Code 扩展 | 目录联接或 VSIX，见下方 |
| Rust (rustup) | 可选，用于 `meris-rs` |
| VS Build Tools 2022 | Windows 上 cargo 链接需要 MSVC |

### 启用原生 context 压缩（可选）

```powershell
setx MERIS_NATIVE 1
```

验证：

```powershell
cd <repo>
meris native status
```

---

## 一、VS Code 扩展

扩展是 CLI 的 IDE 入口，不 bundled Python 运行时。

### 方式 A：目录联接（推荐，改代码即生效）

在 PowerShell 中（将 `<repo>` 换成你的仓库路径）：

```powershell
$src = "<repo>\extensions\vscode-meris"
$dst = "$env:USERPROFILE\.vscode\extensions\meris-agent-vscode"
if (Test-Path $dst) { Remove-Item $dst -Force -Recurse }
cmd /c mklink /J "$dst" "$src"
```

若编辑器使用其他扩展目录，将 `$dst` 改为该编辑器下的 `extensions/meris-agent-vscode`。

**生效**：`Developer: Reload Window`，命令面板搜索 `Meris:`。

### 方式 B：打包安装

```bash
cd extensions/vscode-meris
npx @vscode/vsce package
# VS Code: Extensions → Install from VSIX
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

**前提**：工作区已打开文件夹，且 `meris` 在 PATH 中。

---

## 二、Rust 工具链与 meris-rs

### 依赖（Windows）

1. **Rust**：`winget install Rustlang.Rustup` 或 [rustup.rs](https://rustup.rs)
2. **MSVC 链接器**：`winget install Microsoft.VisualStudio.2022.BuildTools`  
   安装时需包含 **「使用 C++ 的桌面开发」/ VC Tools**

确认：

```powershell
rustc --version
cargo --version
```

### 构建

**方式 1 — Python 封装**（日常推荐）：

```powershell
cd <repo>
meris native build
meris native status
```

**方式 2 — 直接 cargo**（需 MSVC 环境）：

```powershell
cd <repo>\meris-rs
cargo build --release
```

若 `link.exe not found`，先进入 VS 开发者环境再 build。

产物：`meris-rs/target/release/meris-rs.exe`（已在 `.gitignore`，需本机构建）

### 常用 meris-rs 命令

```powershell
meris-rs version
meris-rs context tokens "hello"
meris-rs permissions check --workspace . --tool read_file --args "{}"
meris-rs run doctor
```

当 `MERIS_NATIVE=1` 时，context 压缩优先走 Rust，失败时回退 Python。

---

## 三、一键脚本

```powershell
cd <repo>
powershell -ExecutionPolicy Bypass -File scripts\setup-local.ps1
```

参数：

- `-SkipRust` — 只装 VS Code 扩展联接
- `-SkipExtension` — 只构建 meris-rs
- `-InstallToolchain` — 尝试 winget 安装 rustup + Build Tools

---

## 四、故障排查

| 现象 | 处理 |
|------|------|
| 命令面板无 Meris 命令 | Reload Window；检查扩展目录联接 |
| `meris` 不是内部或外部命令 | `pip install -e .`，确认 Scripts 在 PATH |
| `link.exe not found` | 安装 VS Build Tools + VC Tools |
| `meris native status` → available=False | 运行 `meris native build` |
| Agent 无响应 | `meris doctor`；检查 API key |

---

## 相关文档

- [NATIVE_BINARY.md](NATIVE_BINARY.md) — Rust 二进制与 CI 安装
- [../meris-rs/README.md](../meris-rs/README.md) — crate 说明
- [../extensions/vscode-meris/README.md](../extensions/vscode-meris/README.md) — 扩展详情
- [../README.md](../README.md) — 项目总览
