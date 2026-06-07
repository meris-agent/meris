# 线路 B — Dogfood（暂不发版）

> Phase F 完成后 · **G4 完成标准** → [ROUTE_B_COMPLETION.md](ROUTE_B_COMPLETION.md) · 正式发版见 [E0_RELEASE_CHECKLIST.md](E0_RELEASE_CHECKLIST.md)

## 一次性准备

```powershell
# 1. 更新 meris-rs（Windows，需 gh auth login）
powershell -ExecutionPolicy Bypass -File scripts\install_meris_rs_from_ci.ps1 -CleanDebug

# 2. 项目根 .env（从 .env.example 复制，填 API Key + native 推荐项）
#    MERIS_NATIVE_LOOP=auto
#    不要设 MERIS_NATIVE_PROVIDER=0（除非 Rust provider 调试）

# 3. 验证
meris native status    # nativeProviderEnabled / nativeLoopEnabled 应为 True
meris doctor
meris release check
python scripts/run_benchmark_mock.py --native-only
```

## 每周（或改代码后）

```bash
meris release check
python scripts/run_benchmark_mock.py
python scripts/run_benchmark_mock.py --native-only
meris harness check
meris doctor
```

有 API 时（**G4 验收：默认 3 task**）：

```bash
python scripts/run_benchmark_live.py          # read_hello + docs_smoke + list_tools
python scripts/run_benchmark_live.py --filter read_hello
meris run "你的真实任务" --max-turns 10
```

## Ratchet 闭环

```bash
meris ratchet digest
meris ratchet status
# 有提案时：review → apply --verify
```

## 记录习惯

- Agent 犯错 → 改 `.meris/rules/`、`.meris/skills/`、`AGENTS.md`，不是只改当次输出
- 跨会话 → 更新 `PROGRESS.md`
- 7 天复盘 → [DOGFOOD_7DAY.md](DOGFOOD_7DAY.md)

## 暂缓（F5）

- tag `v0.0.1`、GitHub Release 页、PyPI — **需你明确说「打 tag」后再做**
