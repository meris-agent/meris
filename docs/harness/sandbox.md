# Bash 沙箱（Phase E3）

Meris 在 **permissions** 之外增加两层 **sandbox**：

1. **策略层**（全平台）：拦截 cd/find/pwd/ls、`/workspace` 等探索性 bash  
2. **OS 层**（Linux + bubblewrap）：只读挂载 `/`，workspace 可写，隔离宿主机其它路径

## 配置（`.meris/settings.yaml`）

```yaml
sandbox:
  mode: warn           # off | warn | strict（默认 warn）
  bashTimeoutSec: 120
  osSandbox: auto      # off | auto | require（Linux bubblewrap，默认 auto）
```

| mode | 行为 |
|------|------|
| `off` | 仅 permissions 生效 |
| `warn` | 命中 cd/find/pwd/ls、`/workspace` 时输出 `[sandbox] WARN`，仍执行 |
| `strict` | 同上模式 **直接拒绝** bash，提示用 glob/read_file/pytest |

| osSandbox | 行为 |
|-----------|------|
| `off` | 仅 cwd 锁定 + 策略层（当前 Windows/macOS 行为） |
| `auto` | Linux 且 PATH 有 `bwrap` 时启用 bubblewrap |
| `require` | Linux 必须有 bwrap，否则 bash 失败 |

`meris doctor` 会显示 `sandbox.mode`、超时与 bubblewrap 状态。

## 探测

```bash
meris-rs sandbox probe --workspace .
# 或 Python：meris doctor
```

## 被拦截的模式（warn / strict）

- `cd ...`（含 `&& cd`、`; cd`）
- `find`、`pwd`、行首/`;`/`&&` 后的 `ls`
- 路径 `/workspace`（容器假路径）

允许示例：`pytest tests/ -m "not integration" -q`、`git status`、`python -m pytest ...`（仍需通过 permissions allow 列表）。

## 平台说明

| 平台 | 策略层 | OS 层（bubblewrap） |
|------|--------|---------------------|
| Linux / WSL | ✅ | ✅ `osSandbox: auto`（需 `bubblewrap` 包） |
| Windows | ✅ cwd 锁定 | ❌ 推荐 WSL；文档声明无 OS 沙箱 |
| macOS | ✅ cwd 锁定 | ❌ 暂无 bwrap（可 `osSandbox: off`） |

bubblewrap 实现：`--ro-bind / /` + `--bind $workspace $workspace` + `--tmpfs /tmp` + `--share-net`（保留网络以便 API/git）。

安装（Debian/Ubuntu）：`sudo apt install bubblewrap`

## 相关

- 权限 allow/deny：`.meris/settings.yaml` → `permissions`
- Ratchet 规则：`.meris/rules/bash-permissions.md`
