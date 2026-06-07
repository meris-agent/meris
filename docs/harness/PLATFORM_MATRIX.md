# 平台沙箱矩阵（Phase G3 · Codex CLI 对照）

Meris 与 [OpenAI Codex CLI](https://github.com/openai/codex) 在不同操作系统上的沙箱能力对照。  
配置 preset 见 [sandbox.md](sandbox.md) · 路线图 [PLAN_PHASE_G.md](../PLAN_PHASE_G.md)。

## Preset 映射（全平台一致）

| Codex `--sandbox` | Meris `sandbox.preset` | 策略层 mode | network | osSandbox |
|-------------------|------------------------|-------------|---------|-----------|
| `read-only` | `read-only` | strict | isolated | auto |
| `workspace-write`（Auto 默认） | `workspace-write` | warn | isolated | auto |
| `danger-full-access` | `danger-full-access` | off | shared | off |

`meris doctor` 会显示 `preset=… (≈ Codex --sandbox …)`。

## 能力矩阵

| 能力 | Codex CLI | Linux 原生 | WSL (Windows) | Windows 原生 | macOS |
|------|-----------|------------|---------------|--------------|-------|
| 策略层（cd/find/pwd/ls 拦截） | ✅ | ✅ | ✅ | ✅ | ✅ |
| cwd 锁定 | ✅ | ✅ | ✅ | ✅ | ✅ |
| bubblewrap OS 沙箱 | ✅ (Linux) | ✅ | ✅ | ❌ | ❌ |
| 网络隔离 (`--unshare-net`) | ✅ | ✅ bwrap | ✅ bwrap | ❌ | ❌ |
| network allowlist | ✅ 代理级 | ✅ 命令级 | ✅ 命令级 | ⚠️ 仅策略 | ⚠️ 仅策略 |
| `.env` 遮罩 | ✅ | ✅ bwrap | ✅ bwrap | ❌ | ❌ |
| macOS Seatbelt | ✅ | — | — | — | ❌ Meris 未实现 |
| Windows 原生沙箱 | ✅ | — | — | ❌ | — |

**说明**

- **策略层**：全平台生效，不依赖 bubblewrap。
- **OS 层**：仅 Linux（含 WSL 内 Linux）且 PATH 有 `bwrap` 时，`osSandbox: auto|require` 才启用。
- **network allowlist**：Meris 为命令级主机名检查 + bwrap `--share-net`，非 Codex 的内核 MITM 代理（见 [sandbox.md](sandbox.md) Phase G2）。

## 推荐运行方式

| 你的环境 | 推荐 | OS 沙箱 |
|----------|------|---------|
| Linux / CI | 直接 `meris run` | bubblewrap（`apt install bubblewrap`） |
| Windows | **WSL2 内**运行 meris | WSL 内 bwrap |
| Windows 仅原生 | 可用，策略层 only | 无 — doctor 提示装 WSL |
| macOS | 可用，策略层 only | 无 Seatbelt — 敏感任务用 Linux/WSL |

### Windows + WSL 快速检查

```powershell
wsl -e sh -lc "command -v bwrap && bwrap --version"
meris doctor   # 查看 WSL sandbox + platform sandbox 行
```

WSL 内安装：`sudo apt install bubblewrap`

## doctor 输出

| 检查项 | 含义 |
|--------|------|
| `sandbox` | mode · preset · Codex 等价 · meris-rs · bwrap/网络 |
| `platform sandbox` | 当前 OS 上策略层 vs OS 层摘要 |
| `WSL sandbox`（仅 win32） | WSL 是否可用 · bwrap 是否在 WSL 内 |

## 与 Codex 仍存在的差距

1. **macOS Seatbelt** — 未实现（G6 可选 spike）
2. **Windows 原生 OS 沙箱** — 推荐 WSL；无 AppContainer 集成
3. **network allowlist** — 命令级，非代理级
4. **安装** — Codex npm/brew vs Meris pip（G5 待发 PyPI）

## 相关

- [sandbox.md](sandbox.md) — 配置与 allowlist
- [PLAN_PHASE_G.md](../PLAN_PHASE_G.md) — G1–G6 里程碑
- [USER_SETUP.md](../USER_SETUP.md) — 用户安装
