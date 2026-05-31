# Meris Agent — VS Code / Cursor Extension

Thin wrapper around the `meris` CLI. Requires `meris` on PATH (`pip install -e .` from repo root).

## 本机安装记录（Windows + Cursor）

已配置目录联接（改仓库内文件即生效）：

```
%USERPROFILE%\.cursor\extensions\meris-agent-vscode
  → d:\personal\obsidian\AINote\meris\extensions\vscode-meris
```

**激活**：Cursor → `Developer: Reload Window`

完整步骤与故障排查：[docs/LOCAL_SETUP.md](../../docs/LOCAL_SETUP.md)

## 重新安装

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup-local.ps1 -SkipRust
```

或手动：

```powershell
$src = "d:\personal\obsidian\AINote\meris\extensions\vscode-meris"
$dst = "$env:USERPROFILE\.cursor\extensions\meris-agent-vscode"
cmd /c mklink /J "$dst" "$src"
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

将 `$dst` 改为 `%USERPROFILE%\.vscode\extensions\meris-agent-vscode`。

## Package VSIX（可选）

```bash
cd extensions/vscode-meris
npx @vscode/vsce package
```
