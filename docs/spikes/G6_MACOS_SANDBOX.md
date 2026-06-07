# G6 Spike — macOS Seatbelt 沙箱（对标 Codex CLI）

> Phase G6 · G6.2 **已实现** · 平台矩阵见 [PLATFORM_MATRIX.md](../harness/PLATFORM_MATRIX.md)

## 背景

| 平台 | Meris 今日 | Codex CLI |
|------|-----------|-----------|
| Linux | bubblewrap（`osSandbox: auto`） | Landlock / bubblewrap |
| Windows | 策略层 + WSL bwrap | 原生 + WSL |
| **macOS** | **策略层 + cwd 锁定** | **`sandbox-exec` + Seatbelt SBPL** |

macOS 是 Meris 与 Codex 在 OS 层差距最大的平台（G3 已文档化）。

## Meris 设计（非 Codex 抄写）

见 **[SEATBELT_DESIGN.md](../harness/SEATBELT_DESIGN.md)** — 要点：

1. **程序化 profile**（`meris-read-only` / `meris-workspace-write`），与 G1 preset 一一对应  
2. **分层读 allowlist**（系统根 + workspace），拒绝 `(allow file-read*)` 全局放行  
3. **网络混合模型**：isolated 用 Seatbelt 拒绝；allowlist 用 OS 放行 + G2 命令级拦截  
4. **单一数据源**：`meris-rs sandbox policy` 生成 SBPL，Python 不维护第二份文件  

Codex 参考仅用于理解 `sandbox-exec` 机制，不复制其 SBPL 文件。

## Codex 做法（参考）

OpenAI Codex Rust 核心（`codex-rs/sandboxing/`）：

1. 调用 `/usr/bin/sandbox-exec -p <policy> -- <cmd>`
2. 基础策略文件 `seatbelt_base_policy.sbpl`（默认 deny，白名单 sysctl / 必要路径）
3. **workspace-write**：动态追加 `(allow file-write* (subpath (param "WRITABLE_ROOT_N")))`，绑定 workspace 等目录
4. **read-only**：仅 base policy，无 writable roots
5. 若 Seatbelt 无法应用所选策略 → **拒绝执行**（不 silent fallback）

参考：

- [Codex sandboxing 概念](https://developers.openai.com/codex/concepts/sandboxing)
- [codex-rs seatbelt_base_policy.sbpl](https://github.com/openai/codex/blob/main/codex-rs/sandboxing/src/seatbelt_base_policy.sbpl)

## Meris 映射（提议）

| Meris `sandbox.preset` | Seatbelt 行为（提议） |
|------------------------|----------------------|
| `read-only` | base policy only |
| `workspace-write` | base + workspace 可写 + `/tmp` |
| `danger-full-access` | 不调用 `sandbox-exec`（同 Linux `osSandbox: off`） |

与现有配置对齐：

- `sandbox.osSandbox: auto` → macOS 上检测 `sandbox-exec`，可用则启用
- `network: isolated` → Seatbelt **无** `--unshare-net` 等价；需 `(deny network*)` 或仍依赖命令级 allowlist（G2）
- `maskSecrets` → `(deny file-read* (subpath ".env"))` 或 ro 语义

## 实现 sketch（meris-rs）

```
meris-rs/src/sandbox_macos.rs   # cfg(target_os = "macos")
  - find_sandbox_exec() -> Option<PathBuf>
  - build_seatbelt_policy(workspace, settings) -> (policy, params)
  - run_bash_seatbelt(...) -> Result<(i32, String), String>

run_bash_in_workspace():
  if cfg!(macos) && should_use_seatbelt(settings) {
    run_bash_seatbelt(...)
  } else if should_use_bubblewrap(...) { ... }
```

Python `probe_os_sandbox` / doctor：增加 `seatbelt: true|false` 与 Codex 差距提示（G3 已有 warn）。

## 风险与限制

| 风险 | 说明 |
|------|------|
| SBPL 维护成本 | base policy 需随 macOS 版本迭代（Codex 从 Chromium 策略衍生） |
| 网络隔离 | Seatbelt 网络规则与 Linux bwrap 语义不同；G2 allowlist 仍需要 |
| CI | GitHub `macos-latest` 可测 `sandbox-exec`，但无 GUI automation 权限边界 |
| 签名 / SIP | 某些路径与 TCC（Automation、Accessibility）Codex 用 extension profiles 处理 — Meris 初版可不做 |
| `sandbox-exec` 弃用讨论 | Apple 长期方向不确定；Codex 仍在用，Meris 可跟随 |

## 建议分期

| 阶段 | 交付 | 工作量 |
|------|------|--------|
| **G6.1**（本 spike） | 文档 + doctor 探测 stub | ✅ |
| **G6.2** | `read-only` + `workspace-write` Seatbelt MVP（bash） | ✅ meris-rs + Python |
| **G6.3** | 与 G2 allowlist / maskSecrets 对齐 + macOS CI parity | ✅ |
| G6.4 | CI macOS job + parity tests | ✅（并入 G6.3 macos-seatbelt job） |

**推荐优先级**：低于 G5 发版与 dogfood；Linux/WSL 已覆盖主要 CI 与用户路径。

## 验收标准（未来 G6.2）

```bash
# macOS only
meris-rs sandbox probe --workspace .
# → seatbelt: true, wouldUseSeatbelt: true

meris doctor
# → platform sandbox: ok (policy + seatbelt)

# bash 在 workspace 外写入应失败（workspace-write preset）
```

## 不做（G6 范围外）

- macOS TCC / Automation / Accessibility profiles（Codex PR #11639 级别）
- 替代 `sandbox-exec` 的 App Sandbox 打包
- Windows 原生 AppContainer（另项）

## 相关

- [sandbox.md](../harness/sandbox.md)
- [PLAN_PHASE_G.md](../PLAN_PHASE_G.md)
