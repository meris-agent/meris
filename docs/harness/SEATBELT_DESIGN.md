# Meris macOS Seatbelt 设计

> Meris 用 **preset 驱动的程序化策略** 在运行时生成 Seatbelt 规则（`meris-rs/seatbelt_policy.rs`）。

## 设计原则

| 原则 | Meris 做法 |
|------|------------|
| 策略来源 | `meris-rs seatbelt_policy.rs` 运行时生成 SBPL |
| 与 preset 对齐 | `read-only` / `workspace-write` 直接映射 profile |
| 读权限 | **分层 allowlist**（系统根 + workspace） |
| 网络 | **三层**：isolated 拒绝 / allowlist 混合 / shared 放行 |
| 秘密遮罩 | 与 Linux `maskSecrets` 同一 `collect_mask_paths` |

## Profile 映射

| `sandbox.preset` | Meris profile | 文件读 | 文件写 |
|------------------|---------------|--------|--------|
| `read-only` | `meris-read-only` | 系统根 + workspace | 仅 `/private/tmp`、`/var/folders` |
| `workspace-write` | `meris-workspace-write` | 同上 | workspace + temp |
| `danger-full-access` | （不启用 Seatbelt） | — | — |

系统读根（可维护列表）：`/usr` `/bin` `/sbin` `/System` `/Library` `/private/etc` `/private/var/db` `/opt/homebrew`

**刻意不做** `(allow file-read*)` 全局放行 — 便于审计与收紧。

## 网络（混合模型）

| `network` 有效模式 | Seatbelt | 策略层 G2 |
|--------------------|----------|-----------|
| `isolated` | `(deny network*)` | — |
| `allowlist` | `(allow network-outbound)` | 命令级 host 检查 |
| `shared` | `(allow network-outbound)` | — |

allowlist 下 OS 允许出站，**G2 命令解析仍拦截未授权主机** — Meris 双轨 enforcement。

## 单一数据源

```bash
meris-rs sandbox policy --workspace .   # JSON: profile, policy, params
meris-rs sandbox probe --workspace .    # wouldUseSeatbelt, seatbeltProfile
```

Python `build_seatbelt_policy()` 只调用 meris-rs，不维护第二份 SBPL。

## 验收

```bash
# macOS
meris-rs sandbox policy --workspace . | jq .profile
# "meris-workspace-write"

meris doctor    # platform sandbox: ok · seatbelt active, mask N secret file(s)
```

## allowlist + mask 对齐

| 检查 | 命令 / 行为 |
|------|-------------|
| mask `.env` | `sandbox run` + `cat .env` 无泄漏 |
| allowlist hybrid | `policy` → `networkEnforcement: allowlist-hybrid(N)` |
| strict 拦截 | `sandbox check --mode strict` + 未授权 `curl` → `blocked: true` |
| Python 执行路径 | `run_bash_sync` strict 下同样拦截（与 meris-rs 一致） |

CI：`macos-seatbelt` job 与 Linux bwrap job 对等（mask / write-outside / allowlist）。

## 相关

- [sandbox.md](sandbox.md)
- [PLATFORM_MATRIX.md](PLATFORM_MATRIX.md)
