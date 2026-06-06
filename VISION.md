# Meris — 产品宗旨

> **做一个会自我进化的 coding agent，让使用者越用越顺手。**

Meris 的目标不是「一次配置、永远不变」的静态助手，而是随**项目**与**使用者习惯**持续变聪明的 Agent。

## 核心原则

```
Agent = Model + Harness
进化发生在 Harness，而不是换更大的模型
```

| 原则 | 含义 |
|------|------|
| **越用越顺手** | 重复任务路径变短、误操作变少、验收更准 |
| **因项目而异** | 读现有代码结构、`AGENTS.md`、`.meris/`、git 历史，不强行套用模板 |
| **因用户而异** | 从 session、PROGRESS、批准/拒绝模式里沉淀偏好 |
| **可验证的进化** | 改 Harness（规则 / skill / hook / sensor），用 benchmark 与 pytest 验证，不是只改一次 prompt |

## 模型怎么用（Harness，不是让模型猜）

多厂商能力在 **Model** 层；**选哪家、哪个型号**应写在 Harness（如 `.meris/settings.json` 的 `models` 路由）：

> **问句用便宜模型，大改用强模型** — 写进规则，而不是每次让模型自己猜。

- `ask` / 轻量检索 → 快、省  
- `plan` / `run` / 重构类任务 → 更强  
- 特殊任务（含关键词）→ `rules` 命中再切换  

这与「进化发生在 Harness」一致：路由表可审阅、可改、可进 PR，而不是黑盒 meta-prompt。

见 [docs/MODELS.md](docs/MODELS.md)（多厂商配置与 `models` 路由）。

## 进化机制（Ratchet）

1. **Instructions** — `AGENTS.md`：项目约定、路径、DoD  
2. **Skills** — `.meris/skills/*.md`：领域知识、输出格式  
3. **Rules** — `.meris/rules/*.md`：自动注入的短规则  
4. **State** — `PROGRESS.md`、`.meris/sessions/`：跨会话记忆  
5. **Sensors** — post-edit / onComplete：改完自动验收  
6. **Permissions & hooks** — 拦坏习惯、固化好流程  

Agent 犯错 → **改 Harness，不是只重试同一句 prompt**。

## 与「裸 Chat」的区别

裸 Chat 每次从零上下文开始；Meris 把**项目知识**和**使用痕迹**写回仓库里的 Harness 文件，下一任 Agent（或下一次 session）直接继承。

## 设计检验

新功能或文档改动，问一句：

> 这会让用户在**同一个项目**里**第二次**做同类任务时更省事吗？

若否，优先做 Harness / 工作流，而不是堆新工具。

## 相关

- [docs/RATCHET_DESIGN.md](RATCHET_DESIGN.md) — 自我进化（Ratchet）设计  
- [docs/RATCHET_30MIN.md](RATCHET_30MIN.md) — 30 分钟 Ratchet 闭环清单  
- [docs/DOGFOOD_7DAY.md](DOGFOOD_7DAY.md) — 7 天 Ratchet 练手  
- [ROADMAP.md](ROADMAP.md) — 功能路线图  
- [BRAND.md](BRAND.md) — 品牌与标识  
