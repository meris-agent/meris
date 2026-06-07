# Bash 沙箱（Phase E3 · Phase G1 Codex preset · Phase G2 network allowlist）

Meris 在 **permissions** 之外增加两层 **sandbox**：

1. **策略层**（全平台）：拦截 cd/find/pwd/ls、`/workspace` 等探索性 bash  
2. **OS 层**（Linux + bubblewrap）：只读挂载 `/`，workspace 可写，可选网络隔离与 `.env` 遮罩

## Codex CLI 对照（Phase G1）

| OpenAI Codex `--sandbox` | Meris `sandbox.preset` |
|--------------------------|------------------------|
| read-only | `read-only` |
| workspace-write（Auto 默认） | `workspace-write` |
| danger-full-access | `danger-full-access` |

显式 `mode` / `network` / `osSandbox` **覆盖** preset。详见 [PLAN_PHASE_G.md](../PLAN_PHASE_G.md)。

## 配置（`.meris/settings.yaml`）

```yaml
sandbox:
  preset: workspace-write   # 默认，对标 Codex Auto
  mode: warn                # off | warn | strict
  bashTimeoutSec: 120
  osSandbox: auto           # off | auto | require（Linux bubblewrap）
  network: isolated         # shared | isolated — preset 默认 isolated
  networkAllowlist: []      # 非空 → allowlist 模式（见下）
  maskSecrets: true
  maskPaths: []
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
| `shared` | `--share-net`（需 git/curl 时显式开启或 danger preset） |
| `isolated` | `--unshare-net`，bash 无法访问网络（**workspace-write 默认**） |
| `allowlist` | 显式 allowlist 模式；或 `isolated` + 非空 `networkAllowlist` |

## Phase G2 — network allowlist

Codex CLI 可在沙箱内按域名放行网络。Meris 采用 **命令级检查 + bwrap share-net**（非内核 MITM 代理）：

```yaml
sandbox:
  network: isolated
  networkAllowlist:
    - api.deepseek.com
    - "*.github.com"
    - pypi.org
```

| 条件 | 行为 |
|------|------|
| `networkAllowlist` 非空且 `network: isolated` | 有效模式 = `allowlist`；bwrap 使用 `--share-net` |
| `network: allowlist` | 同上，需非空 allowlist |
| 命令含 curl/git/ssh/pip 等 | 解析 URL/主机名，必须在 allowlist 内 |
| `strict` 模式 | 违规 **拒绝** bash |
| `warn` 模式 | 输出 `[sandbox] WARN`，仍执行 |

支持 glob：`*.github.com` 匹配 `api.github.com` 与 `github.com`。

**限制**：仅检查 bash 命令字符串中的可解析主机名；子进程、IP 直连、未列出的工具不受控。对标 Codex 的完整网络代理仍有差距。

默认遮罩文件（存在则 `--ro-bind /dev/null`）：`.env`、`.env.local`、`.env.production` 等。

## 探测

```bash
meris-rs sandbox probe --workspace .
meris doctor    # Windows 另显示 WSL + bwrap 状态
```

## 平台说明

详见 **[PLATFORM_MATRIX.md](PLATFORM_MATRIX.md)**（Phase G3 · Codex 对照）。

| 平台 | 策略层 | OS 层 |
|------|--------|-------|
| Linux / WSL | ✅ | ✅ bubblewrap |
| Windows 原生 | ✅ cwd | ❌ — `doctor` 提示 WSL + `apt install bubblewrap` |
| macOS | ✅ cwd | ❌ — Codex Seatbelt via `sandbox-exec` (G6.2) |

安装（Debian/Ubuntu / WSL）：`sudo apt install bubblewrap`

## Phase G6.2 — macOS Seatbelt

Linux 以外，macOS 通过 `/usr/bin/sandbox-exec` 执行 bash（`osSandbox: auto|require`）：

| preset | Seatbelt |
|--------|----------|
| `read-only` | 无 workspace 写权限 |
| `workspace-write` | workspace + `/private/tmp` 可写 |
| `danger-full-access` | `osSandbox: off`，不启用 |

`network: isolated` 时在 SBPL 中加入 `(deny network*)`。详见 [G6_MACOS_SANDBOX.md](../spikes/G6_MACOS_SANDBOX.md)。

## 相关

- 权限：`.meris/settings.yaml` → `permissions`
- 规则：`.meris/rules/bash-permissions.md`
