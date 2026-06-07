# Phase G — OpenAI Codex CLI 对标（Harness 已齐，补安全与分发）

> 对照：[OpenAI Codex CLI](https://github.com/openai/codex) · [PLAN_PHASE_E.md](PLAN_PHASE_E.md)（Harness 课已上完）  
> 宗旨：缩小 **沙箱 / 网络 / 安装** 差距，保留 Meris 差异化（Ratchet、多厂商 routing）

## 差距快照（2026-06）

| 维度 | Codex CLI | Meris Phase F 后 | Phase G 目标 |
|------|-----------|------------------|--------------|
| Harness / review / exec / events | ✅ | ✅ Phase E | 维持 |
| Rust agent loop | ✅ 全 Rust | ✅ 混合 | G4 默认 native |
| 沙箱 preset | read-only / workspace-write / danger | warn/strict 手工配 | **G1 ✅ preset** |
| 默认无网络 bash | ✅ | shared 默认 | **G1 ✅ isolated 默认** |
| 网络 allowlist | ✅ | ❌ | G2 |
| macOS Seatbelt / Win 沙箱 | ✅ | ❌ / WSL | G3（文档 + WSL 优先） |
| 一键安装 | npm/brew | pip 未发 | G5 tag/PyPI |
| Ratchet 闭环 | ❌ | ✅ | 维持（差异化） |

## 里程碑

| 阶段 | 交付 | 验收 |
|------|------|------|
| **G1** | Codex 风格 `sandbox.preset` + 默认 `workspace-write`（network isolated） | `test_sandbox_presets.py` + 文档对照表 |
| **G2** | `network.allowlist`（bwrap 下允许域名/IP） | 单测 + sandbox.md |
| **G3** | 平台矩阵文档 + doctor 提示 Codex 等价 preset | doctor 输出 preset 名 |
| **G4** | 默认 `MERIS_NATIVE_LOOP=auto` 进模板；Route B 完成标准 | live benchmark 3 task |
| **G5** | E0 发版（tag + PyPI + Release 页） | 用户明确「打 tag」 |
| **G6** | 可选：macOS sandbox 调研 / execpolicy 加强 | spike 文档 |

## G1 preset 映射（Codex → Meris）

| Codex `--sandbox` | Meris `sandbox.preset` | mode | network | osSandbox |
|-------------------|------------------------|------|---------|-----------|
| read-only | `read-only` | strict | isolated | auto |
| workspace-write（Auto 默认） | `workspace-write` | warn | isolated | auto |
| danger-full-access | `danger-full-access` | off | shared | off |

显式 `sandbox.mode` / `network` / `osSandbox` **覆盖** preset 字段。

## 依赖

```
G1 preset ──► G2 allowlist ──► G3 doctor/平台
Route B dogfood ──► G5 发版（并行）
P5 native ──► G4 默认 native loop
```

## 不做（相对 Codex CLI）

- ChatGPT 设备码登录 · Codex 专有模型 · Cloud Agent · 闭源 Memory

## 参考

- [docs/harness/sandbox.md](harness/sandbox.md)
- [ROUTE_B_DOGFOOD.md](ROUTE_B_DOGFOOD.md)
- [OpenAI agent approvals & security](https://developers.openai.com/codex/agent-approvals-security)
