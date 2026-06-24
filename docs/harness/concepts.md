# Harness 核心概念：工作区、项目、Skill、MCP

> 使用 Agent UI、编写 Harness 或贡献 UI 代码前建议先读本文，避免把 cwd、Skill、MCP 混在同一套文案里。  
> 配套：[routing.md](routing.md)（cwd 与模型路由）、[README 宗旨](../README.md#meris-agent)。

## 「Harness」指什么（避免混淆）

Meris 文档里的 **Harness** 是 [agent harness](https://openai.com/index/harness-engineering/)（模型外的项目约束层），**产品名是 Meris**，不是叫 Harness 的软件。

| 名称 | 路径 / 项目 | 含义 |
|------|-------------|------|
| **项目 Harness** | 各仓库根：`AGENTS.md`、`.meris/`、`PROGRESS.md` | 用户可编辑的规则、技能、权限、会话 |
| **Harness 引擎** | 本 pip 包：`meris/harness/` | 读取项目文件、驱动 agent loop |
| **Harness 文档** | `docs/harness/` | 机制说明（`init-harness` 可拷到用户项目） |

**不是同一事物：**

- [OpenHarness](https://github.com/HKUDS/OpenHarness) — 独立开源 agent 框架，与 Meris **无隶属关系**
- [Harness.io](https://www.harness.io/) — DevOps CI/CD 平台，与 AI agent harness **无关**（英文同词）

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

- **工作区**：像 VS Code「打开的文件夹」— 可在多个已注册根目录之间切换。
- **项目**：Meris 所称的 **Harness 附着点** — 运行 `init-harness` 的那一个仓库根。
- **禁止混用文案**：Skill 列表、MCP 设置页不要用「工作区 Tab」；应写「当前项目根下的 `.meris/skills/`」。

### 父子目录示例（外层文件夹 + 嵌套 git 仓库）

常见于「笔记库 / 文档根 + 内嵌代码仓库」：

| 任务 | 正确 cwd（项目根） |
|------|-------------------|
| 改内嵌代码仓库、跑 pytest | 内层 git 仓库根（如 `my-app/`） |
| 改外层 Markdown / 文档 | 外层根目录 |

在外层 cwd 跑 `meris run` 改内层 README 可能路径错误 — **先切换到目标项目根，再执行任务**。

完整示例模板：[examples/ainote-vault/](../examples/ainote-vault/README.md)。

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
- [examples/ainote-vault/](../examples/ainote-vault/) — 笔记库 + 嵌套代码仓库示例
- [multi-repo.md](multi-repo.md) — 多仓库 task scope
