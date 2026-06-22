# Loop 事件流

Meris agent loop 可输出 **JSONL 事件**，供 TUI、IDE、CI 消费。

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
| `token` | assistant 文本片段（可分块，`chunk` 序号；OpenAI 兼容 provider 支持真流式） |
| `plan` | Plan 模式任务清单（`items[]` checkbox，`path`） |
| `parallel_start` | 并行批次开始（`tasks[]` 含 `index`/`task`） |
| `parallel_task_done` | 单任务结束（`parallel_index`，`status`） |
| `parallel_done` | 整批结束（`count`） |

并行子事件带 `parallel_index` / `parallel_task` / `parallel_session` 标签。
| `reasoning` | 模型推理链（DeepSeek `reasoning_content` 等，可折叠，与 `thinking` 区分） |
| `thinking` | harness 进度（压缩、路由等，可折叠） |
| `tool_start` / `tool_end` | 工具调用（`tool_start` 含 `args`） |
| `approval_request` | approve 模式待审批（含 `request_id` / `tool` / `args`） |
| `file_change` | `write_file` / `edit_file` 后（含 `path`、`diff_preview`） |
| `sensor` | DoD / postEdit 结果 |
| `status` | 其它进度行 |
| `done` | 终态 status |

每行 JSON：`{"type":"event","ts":...,"kind":"...","message":"...",...}`

## TUI

`meris tui` 内部收集事件，结构化行（tool/sensor/done）写入日志面板；右侧 **Ratchet** 列显示 pending proposals / insights。

## 相关

- 实现：`meris/harness/protocol.py`
- UI：`meris/ui` SSE 与 Agent Window 事件路由
