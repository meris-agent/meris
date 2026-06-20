# 模型路由（Meris 本仓库）

配置：`.meris/settings.yaml` + 个人 `.meris/settings.local.yaml`（gitignore）。

## 原则

- **问句 / 只读** → `fast` profile（如 deepseek-chat）  
- **改代码 / run** → `code` 或 `dynamic` 候选池  
- **大重构** → `rules` 命中 `heavy-refactor` → `heavy` profile  

见 [docs/MODELS.md](../MODELS.md)。

## 意图 → mode → model 决策表

| 用户意图（典型） | CLI / UI mode | 工具权限 | 默认 profile | 备注 |
|------------------|---------------|----------|--------------|------|
| 解释代码、问答、检索 | `ask` | 只读 | `fast` | 无写盘、无 bash 改文件 |
| 出任务清单、不写代码 | `plan` | 只读 | `fast` 或 `code` | 落盘 `.meris/plan/tasks.md` |
| 改代码、跑测试、提交 | `run` | 读写 + sensors | `code` / `dynamic` | DoD 失败触发 Ratchet |
| 审查 diff / staged | `review` | 只读 | `fast` | `meris review` |
| 多任务并行 | `parallel` + `--mode ask` | 各 lane 隔离 | 同 `ask` | UI Parallel tab |
| Plan 清单 → 实现 | `run --from-plan` | 读写 | `code` | Agent Window **Run plan →** |

### mode 与 Harness 的关系

| mode | 读入 Harness | 写回 Harness |
|------|--------------|--------------|
| `ask` | rules · skills · PROGRESS | 通常无（除非用户要求） |
| `plan` | 同上 + plan-format skill | `.meris/plan/tasks.md` |
| `run` | 同上 + spec | PROGRESS · sensors · Ratchet 事件 |

### 动态路由（turn 级）

`pick_model_for_turn` 在**同一 session 内**按轮次调整：

| 信号 | 行为 |
|------|------|
| 最近 tool 失败 / 长输出 | 可升到 `heavy` 候选 |
| 纯对话、无 tool | 保持 `fast` |
| `models.dynamic.enabled: false` | 仅用 `byMode` 静态表 |

验证：

```bash
meris models route --json "你的任务描述"
meris doctor
```

## local 覆盖（重要）

`settings.local.yaml` **只写少量字段**，例如：

```yaml
models:
  profiles:
    code:
      model: ep-your-endpoint
  dynamic:
    enabled: true
```

**不要**在 local 里整段复制 `byMode` / 整表 `rules` — 会**替换** YAML 列表。

**E6.5**：`models.rules` 按 `name` 深合并（local 只覆盖同名 rule 的字段）；其它列表仍为替换。

## Agent Window 与路由

| UI 控件 | 路由层 |
|---------|--------|
| Composer `mode-select` | 覆盖当次 `ask` / `plan` / `run` |
| 模型下拉 `Auto` | `resolve_task_routing` + `pick_model_for_turn` |
| 顶栏 workspace 下拉 | **cwd 路由**（非 model）：决定 `.meris/` 与 git 上下文 |
| Plan → Run plan | 自动切到嵌套 `meris/` 仓库根 + `--from-plan` |

## 相关

- [architecture.md](architecture.md) — 包布局  
- [Meris Agent 设计模式对照](../../Articles/Meris-Agent设计模式对照.md)（vault 笔记）
