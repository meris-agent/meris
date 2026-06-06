# Phase F — Native 稳定化与发布准备（不打 tag 可并行）

> P5-4 完成后 · 与 [RUST_ROADMAP.md](RUST_ROADMAP.md) / [PLAN_P5_4.md](PLAN_P5_4.md) 衔接 · **E0 tag 暂缓**

## 目标

在 **不强制打 tag** 的前提下：

1. 文档与 roadmap 反映 P5-4 现状
2. 补齐 native loop 与 Python loop 的**可感知差距**
3. 分发路径可手动验证（`workflow_dispatch` artifact、release check）
4. Dogfood 与 benchmark 覆盖 native 路径

**智力仍取决于 LLM**；本阶段重点是 orchestration parity 与可交付性。

## 架构（F 阶段后）

```
meris-rs run ask|plan|run|review   ──► native agent（冷启动）
         │ 复杂子命令 / TUI / MCP 配置
         └──────────────────────────► Python meris（MERIS_NATIVE_LOOP=auto）
                │
                ├─ harness 桥：system-prompt / review-task / hooks / sensors / mcp
                └─ 动态路由、parallel、ratchet 仍 Python 优先
```

## 里程碑

| 阶段 | 交付 | 验收 |
|------|------|------|
| **F1** ✅ | 文档同步：ROADMAP、USER_SETUP native、meris-rs README、RELEASE 亮点 | 新人可按文档启用 native loop |
| **F2-M1** ✅ | `harness review-task --json` + `meris-rs run review` | `test_review_bridge.py` + CI smoke |
| **F2-M2** ✅ | `--max-turns` / `--resume` + `run_entry.rs` 单测 | `cargo test run_entry` |
| **F2-M3** ✅ | DoD 失败 `harness dod-failed` + ratchet 提示 | `test_dod_bridge.py` |
| **F3-M1** ✅ | [NATIVE_BINARY.md](NATIVE_BINARY.md) artifact 下载 | USER_SETUP 链接 |
| **F3-M2** | pip wheel 可选 bundled binary（平台 wheel 或 post-install 脚本） | 长期；需 hatchling 策略 |
| **F4** ✅ | native_* 离线 benchmark + `--native` / `--native-only` | `test_benchmark_native.py` + CI |
| **F5** | E0 正式发布 | tag `v0.0.1` + PyPI（**用户明确要求后再做**） |

## F1 范围（文档）

- [ROADMAP.md](../ROADMAP.md)：P5-4 完成、Phase F 链接
- [USER_SETUP.md](USER_SETUP.md)：`MERIS_NATIVE` / `MERIS_NATIVE_LOOP` 推荐配置
- [RELEASE_v0.0.1.md](RELEASE_v0.0.1.md)：native loop、meris-rs run 亮点
- [PROGRESS.md](../PROGRESS.md)：Phase F 进行中条目

## F2-M1 范围（review 桥）

1. `meris harness review-task --json [--staged]` → `{"task":"..."}`
2. `meris-rs run review [--staged] [--cwd] [--event-stream]` → 加载 task → `agent run --mode review`
3. CI：`meris harness review-task` smoke（无 diff 时 exit 非 0 可 skip）

## F4 范围（native benchmark）

1. `tasks.json` 增加 `native_system_prompt` / `native_dod_bridge` / `native_run_entry` 本地任务
2. 默认 mock benchmark 仍 **8/8**（排除 `native_*`）
3. `python scripts/run_benchmark_mock.py --native-only` — 3 项 bridge smoke
4. `meris benchmark run --native-only` / `--native` — CLI 对齐

## 环境变量（推荐 dogfood）

| 变量 | 推荐 |
|------|------|
| `MERIS_NATIVE` | 默认 auto（有二进制即启用） |
| `MERIS_NATIVE_LOOP` | `auto` 或 `1` |
| `MERIS_NATIVE_LOOP=0` | 调试 Python loop |

```bash
meris-rs run ask "List meris/*.py"
meris-rs run review --staged
meris release check
```

## 风险

- Windows 本地 `cargo build` 可能被 App Control 拦截 — 依赖 Linux CI
- `review` 依赖 git diff；CI 无 diff 时只测 CLI 形状
- pip bundled binary 涉及多平台 wheel — F3-M2 单独评估

## 参考

- P5-4：[PLAN_P5_4.md](PLAN_P5_4.md)
- Review：[meris/harness/review.py](../meris/harness/review.py)
- Release check：[meris/harness/release_check.py](../meris/harness/release_check.py)
