# Loop 事件流（Phase E4）

Meris agent loop 可输出 **JSONL 事件**，供 TUI、IDE、CI 消费（对标 Codex Submission/Event 队列）。

## 启用

```bash
meris run "fix tests" --event-stream .meris/events/run.jsonl
meris run "task" --event-stream -          # stdout
meris exec "task" --json                   # 内存收集 + JSON 摘要
```

## 事件类型

| kind | 说明 |
|------|------|
| `submission` | 用户任务 / cancel（SQ） |
| `session_start` | workspace、mode、session、model |
| `token` | assistant 文本片段 |
| `tool_start` / `tool_end` | 工具调用 |
| `sensor` | DoD / postEdit 结果 |
| `status` | 其它进度行 |
| `done` | 终态 status |

每行 JSON：`{"type":"event","ts":...,"kind":"...","message":"...",...}`

## TUI

`meris tui` 内部收集事件，结构化行（tool/sensor/done）写入日志面板；右侧 **Ratchet** 列显示 pending proposals / insights。

## 相关

- 实现：`meris/harness/protocol.py`
- Codex 对照：[PLAN_PHASE_E.md](../PLAN_PHASE_E.md) E4
