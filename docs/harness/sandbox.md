# Bash 沙箱（Phase E3）

Meris 在 **permissions** 之外增加一层 **sandbox**，拦截探索性 / 越界 bash（与 `.meris/rules/bash-permissions.md` 一致）。

## 配置（`.meris/settings.yaml`）

```yaml
sandbox:
  mode: warn      # off | warn | strict（默认 warn）
  bashTimeoutSec: 120
```

| mode | 行为 |
|------|------|
| `off` | 仅 permissions 生效 |
| `warn` | 命中 cd/find/pwd/ls、`/workspace` 时输出 `[sandbox] WARN`，仍执行 |
| `strict` | 同上模式 **直接拒绝** bash，提示用 glob/read_file/pytest |

`meris doctor` 会显示当前 `sandbox.mode` 与超时。

## 被拦截的模式（warn / strict）

- `cd ...`（含 `&& cd`、`; cd`）
- `find`、`pwd`、行首/`;`/`&&` 后的 `ls`
- 路径 `/workspace`（容器假路径）

允许示例：`pytest tests/ -m "not integration" -q`、`git status`、`python -m pytest ...`（仍需通过 permissions allow 列表）。

## 平台说明

| 平台 | 现状 |
|------|------|
| 全平台 | Python loop：cwd 锁定 workspace、可配置 bash 超时 |
| 全平台 + `MERIS_NATIVE=1` | `meris-rs sandbox run/check` — bash 执行与策略检查走 Rust |
| Linux / WSL | 后续：bubblewrap 级隔离（E3.3+） |
| Windows | 推荐 WSL 跑 agent；原生 Windows 暂无 OS 级沙箱（E3.4） |

OS 级隔离与 network proxy 见 [PLAN_PHASE_E.md](../PLAN_PHASE_E.md) E3.3+。

## 相关

- 权限 allow/deny：`.meris/settings.yaml` → `permissions`
- Ratchet 规则：`.meris/rules/bash-permissions.md`
