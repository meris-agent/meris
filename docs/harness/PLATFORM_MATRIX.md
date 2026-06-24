# 平台沙箱矩阵

Meris 在不同操作系统上的沙箱能力。配置 preset 见 [sandbox.md](sandbox.md)。

## Preset 一览

| Meris `sandbox.preset` | 策略层 mode | network | osSandbox |
|------------------------|-------------|---------|-----------|
| `read-only` | strict | isolated | auto |
| `workspace-write`（默认） | warn | isolated | auto |
| `danger-full-access` | off | shared | off |

显式 `mode` / `network` / `osSandbox` 可覆盖 preset。`meris doctor` 会显示当前 `preset`。

## 能力矩阵

| 能力 | Linux 原生 | WSL (Windows) | Windows 原生 | macOS |
|------|------------|---------------|--------------|-------|
| 策略层（cd/find/pwd/ls 拦截） | ✅ | ✅ | ✅ | ✅ |
| cwd 锁定 | ✅ | ✅ | ✅ | ✅ |
| bubblewrap OS 沙箱 | ✅ | ✅ | ❌ | ❌ |
| 网络隔离 (`--unshare-net`) | ✅ bwrap | ✅ bwrap | ❌ | ❌ |
| network allowlist | ✅ 命令级 | ✅ 命令级 | ⚠️ 仅策略 | ⚠️ hybrid |
| `.env` 遮罩 | ✅ bwrap | ✅ bwrap | ❌ | ✅ Seatbelt |
| macOS Seatbelt | — | — | — | ✅ `sandbox-exec` |

**说明**

- **策略层**：全平台生效，不依赖 bubblewrap。
- **OS 层**：Linux（含 WSL 内 Linux）且 PATH 有 `bwrap` 时，`osSandbox: auto|require` 才启用 bubblewrap。
- **network allowlist**：命令级主机名检查 + bwrap `--share-net` 或 macOS hybrid（见 [sandbox.md](sandbox.md)）。

## 推荐运行方式

| 你的环境 | 推荐 | OS 沙箱 |
|----------|------|---------|
| Linux / CI | 直接 `meris run` | bubblewrap（`apt install bubblewrap`） |
| Windows | **WSL2 内**运行 meris | WSL 内 bwrap |
| Windows 仅原生 | 可用，策略层 only | 无 — doctor 提示装 WSL |
| macOS | 可用 | Seatbelt（`sandbox-exec`）或策略层 only |

### Windows + WSL 快速检查

```powershell
wsl -e sh -lc "command -v bwrap && bwrap --version"
meris doctor   # 查看 WSL sandbox + platform sandbox 行
```

WSL 内安装：`sudo apt install bubblewrap`

## doctor 输出

| 检查项 | 含义 |
|--------|------|
| `sandbox` | mode · preset · meris-rs · bwrap/网络 |
| `platform sandbox` | 当前 OS 上策略层 vs OS 层摘要 |
| `WSL sandbox`（仅 win32） | WSL 是否可用 · bwrap 是否在 WSL 内 |

## 已知平台限制

1. **Windows 原生** — 无 OS 级沙箱；推荐 WSL2 + bubblewrap
2. **network allowlist** — 命令级解析，非内核代理；子进程 / IP 直连不受控
3. **macOS** — Seatbelt 能力见 [SEATBELT_DESIGN.md](SEATBELT_DESIGN.md)

## 相关

- [sandbox.md](sandbox.md) — 配置与 allowlist
- [USER_SETUP.md](../USER_SETUP.md) — 用户安装
