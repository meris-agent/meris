# Bash 沙箱（Phase E3）

Meris 在 **permissions** 之外增加两层 **sandbox**：

1. **策略层**（全平台）：拦截 cd/find/pwd/ls、`/workspace` 等探索性 bash  
2. **OS 层**（Linux + bubblewrap）：只读挂载 `/`，workspace 可写，可选网络隔离与 `.env` 遮罩

## 配置（`.meris/settings.yaml`）

```yaml
sandbox:
  mode: warn           # off | warn | strict（默认 warn）
  bashTimeoutSec: 120
  osSandbox: auto      # off | auto | require（Linux bubblewrap）
  network: shared      # shared | isolated — isolated 时 bash 无网络
  maskSecrets: true    # bwrap 下用 /dev/null 遮罩 .env 等
  maskPaths: []        # 额外遮罩路径（相对 workspace）
```

| mode | 行为 |
|------|------|
| `off` | 仅 permissions 生效 |
| `warn` | 命中 cd/find/pwd/ls、`/workspace` 时输出 `[sandbox] WARN`，仍执行 |
| `strict` | 同上模式 **直接拒绝** bash |

| osSandbox | 行为 |
|-----------|------|
| `off` | 仅 cwd 锁定 + 策略层 |
| `auto` | Linux 且 PATH 有 `bwrap` 时启用 bubblewrap |
| `require` | 必须有 bwrap，否则 bash 失败 |

| network | 行为（仅 bubblewrap） |
|---------|----------------------|
| `shared` | `--share-net`（默认，便于 git/pytest） |
| `isolated` | `--unshare-net`，bash 无法访问网络 |

默认遮罩文件（存在则 `--ro-bind /dev/null`）：`.env`、`.env.local`、`.env.production` 等。

## 探测

```bash
meris-rs sandbox probe --workspace .
meris doctor    # Windows 另显示 WSL + bwrap 状态
```

## 平台说明

| 平台 | 策略层 | OS 层 |
|------|--------|-------|
| Linux / WSL | ✅ | ✅ bubblewrap |
| Windows 原生 | ✅ cwd | ❌ — `doctor` 提示 WSL + `apt install bubblewrap` |
| macOS | ✅ cwd | ❌ |

安装（Debian/Ubuntu / WSL）：`sudo apt install bubblewrap`

## 相关

- 权限：`.meris/settings.yaml` → `permissions`
- 规则：`.meris/rules/bash-permissions.md`
