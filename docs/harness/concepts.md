# Vibe Coding 概念：工作区、项目、Skill、MCP

> **改 Agent UI / 设置页 / Harness 前先读本文**，避免把 cwd、Skill、MCP 混在同一套文案里。  
> 与 [routing.md](routing.md)（顶栏下拉 = cwd 路由）、README North star（Harness 分层）配套。

## 一张表

| 概念 | 含义 | 存在位置 | Agent 怎么用 |
|------|------|----------|--------------|
| **工作区（Workspace）** | UI 里**当前在操作哪个文件夹**（cwd） | 顶栏项目下拉、`~/.meris/ui/workspace-roots.json` | 决定读写文件、用哪套 `.meris/`、session 落在哪 |
| **项目（Project / Harness）** | **该 cwd 上的 Agent 配置与记忆** | `AGENTS.md`、`.meris/*`、`PROGRESS.md` | 规则、技能、MCP、模型路由、会话都挂在这个根上 |
| **Rule** | 短规则，可自动注入 | `.meris/rules/*.md` | `inject: always` 进 system prompt；其余索引里按需 `read_file` |
| **Skill** | 按需加载的「说明书」（格式、流程、领域知识） | `.meris/skills/*.md` + `~/.meris/skills/*.md` | 默认**不**进 prompt；`load_skill` 或 Composer `@` 挂上 |
| **MCP** | 外挂工具服务（DB、浏览器、自定义 API） | `settings.yaml` 的 `mcpServers` 或 UI 的 `.meris/ui/mcp-servers.json` | 运行时注册为 `mcp_{server}_{tool}` |
| **CLI 命令** | 终端子命令 | `meris` CLI | 给人 / 设置页速查 / ▶ 一键运行；**不是** Skill |

## 工作区 ≠ 项目

```text
┌─────────────────────────────────────────────────────────┐
│  Agent UI 顶栏「工作区」下拉  =  切换 cwd（多根目录）      │
└───────────────────────────┬─────────────────────────────┘
                            │ 选中某一个路径
                            ▼
┌─────────────────────────────────────────────────────────┐
│  项目（Harness）= 该路径下的 AGENTS.md + .meris/ + …     │
│  · rules / skills / sessions / ratchet / plan           │
│  · MCP 配置（随此 cwd 的 .meris 生效）                    │
└─────────────────────────────────────────────────────────┘
```

- **工作区**：像 VS Code「打开的文件夹」— 可在 vault 根与 `meris/` 子仓库之间切换（见 `.meris/rules/workspace.md`）。
- **项目**：Meris 所称的 **Harness 附着点** — 有 `init-harness` 的那一个仓库根。
- **禁止混用文案**：Skill 列表、MCP 设置页不要用「工作区 Tab」；应写「当前项目根下的 `.meris/skills/`」。

### 父子目录示例（笔记库 + meris 子仓库）

| 任务 | 正确 cwd（项目根） |
|------|-------------------|
| 改 Meris 源码、pytest、`meris harness check` | `meris/` git 仓库根 |
| 改 Markdown 笔记 `Articles/` | 笔记库根（vault 根） |

在 vault 根跑 `meris run` 改 README 可能写成 `meris/README.md` 并被 block — **先切顶栏 cwd，再改 Harness**。

## Harness 分层（进化写在哪）

Harness 分层（摘要）：

| 层 | 路径 | 注入 / 使用 |
|----|------|-------------|
| Instructions | `AGENTS.md` | 常驻 system prompt |
| Rules | `.meris/rules/` | 可 always 或 on-demand |
| Skills | `.meris/skills/` | on-demand（`load_skill`） |
| State | `PROGRESS.md`、`.meris/sessions/` | 跨会话 |
| Sensors / hooks | `settings.yaml` | 改完 / 提交时验收 |
| MCP | `mcpServers` | 工具层，与 Skill 正交 |

Agent 犯错 → **改 Harness 文件**，不是只重试同一句 prompt。

## Skill vs Rule vs MCP vs CLI

| | Skill | Rule | MCP | CLI |
|---|-------|------|-----|-----|
| **典型内容** | Plan 格式、发布检查清单、安全审查步骤 | 「不要改 generated」「cwd 表」 | 连 Postgres、开浏览器 | `meris doctor` |
| **厚度** | 可长 | 宜短 | 外部进程 | 无 prompt |
| **Composer** | `@` 选择挂上 | （不直接选） | （在设置里配，不在 Composer 重配） | 设置页「CLI 命令」速查 |
| **设置页** | 技能 | 规则 | MCP | CLI 命令（独立页） |

**配置进设置中心，聊天区只管聊天**（设置页与 Composer 职责分离）。

## Agent UI 控件对照

| UI | 绑定的概念 | 不要误解成 |
|----|------------|------------|
| 顶栏项目下拉 | cwd / 项目根切换（**仅项目文件夹**） | Skill 分类、模型选择 |
| 左栏「文件」 | **当前项目**的文件树 | 多项目列表、Skill 列表 |
| Composer `mode` | ask / plan / run | 工作区 |
| 模型 `Auto` | `models` 路由 | cwd |
| Composer `@` | 挂 Skill 内容 | 换工作区 |
| Composer `#` | 挂仓库内文件 | Skill |
| 设置 → 技能 | 当前项目 `.meris/skills/` + 全局 `~/.meris/skills/` | 顶栏 cwd 列表 |
| 设置 → MCP | 当前项目的 MCP 配置 | Skill |
| 设置 → 规则 | `.meris/rules/` | 工作区列表 |

详见 [routing.md](routing.md)「Agent Window 与路由」表。

## 技能导入

- **目标**：复制到 **当前 cwd** 的 `.meris/skills/`（属于当前项目 Harness）。
- **来源**：用户选的任意本地目录；支持 `name/SKILL.md` 或 `*.md`。
- **与顶栏无关**：导入不改变 workspace roots，只改当前项目下的 skills 文件。

## 实现命名（代码维护）

| 用户文案 | 建议代码/API | 避免 |
|----------|--------------|------|
| 已安装技能 | `source: "installed"` | `source: "workspace"`（与 cwd 工作区混淆） |
| 全局技能 | `source: "global"` | — |
| 内置模板 | `source: "builtin"` | — |
| 当前项目根 | `cwd` / `activeRoot` | 在 Skill 上下文里写 `workspace` |
| 本次任务范围 | `taskScope` / `taskScopeSelected` | 与 cwd 混用（scope 可多选，cwd 唯一） |

## 多仓库（task scope）

- **已注册项目**：顶栏 / ⋯ 列表（`workspace-roots.json` 或扩展 globalState）。  
- **task scope**：左栏「本次涉及」勾选，持久化 `~/.meris/ui/task-scope.json`。  
- **cwd**：写盘与左栏文件树仍只有一个；run 只改 cwd，scope 用于跨项目只读探索提示。

详见 [multi-repo.md](multi-repo.md)。

## Meris Cloud

**Meris Cloud** 为闭源公网 SaaS，不在本仓库。本地使用 `meris ui` / VS Code 扩展；勿将单机 UI 进程直接暴露公网（会串会话）。托管版见 [CLOUD.md](../../CLOUD.md)。

## 相关

- [multi-repo.md](multi-repo.md) — task scope 与跨项目流程
- [git-workflow.md](git-workflow.md) — 改动面板与 Ship 流程
- [routing.md](routing.md) — cwd 与 model 路由
- [architecture.md](architecture.md) — 包布局
- `.meris/rules/workspace.md` — vault / meris 双 cwd
- [multi-repo.md](multi-repo.md) — 多仓库 task scope
