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

## Agent Window（类 Cursor 可视化）

命令面板 → **Meris: Open Agent Window**（编辑器旁面板）

或点击 Activity Bar **Meris** 图标 → 侧边栏 **Agent** 视图（常驻）

- **设置**：右上角 **⚙** → 主题预设（深色/午夜/柔和/浅色）+ 自定义背景色
- **草稿持久化**：任务输入 / mode / approve 勾选自动恢复
- **错误横幅**：进程失败时顶部显示 stderr
- **左栏 Sessions**：读取 `.meris/sessions/`，点击可恢复（`running` / `cancelled` / `error`）
- **可折叠 Tool 卡片**：`args` + `output` 分区，`tool_end` 后自动折叠
- **Approve 模式**：勾选 approve → 内联 **Approve / Deny** 条（`approval_request` + 文件通道）
- assistant 回复：**流式 token**（OpenAI 兼容 API）+ 流式中 **Markdown 轻渲染**
- **reasoning** 金色折叠条（模型推理链，如 DeepSeek `reasoning_content`）
- **thinking** 紫色折叠条（上下文压缩、模型路由）
- **diff 语法高亮**（绿/红行）+ **file_change** 可折叠 diff / Open in editor
- 后台运行 `meris <mode> --event-stream` 或 `meris session resume --event-stream`
- 实时渲染 JSONL 事件：assistant 文本、tool 调用、sensor、done
- **Stop** 终止当前进程；**Ctrl+Enter** 提交任务

规划与后续阶段：[docs/PLAN_AGENT_WINDOW.md](../../docs/PLAN_AGENT_WINDOW.md)

## 独立 Web UI（Path B）

不依赖 IDE 时，在仓库根目录：

```bash
meris ui
# 浏览器打开 http://127.0.0.1:8765/
```

复用同一套 `agent.js` / `agent.css`，通过 SSE 消费 JSONL 事件。

## Commands

| Command Palette | Terminal |
|-----------------|----------|
| Meris: Open Agent Window | Webview 面板（推荐） |
| Meris: Ask | `meris ask "..."` |
| Meris: Plan | `meris plan "..."` |
| Meris: Run Agent | `meris run "..."` |
| Meris: Run (approve) | `meris run "..." --approve` |
| Meris: Doctor | `meris doctor` |
| Meris: Open TUI | `meris tui` |

终端命令仍在集成终端于 workspace 根目录执行。

## VS Code（非 Cursor）

将 `$dst` 改为 `$env:USERPROFILE\.vscode\extensions\meris-agent-vscode`。

## Package VSIX（可选）

```bash
cd extensions/vscode-meris
npx @vscode/vsce package
```
