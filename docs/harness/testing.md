# 测试与 Definition of Done

## 单元测试（本仓库）

```bash
pytest tests/ -m "not integration" -q
```

- 集成测试标记：`@pytest.mark.integration`（CI 默认不跑）
- 改 Python 后必须跑上述命令，退出码 0 才算完成。

## Harness 检查（Phase E2）

```bash
meris harness check
```

静态检查路径/import 等；失败时输出 **hint** 供 Agent 自修。

## Benchmark（Harness 回归）

```bash
meris benchmark list
meris benchmark run
meris benchmark run --filter plan_smoke
python scripts/run_benchmark_mock.py   # 离线 mock，CI 同款，不耗 API
```

任务含 local：`harness_check`、`review_task`（E5.4）；agent 任务需 LLM。

## CI（GitHub Actions）

Push/PR 自动跑：`pytest`、`ruff`、`meris harness check`、`run_benchmark_mock.py`、`meris ratchet status`；Rust job 另跑 `cargo test` + sandbox check。

## Sensors

`.meris/settings.yaml` 中 `sensors.postEdit` / `onComplete` 可在改文件后自动跑验收命令。

## DoD（AGENTS 摘要）

任务完成 = **pytest 全绿**（见上）。文档-only 改动仍建议跑 pytest（本仓库测试很快）。
