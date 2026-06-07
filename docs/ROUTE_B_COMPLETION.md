# 线路 B 完成标准（Phase G4）

> 日常 dogfood 见 [ROUTE_B_DOGFOOD.md](ROUTE_B_DOGFOOD.md) · Codex 对标 [PLAN_PHASE_G.md](PLAN_PHASE_G.md)

Phase G4 定义 **「Route B 技术就绪」**：native loop 默认开启、离线/在线验收可重复。  
**不等于**发版（G5 仍等你明确说「打 tag」）。

## 一次性检查清单

| # | 步骤 | 期望 |
|---|------|------|
| 1 | `meris-rs` 可用 | `meris native status` → `available: true` |
| 2 | `.env` 含 `MERIS_NATIVE_LOOP=auto` | `nativeLoopEnabled: true`（勿设 `MERIS_NATIVE_PROVIDER=0`） |
| 3 | `meris doctor` | API + harness + **native loop** + sandbox 无 fail |
| 4 | `meris release check` | pytest + mock benchmark + harness + cargo 全绿 |
| 5 | 离线 mock | `python scripts/run_benchmark_mock.py --native-only` 通过 |
| 6 | **Live 3 task** | `python scripts/run_benchmark_live.py` → **3/3 passed** |

`init-harness` 会在无 `.env` 时从模板创建，默认已含 `MERIS_NATIVE_LOOP=auto`。

## Live 3 task（G4 验收）

默认运行以下 **只读 ask** 任务（需 API Key）：

| Task id | 验证点 |
|---------|--------|
| `read_hello` | `read_file` + 回答 |
| `docs_smoke` | 读 `docs/harness/testing.md` |
| `list_tools` | `grep` 工具名 |

```bash
python scripts/run_benchmark_live.py
# 或显式
python scripts/run_benchmark_live.py --route-b
# 单任务调试
python scripts/run_benchmark_live.py --filter read_hello
```

输出应含 `(native loop via MERIS_NATIVE_LOOP=auto)`。

## 与 Codex CLI 对齐点（G4）

| Codex | Meris G4 |
|-------|----------|
| 默认 Rust agent loop | `MERIS_NATIVE_LOOP=auto` 进 `.env.example` + init 模板 |
| 可重复 smoke | live 3 task + mock native-only |

仍保留 Python loop 回退：`MERIS_NATIVE_LOOP=0`。

## 完成后仍建议（非 G4 阻塞）

- 1–2 周真实任务 dogfood（`meris run …`）
- Ratchet digest 闭环 → [RATCHET_30MIN.md](RATCHET_30MIN.md)
- 7 天复盘 → [DOGFOOD_7DAY.md](DOGFOOD_7DAY.md)

## 相关

- [.env.example](../.env.example)
- [USER_SETUP.md](USER_SETUP.md) — native 环境变量
- [NATIVE_BINARY.md](NATIVE_BINARY.md) — 安装 meris-rs
