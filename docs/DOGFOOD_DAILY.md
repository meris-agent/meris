# 日常 Dogfood 清单

> 人工 1–2 周真实任务验证；本文件 + `scripts/dogfood-daily.ps1` 提供可重复检查项。

## 每日启动（约 5 分钟）

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dogfood-daily.ps1
# 或
meris dogfood
```

脚本会检查：

- `meris doctor` 全绿（或已知可忽略项已记录）
- `MERIS_NATIVE_LOOP` / native status
- 最近一次 benchmark / pytest 摘要（若存在 `.meris/events/`）
- PROGRESS.md 是否有未闭合 Session note

## 每日任务模板

在 vault 或 `meris/` 仓库任选 **1 个真实任务**（修 bug、写测试、更新文档、小功能）：

1. `cd meris`（改源码时）或 vault 根（改笔记时）
2. `meris ui` 或 VS Code Meris 面板
3. **Ask** 探索 → **Plan** 勾选 → **Run** 执行
4. 失败时：先改 Harness（rules/skills/Ratchet），再重跑
5. 结束时更新对应 `PROGRESS.md` Session note

## 每周复盘

| 指标 | 目标 |
|------|------|
| DoD 一次通过率 | 上升趋势 |
| Ratchet pending | 0 或已 review |
| benchmark local | 8/8 或记录例外 |
| Harness 改动 | 每次失败至少 1 条规则/skill |

## 记录格式（PROGRESS.md）

```markdown
## Session note (YYYY-MM-DD)
- **Task**: …
- **Status**: completed | dod_failed | error
- **Harness delta**: （若有）rules/skills 变更
```

## 相关文档

- [ROUTE_B_DOGFOOD.md](ROUTE_B_DOGFOOD.md)
- [docs/harness/testing.md](harness/testing.md)
