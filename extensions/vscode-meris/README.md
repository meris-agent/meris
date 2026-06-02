# Meris Agent — VS Code / Cursor Extension

Thin wrapper around the `meris` CLI. Requires `meris` on PATH (`pip install -e .` from repo root).

## 安装（Windows + Cursor）

推荐目录联接（改仓库内文件即生效）：

```powershell
$src = "<repo>\extensions\vscode-meris"   # 换成你的 clone 路径
$dst = "$env:USERPROFILE\.cursor\extensions\meris-agent-vscode"
if (Test-Path $dst) { Remove-Item $dst -Force -Recurse }
cmd /c mklink /J "$dst" "$src"
```

**激活**：Cursor → `Developer: Reload Window`

完整步骤：[docs/LOCAL_SETUP.md](../../docs/LOCAL_SETUP.md)

或一键脚本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup-local.ps1 -SkipRust
```

## Commands

| Command Palette | Terminal |
|-----------------|----------|
| Meris: Ask | `meris ask "..."` |
| Meris: Plan | `meris plan "..."` |
| Meris: Run Agent | `meris run "..."` |
| Meris: Run (approve) | `meris run "..." --approve` |
| Meris: Doctor | `meris doctor` |
| Meris: Open TUI | `meris tui` |

Runs in integrated terminal at workspace root.

## VS Code（非 Cursor）

将 `$dst` 改为 `$env:USERPROFILE\.vscode\extensions\meris-agent-vscode`。

## Package VSIX（可选）

```bash
cd extensions/vscode-meris
npx @vscode/vsce package
```
