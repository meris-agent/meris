# Bash 沙箱（Phase E3）

Meris 在 **permissions** 之外增加两层 **sandbox**：

1. **策略层**（全平台）：拦截 cd/find/pwd/ls 等探索性 bash  
2. **OS 层**（Linux + bubblewrap）：只读 `/`，workspace 可写

```yaml
sandbox:
  mode: warn
  bashTimeoutSec: 120
  osSandbox: auto   # off | auto | require
```

| osSandbox | 行为 |
|-----------|------|
| `auto` | Linux 有 `bwrap` 时启用 |
| `require` | 必须有 bwrap |
| `off` | 仅 cwd + 策略层 |

Linux：`sudo apt install bubblewrap` · `meris-rs sandbox probe --workspace .`

详见仓库 [docs/harness/sandbox.md](../../docs/harness/sandbox.md)。
