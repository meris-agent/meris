# Meris Ratchet — 自我进化设计

> **读者**：想理解 Ratchet 如何工作的用户与贡献者。  
> **怎么用**：见 [README](../README.md) 的 Ratchet 命令表与 [USER_SETUP.md](USER_SETUP.md)。  
> 维护者实现进度不在公开仓；用户以 README 命令表与本设计文档为准。

---

## 1. 问题陈述

### 现状

Meris 已有 Harness **载体**（AGENTS、rules、skills、PROGRESS、session、sensors），但进化依赖维护者：

- 看失败 → 手改 `.meris/rules/` 或 `AGENTS.md`
- 7 天 dogfood 已验证有效，但 **不可扩展** 给普通用户

### 目标

实现 **Ratchet 闭环**：

```
信号（失败/拒绝/重复） → 诊断 →  Harness 补丁提案 → 人确认 → 写入 → benchmark/pytest 验证
```

第二次做同类任务时，Agent **无需重新踩坑**。

### 非目标（v1 不做）

- 在线微调模型权重
- 未经确认自动改 `AGENTS.md` / `settings.json` permissions
- 跨项目上传/同步用户数据（云画像）
- 用 Ratchet 替代 code review 或安全审计

---

## 2. 设计原则

| 原则 | 说明 |
|------|------|
| **Harness-first** | 进化产物必须是仓库内可读文件（rules/skills/AGENTS 片段/PROGRESS 摘要） |
| **Human-in-the-loop** | 默认 **提议 + diff**，`--apply` 需显式确认；敏感路径永不动 |
| **可验证** | 每次 apply 后可选跑 `meris benchmark run` 或 AGENTS DoD |
| **可逆** | 补丁带 id，可 `meris ratchet revert <id>` |
| **项目隔离** | 所有状态在 `<workspace>/.meris/`，不进 PyPI 包 |

检验句（与 VISION 一致）：

> 应用这条补丁后，同一项目里第二次做同类任务是否更省事？

---

## 3. 信号（Signals）— 什么触发 Ratchet

Ratchet 消费 **结构化信号**，不是扫描整个 git history。

### 3.1 信号来源

| 来源 | 字段 | 触发场景 |
|------|------|----------|
| **Session** | `.meris/sessions/{id}.json` | `status`: `dod_failed`, `error`, `cancelled` |
| **PROGRESS** | `PROGRESS.md` append | 连续相同 `Status: dod_failed` |
| **Benchmark** | `meris benchmark run` | task `fail` + `detail` |
| **Approve** | 新：`.meris/ratchet/events.jsonl` | 用户拒绝某 tool（`y/n → n`） |
| **Doctor** | `meris doctor` warn | 缺 Harness、API 以外：重复 warn 模式（后续） |

### 3.2 信号记录（新）

```
.meris/ratchet/
├── events.jsonl      # 追加-only 事件流
├── proposals/        # 待审补丁 YAML/MD
├── applied/          # 已应用补丁归档
└── profile.md        # 可选：用户习惯摘要
```

**events.jsonl** 单行 JSON 示例：

```json
{"ts":"2026-05-30T12:00:00Z","kind":"dod_failed","session":"abc123","task":"fix test","detail":"pytest failed","tags":["dod","pytest"]}
{"ts":"...","kind":"approve_denied","session":"abc123","tool":"bash","args_summary":"git push","tags":["permissions"]}
{"ts":"...","kind":"benchmark_fail","task_id":"plan_smoke","detail":"missing: [ ]","tags":["plan","format"]}
```

写入时机：

- `loop.py` 的 `finally`：`dod_failed` / `error` → append event
- `benchmark.py`：fail → append event
- `approve_fn` 返回 false → append event（不记录完整 args，仅摘要）

---

## 4. 诊断（Diagnose）— 从信号到「教训类型」

### 4.1 教训分类（Lesson taxonomy）

与 dogfood 复盘对齐，可扩展：

| ID | 类型 | 典型信号 | 默认补丁目标 |
|----|------|----------|--------------|
| `L-path` | 路径/命名 | plan 路径错、block 路径 | `.meris/rules/paths.md` |
| `L-cwd` | 工作区 cwd | vault 根改 README 被 block | `.meris/rules/workspace.md` |
| `L-format` | 输出格式 | plan 无 `- [ ]` | `.meris/skills/plan-format.md` |
| `L-perm` | 权限/工具 | approve 多次拒绝 bash | `settings.json` deny 或 AGENTS 禁止节 |
| `L-dod` | 验收失败 | dod_failed + pytest | AGENTS DoD 或 `sensors.postEdit` |
| `L-repeat` | 重复任务 | 相似 task 字符串聚类 | PROGRESS 摘要或 skill |

### 4.2 诊断流水线

```
events.jsonl (最近 N 条)
    → 规则引擎（regex + 标签，无 LLM，快）
    → 可选 LLM 归纳（meris ratchet analyze，慢但灵活）
    → Proposal 对象
```

**v1 优先规则引擎**（确定性、可测）：

```python
# 伪代码
if "missing: [ ]" in detail and mode == "plan":
    return Proposal(lesson="L-format", target=".meris/skills/plan-format.md", ...)
if approve_denied(tool="bash", pattern="git push"):
    return Proposal(lesson="L-perm", target="AGENTS.md", section="禁止操作", ...)
```

**v2 加 LLM**：把 session 末 3 轮 + 现有 rules 摘要喂给 `meris ask`，输出 **严格 JSON Proposal**（便于 `--apply` 解析）。

---

## 5. 补丁（Proposal）— 写回 Harness 的单位

### 5.1 Proposal  schema

文件：`.meris/ratchet/proposals/{id}.yaml`

```yaml
id: ratchet-20260530-001
created: 2026-05-30T12:00:00Z
lesson: L-format
confidence: high          # high | medium | low
signals:
  - benchmark_fail:plan_smoke
summary: "Plan 输出缺少 - [ ] checkbox"
target:
  path: .meris/skills/plan-format.md
  action: append          # append | create | patch_section
  content: |
    ## Ratchet auto (2026-05-30)
    - benchmark plan_smoke 要求输出含 `- [ ]`
verify:
  - "meris benchmark run --filter plan_smoke"
status: pending           # pending | applied | rejected
```

### 5.2 允许的 target（白名单）

| path | action | 需确认 |
|------|--------|--------|
| `.meris/rules/*.md` | create / append | 否（低风险） |
| `.meris/skills/*.md` | create / append | 否 |
| `PROGRESS.md` | append 摘要块 | 否 |
| `.meris/profile.md` | create / append | 否 |
| `AGENTS.md` | `patch_section`（仅指定 ## 下追加） | **是** |
| `.meris/settings.json` | 仅 `permissions.deny` 追加 | **是** |
| `meris/**` 源码 | — | **禁止** auto-apply |

### 5.3 PROGRESS 摘要块（替代无限 session note）

apply 时可把多条 session note **rollup** 为：

```markdown
## Ratchet 摘要 (auto, 2026-05-30)

- **别再做**：在 vault 根 run 改 Meris README
- **记得**：plan 必须 `- [ ]`，见 plan-format skill
- **DoD**：改 Python 后跑 `pytest tests/ -m "not integration" -q`
```

`load_progress()` 优先读摘要节 + 最近 3 条 session note（实现时在 `memory.py` 改裁剪逻辑）。

---

## 6. CLI — `meris ratchet`

### 6.1 子命令

```bash
# 扫描信号，生成/更新 proposals（规则引擎，不调 LLM）
meris ratchet scan
meris ratchet scan --since 7d

# 列出待审补丁
meris ratchet list
meris ratchet show ratchet-20260530-001

# 交互审阅：展示 diff，y/n
meris ratchet review
meris ratchet review ratchet-20260530-001

# 应用补丁（写文件 + 归档 + 可选 verify）
meris ratchet apply ratchet-20260530-001
meris ratchet apply ratchet-20260530-001 --verify

# 撤销（从 applied/ 恢复 git-style 或备份）
meris ratchet revert ratchet-20260530-001

# LLM 辅助诊断（v2）
meris ratchet analyze --session abc123
meris ratchet analyze --last-fail
```

### 6.2 与现有命令集成

| 钩子位置 | 行为 |
|----------|------|
| `run` 结束且 `dod_failed` | 打印：`[ratchet] 1 proposal ready — meris ratchet review` |
| `benchmark run` 有 fail | 同上 + `--filter` 提示 |
| `doctor` | 新增 check：`ratchet pending: N` |

可选：`meris run --ratchet` → run 失败后自动 `scan`（不 auto-apply）。

---

## 7. 用户习惯层（Profile）

`.meris/profile.md`（注入 system prompt，在 rules 之后）：

```markdown
# User profile (Ratchet)

- 默认偏好：`--approve` 改源码
- 常拒绝：bash `git push`
- 常用 cwd：Meris 仓库根（非 vault 根）
```

来源：

- approve deny 统计（同一 tool+matcher ≥2 次）
- CLI 显式：`meris ratchet profile set prefer-approve=true`

**不**自动推断 API key、路径外的隐私内容。

---

## 8. 项目画像（Project learn）

```bash
meris ratchet learn --init
```

只读扫描（不调用 LLM 的 v1）：

- 检测 `pyproject.toml` / `package.json` / `Cargo.toml`
- 猜测试命令 → 建议写入 AGENTS DoD
- 列顶层目录 → 建议 `AGENTS.md` 布局表草稿（proposal，不直接写）

与 `init-harness` 关系：`init-harness` 复制模板；`ratchet learn --init` 在已有仓库 **补全** 提案。

---

## 8′. 主动进化（Digest / Insights）

与 §3–§6 **被动 Ratchet**（失败 → scan/analyze → proposal）**并存**，不替代：

```
.meris/sessions/*.json  user 消息
        ↓
meris ratchet digest [--llm]     # 规则档 + 可选 LLM
        ↓
.meris/ratchet/insights/pending.jsonl
        ↓
meris ratchet insights review    # 提问 → 用户确认
        ↓
accept → 现有 proposal → apply   # 写入 .meris/rules|skills
dismiss → dismissed.jsonl        # 不再提示
```

| 命令 | 作用 |
|------|------|
| `meris ratchet digest` | 扫最近 N 天 user 消息，重复主题 → insight |
| `meris ratchet digest --dry-run` | 只预览，不写盘 |
| `meris ratchet digest --llm` | 规则档 + LLM 补充（需 API） |
| `meris ratchet insights list` | 待确认习惯 |
| `meris ratchet insights review` | 交互：写入 Harness / dismiss / 跳过 |
| `meris ratchet insights accept <id> [--apply]` | 非交互接受 |

**规则档**内置主题（≥2 个不同 session 命中）：YAML/local 最小覆盖、暂不发版、Harness-first、最小 diff。

**检验句**（与被动 Ratchet 相同）：

> 用户确认并 apply 后，Agent 是否更少违背已表达的偏好？

**隐私**：只读 workspace 内 session；不扫 Cursor 云端聊天；LLM 档不传 API key。

---

## 9. 模块划分（实现）

```
meris/harness/ratchet/
├── events.py       # append/read events.jsonl
├── classify.py     # 规则引擎 → Lesson
├── proposal.py     # Proposal dataclass, load/save yaml
├── apply.py        # 白名单写入 + 备份
├── scan.py         # scan → proposals
├── profile.py      # profile.md
├── learn.py        # project scan
├── insights.py     # insight jsonl
├── digest.py       # session 习惯挖掘
└── digest_llm.py   # digest LLM 档

meris/cli.py        # ratchet 子命令组
```

与现有模块关系：

| 现有 | Ratchet 用法 |
|------|--------------|
| `guides.load_guides()` | 已注入 rules；补丁 append 后下轮生效 |
| `memory.load_progress()` | 改裁剪：摘要优先 |
| `loop.py` | emit events；dod_failed 提示 |
| `benchmark.py` | emit events |
| `sensors.py` | verify 步骤可复用 DoD |

---

## 10. 当前能力（摘要）

Ratchet 已包含：**被动**（失败/拒绝 → scan/analyze → 提案 → 人审 → apply/revert）与 **主动**（digest → insights review）两条链；支持 profile、learn、benchmark 验证、TUI 审阅。完整命令见 [README](../README.md#workflows)。

---

## 11. 安全与边界

- **永不** auto-apply 到 `meris/` 包源码、`.env`、secrets
- Proposal `content` 长度上限（如 4KB/条）
- `events.jsonl` 不存 API key、完整 bash 命令（仅 hash/摘要）
- 团队仓库：Ratchet 补丁应走 PR（文档说明，CLI 不强制）

---

## 12. 相关文档

- [harness/testing.md](harness/testing.md) — pytest 与 benchmark
- [docs/README.md](README.md) — 文档索引  
