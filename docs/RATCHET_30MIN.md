# Ratchet 30 分钟闭环清单

> **目标**：在 **Meris 仓库根**（含 `pyproject.toml` 的目录）走通一次完整闭环，并用 benchmark 证明「Harness 补丁后更省事」。  
> 对应宗旨：[VISION.md](../VISION.md) · 设计：[RATCHET_DESIGN.md](RATCHET_DESIGN.md)

**检验句**：应用补丁后，第二次做同类任务（尤其 `plan_smoke`）是否更少踩坑？

---

## 开始前（1 分钟）

```powershell
cd <meris-repo>    # 例如 d:\personal\obsidian\AINote\meris
meris doctor
```

确认：

- `cwd` 是 **git 仓库根**，不是 Obsidian vault 父目录
- API key 已配置（若要走 **路径 B：analyze**）

---

## 0′–5′ 基线（可验证进化的起点）

```powershell
pytest tests/ -m "not integration" -q
meris benchmark run
meris ratchet status --cwd .
```

在 `PROGRESS.md` 末尾追加（示例）：

```markdown
## Ratchet 闭环 @YYYY-MM-DD
- Baseline benchmark: read_hello / list_tools / plan_smoke → 记下 pass/fail
- Pending proposals: (status 输出)
```

| 验收 | 说明 |
|------|------|
| pytest 全绿 | 仓库未被破坏 |
| benchmark 有结果 | 记下 3 个 task 各自 pass/fail，后面要对比 |

---

## 5′–12′ 产生一条 **pending** 提案

当前若无 pending（`meris ratchet list` 为空），任选 **一条路径**。

### 路径 A — 规则引擎（推荐首次，**不需 LLM**）

适合 `plan_smoke` 因缺少 `- [ ]` 而失败的项目。

```powershell
meris benchmark run --filter plan_smoke
```

若该 task **fail**（detail 含 `missing: [ ]`）：

```powershell
meris ratchet scan --cwd .
meris ratchet list --cwd .
```

应出现 `L-format` 类提案，`verify` 含 `meris benchmark run --filter plan_smoke`。

若 **pass**（说明 rules/skills 已足够严）：改走路径 B，或见 [附录 A](#附录-a-仍无-pending-时)。

### 路径 B — LLM analyze（需 API）

基于最近一次失败 session：

```powershell
meris ratchet analyze --last-fail --cwd .
meris ratchet list --cwd .
```

预览 prompt（不调用模型）：

```powershell
meris ratchet analyze --dry-run --cwd .
```

| 验收 | 说明 |
|------|------|
| `list` 至少 1 条 `pending` | 记下 `ID`（如 `ratchet-20260604-140729`） |

---

## 12′–18′ 审阅（Human-in-the-loop）

```powershell
meris ratchet show <ID> --cwd .
```

检查：

1. **Target** 仅在 `.meris/rules/` 或 `.meris/skills/`（或你显式 `--force-agents` 的 `AGENTS.md`）
2. **Content** 里有 `<!-- ratchet:... -->` 标记，避免重复 append
3. **Verify** 是否合理（规则类常为 `meris benchmark run --filter plan_smoke`）

交互审阅（逐条确认）：

```powershell
meris ratchet review --cwd .
# 或指定 ID
meris ratchet review <ID> --cwd .
```

不想应用：

```powershell
meris ratchet reject <ID> --cwd .
```

| 验收 | 说明 |
|------|------|
| 你理解补丁在改什么 | 符合 VISION：改 Harness，不是改 Python 源码 |
| `show` 内容无敏感信息 | 不应出现 API key、完整 bash |

---

## 18′–25′ 应用 + 验证

```powershell
meris ratchet apply <ID> --cwd . --verify
```

`--verify` 会执行提案里的 verify（目前主要支持以 `meris benchmark` 开头的命令）。

再跑全量 benchmark 对比基线：

```powershell
meris benchmark run
meris ratchet status --cwd .
```

| 验收 | 说明 |
|------|------|
| `Applied → ...` | 目标文件已 append/create |
| `plan_smoke` 由 fail→pass（路径 A）或同类任务改善 | **闭环核心证据** |
| `Pending proposals: 0` | 已归档到 `.meris/ratchet/applied/` |

若 verify 后仍 fail：

```powershell
meris ratchet revert <ID> --cwd .
```

手动编辑 Harness 后重新 `scan` 或 `analyze`，不要留着半套规则。

---

## 25′–30′ 写回记忆 + 日常习惯

```powershell
meris doctor
```

更新 `PROGRESS.md`：

```markdown
## Ratchet 闭环 @YYYY-MM-DD（完成）
- Applied: <ID> → <path> (<lesson>)
- After benchmark: plan_smoke pass/fail, ...
- 第二次同类任务预期: （一句话）
```

可选：用 Ratchet 摘要行（若你启用了 memory 裁剪）：

```powershell
meris run --ratchet "noop: 仅触发 post-run profile+scan"   # 或下次真实任务加 --ratchet
```

**日常入口**（dogfood）：

```powershell
meris run --ratchet --approve "你的真实小任务"
# 失败后
meris ratchet scan
meris ratchet review --verify
```

---

## 闭环示意图

```
benchmark / run 失败
       ↓
events.jsonl（自动）
       ↓
scan（规则） 或  analyze（LLM）
       ↓
proposals/<id>.json（pending）
       ↓
show → review → apply [--verify]
       ↓
.meris/rules|skills/*.md 更新
       ↓
benchmark 再跑 → PROGRESS 记录
```

---

## 附录 A：仍无 pending 时

| 情况 | 做法 |
|------|------|
| `plan_smoke` 已 pass | 路径 B：`analyze --last-fail`；或先 `meris run` 制造一次 dod_failed 再 scan |
| `scan` 无输出 | `meris ratchet status` 看 7 天内是否有 events；无则先跑一次会失败的 benchmark 或 `run` |
| analyze 0 条提案 | 看 `--dry-run` prompt；收紧 task 或换 `--session-id <id>` |
| 只想练手 | 复制 [examples/ainote-vault](examples/ainote-vault) 到新目录，`init-harness` 后重走本清单 |

---

## 附录 B：你本仓当前状态（参考）

最近一次 analyze 提案 `ratchet-20260604-140729`（`L-read-code-first`）**已 applied** 到 `.meris/rules/workspace.md`，故 `list` 可能为空——正常。

若要**再练一遍**路径 A：在测试用临时目录操作，或临时移除某条 `<!-- ratchet:L-format -->` 后跑 `plan_smoke`（仅本地实验，勿提交 `.meris/` 运行时文件）。

---

## 完成后仍缺的「宗旨项」（不在 30 分钟内）

- GitHub Release / PyPI 发布 → [ROADMAP.md](../ROADMAP.md)
- TUI Ratchet 面板、`L-perm` / `L-dod` 规则 → [RATCHET_DESIGN.md §10](RATCHET_DESIGN.md)
- 7 天 [DOGFOOD_7DAY.md](DOGFOOD_7DAY.md) 全表

---

## 相关

- [DOGFOOD_7DAY.md](DOGFOOD_7DAY.md) — 7 天习惯养成  
- [VISION.md](../VISION.md) — 产品宗旨
