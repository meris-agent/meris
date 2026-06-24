# Meris — 多模型配置

Meris 不绑定单一厂商。通过 **`MERIS_PROVIDER`** 选择内置预设，或用 **`MERIS_BASE_URL` + `MERIS_MODEL`** 接任意 OpenAI 兼容 API。

## 快速命令

```bash
meris models list              # 预设一览 + 当前解析结果
meris models show openai       # 某厂商的 URL、默认模型、API key 变量名
meris doctor                   # 检查 key / model / 探活
```

## 内置预设

| `MERIS_PROVIDER` | 厂商 | API Key 环境变量（任选其一） |
|------------------|------|------------------------------|
| `openai` | OpenAI | `OPENAI_API_KEY` |
| `deepseek` | DeepSeek | `DEEPSEEK_API_KEY`, `LLM_API_KEY` |
| `anthropic` | Claude（原生） | `ANTHROPIC_API_KEY` — 需 `pip install meris-agent[anthropic]` |
| `gemini` | Google Gemini | `GEMINI_API_KEY`, `GOOGLE_API_KEY` |
| `glm` | 智谱 | `ZHIPU_API_KEY`, `GLM_API_KEY` |
| `moonshot` | Moonshot / Kimi | `MOONSHOT_API_KEY`, `KIMI_API_KEY` |
| `qwen` | 阿里通义 / **百炼**（DashScope OpenAI 兼容） | `DASHSCOPE_API_KEY`, `BAILIAN_API_KEY` |
| `volcengine` | **火山引擎**方舟 / 豆包 | `ARK_API_KEY`, `VOLCENGINE_API_KEY` |
| `local` | **自部署**（vLLM、Xinference、LocalAI、LiteLLM 等） | `OPENAI_API_KEY`（多数可填任意占位） |
| `ollama` | 本地 Ollama | 通常无需 key |
| `groq` | Groq | `GROQ_API_KEY` |
| `mistral` | Mistral | `MISTRAL_API_KEY` |
| `openrouter` | OpenRouter 网关 | `OPENROUTER_API_KEY` |
| `ollama` | 本地 Ollama | 通常无需 key（`http://127.0.0.1:11434/v1`） |

**别名**：`kimi`→`moonshot`，`bailian`/`aliyun`→`qwen`，`doubao`/`ark`→`volcengine`，`vllm`→`local` 等（见 `meris models list`）。

## 国内与自部署（常见问法）

### 阿里百炼

百炼控制台发的 **DashScope API Key** 与通义一致，走 OpenAI 兼容模式即可（内置预设 `qwen`，别名 `bailian`）：

```bash
export MERIS_PROVIDER=qwen
export DASHSCOPE_API_KEY=sk-...          # 百炼 / 模型服务灵积 控制台
export MERIS_MODEL=qwen-plus             # 或 qwen-max、qwen-turbo 等
# 一般无需改 MERIS_BASE_URL（默认已是 compatible-mode/v1）
```

若控制台给的是**推理接入点 ID** 或其它非标准模型名，用 `MERIS_MODEL=` 填控制台里的模型 ID。

### 火山引擎（豆包 / 方舟 Ark）

```bash
export MERIS_PROVIDER=volcengine
export ARK_API_KEY=...                   # 方舟 API Key
export MERIS_MODEL=ep-xxxxxxxx           # 控制台「推理接入点」ID，必填
# 区域不同可改 base，例如：
# export MERIS_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
```

`MERIS_MODEL` 在火山侧通常是 **`ep-...` 接入点 ID**，不是 `doubao-pro-32k` 字符串；默认值仅作占位，以控制台为准。

### 自己部署的模型

只要暴露 **OpenAI 兼容** `/v1/chat/completions`（vLLM、Xinference、LocalAI、FastChat、LiteLLM 代理等）：

```bash
export MERIS_PROVIDER=local              # 或 ollama（仅 Ollama 11434 端口）
export MERIS_BASE_URL=http://127.0.0.1:8000/v1
export MERIS_MODEL=your-model-name
export OPENAI_API_KEY=not-needed         # 本地无鉴权时可随便填
```

| 部署方式 | 建议 `MERIS_PROVIDER` | 典型 `MERIS_BASE_URL` |
|----------|----------------------|------------------------|
| Ollama | `ollama` | `http://127.0.0.1:11434/v1` |
| vLLM | `local` | `http://127.0.0.1:8000/v1` |
| Xinference | `local` | `http://127.0.0.1:9997/v1` |
| LiteLLM 网关 | `local` 或 `openai` | 你的 LiteLLM 地址 |
| 内网私有网关 | `openai` + 自定义 URL | `https://internal-gw/v1` |

**不支持**：仅提供非 OpenAI 协议的原生 SDK（需自行用 LiteLLM 等做一层兼容代理）。

## 示例

### DeepSeek

```bash
export MERIS_PROVIDER=deepseek
export DEEPSEEK_API_KEY=sk-...
```

### OpenAI

```bash
export MERIS_PROVIDER=openai
export OPENAI_API_KEY=sk-...
# 可选: export MERIS_MODEL=gpt-4o
```

### Anthropic

```bash
pip install "meris-agent[anthropic]"
export MERIS_PROVIDER=anthropic
export ANTHROPIC_API_KEY=sk-ant-...
```

### 自定义 OpenAI 兼容端点

```bash
export MERIS_PROVIDER=openai
export OPENAI_API_KEY=...
export MERIS_BASE_URL=https://your-gateway/v1
export MERIS_MODEL=your-model-id
```

## 按任务自动选模型（Harness 路由）

> **问句用便宜模型，大改用强模型** — 模型定义、策略、路由分工写进 Harness。

Harness 配置使用 **YAML**（支持 `#` 注释，IDEA 原生识别）：

| 文件 | 用途 |
|------|------|
| [templates/settings.example.yaml](../templates/settings.example.yaml) | 全量模板（权限、传感器、models…，含注释） |
| `.meris/settings.yaml` | 团队共享（可提交 Git） |
| `.meris/settings.local.yaml` | 个人覆盖（如真实 `ep-...`，已在 `.gitignore`） |

`meris init-harness .` 会生成 `.meris/settings.yaml`。仍支持旧版 `settings.json` / `settings.local.json`（自动兼容，YAML 优先）。

```powershell
# 个人覆盖示例
notepad .meris\settings.local.yaml
```

`.env` 里保留各 profile 对应厂商的 API Key。`models` 段 YAML 示例：

```yaml
models:
  profiles:
    fast:
      provider: deepseek
      model: deepseek-chat
      hint: 只读问答、解释、轻量 plan
    code:
      provider: volcengine
      model: ep-xxxxxxxx
      hint: 改代码、跑测试、实现功能
  byMode:
    ask:
      profile: fast
    run:
      strategy: dynamic
      candidates: [fast, code, heavy]
      defaultProfile: fast
  dynamic:
    enabled: false
    router:
      provider: deepseek
      model: deepseek-chat
    reRoute: onMutation
```

完整字段说明见 **`templates/settings.example.yaml`** 内 `#` 注释。

### 三层分工

| 层 | 字段 | 作用 |
|----|------|------|
| **模型池** | `models.profiles` | 每个 profile 定义一次 provider / model / hint |
| **策略** | `models.byMode` / `models.rules` | 每个 mode 用哪个 profile，或动态候选集 |
| **路由引擎** | `models.dynamic` | 全局开关 + 便宜的路由模型（分类器） |

### profiles — 模型池

每个 key（如 `fast`、`code`）是一套可复用的模型连接：

| 字段 | 必填 | 含义 |
|------|------|------|
| `provider` | 是 | 预设 id，见 `meris models list` |
| `model` | 是 | 模型名或火山 `ep-...` 接入点 |
| `hint` | 否 | 写给路由模型看的说明（动态路由时帮助选型） |
| `baseUrl` | 否 | 覆盖该 profile 的 API 地址 |

### `byMode` — 每个 CLI mode 的策略

| 写法 | 含义 |
|------|------|
| `{ "profile": "fast" }` | **静态**：该 mode 始终用此 profile |
| `{ "strategy": "dynamic", "candidates": [...], "defaultProfile": "fast" }` | **动态**：运行中由路由模型从候选里选（需 `dynamic.enabled`） |
| `{ "provider": "...", "model": "..." }` | **旧写法**，仍兼容，等价于内联 profile |

`candidates` 必须是 `profiles` 里已有的 id 列表。`defaultProfile` 是路由失败或未开动态时的兜底。

### `rules` — 任务级覆盖（静态，优先级最高）

| 字段 | 含义 |
|------|------|
| `match.mode` | 限定 `ask` / `plan` / `run` |
| `match.taskContains` | 任务文本包含任一关键词即命中 |
| `match.taskRegex` | 正则匹配任务 |
| `profile` | **推荐**：引用 `profiles` 中的 id |
| `provider` + `model` | **旧写法**，仍兼容 |

**优先级**：`rules`（第一条命中）→ `byMode[mode]` → `models.default` → 仅环境变量。

### `dynamic` — 运行时按需切换

仅在 **`dynamic.enabled: true`** 且某 mode 为 **`strategy: dynamic`** 时，每轮（或按 `reRoute`）多调一次路由模型，从该 mode 的 `candidates` 里选一个 profile。

| 字段 | 含义 |
|------|------|
| `enabled` | 总开关 |
| `router` | **路由模型**（分类器），单独指定 `{ provider, model }`，不是候选之一 |
| `reRoute` | `everyTurn`：每轮都问；`onMutation`：首轮 + 上一轮有写文件/bash 时才问（省调用） |

`router` 是对象的原因：它和 profile 一样是「连哪家 API、用哪个 model」，但角色是**调度员**，与干活的 profile 分开配置。

日志示例：

```text
[meris] model route=dynamic:code provider=volcengine model=ep-... (needs code edits)
```

预览静态路由（不含动态 LLM 判断）：

```bash
meris models route "大规模重构 auth 模块" --mode run
meris ask "..."   # 静态 mode 日志: route=byMode:ask:fast
```

### 个人覆盖示例

团队 `settings.yaml` 用占位 `ep-xxxxxxxx`；本机 `settings.local.yaml` 只覆盖必要字段：

```yaml
models:
  profiles:
    code:
      provider: volcengine
      model: ep-你的接入点
  dynamic:
    enabled: true
```

深合并后继承团队的 `byMode`、`rules`、`router` 等。

### 说明

- **静态**（`profile` / `rules`）：快、可测、可 PR review，默认推荐。
- **动态**（`strategy: dynamic` + `dynamic.enabled`）：多一次路由 API 调用，适合 `run` 里「先读后写、按需升档」。
- 未配 `models` 时行为不变：只用 `MERIS_PROVIDER` / `.env`。
- 旧配置（`byMode` 直接写 `provider`/`model`）无需迁移即可继续用；新仓库建议用 `profiles` + `profile` 引用。

## 自动推断

未设置 `MERIS_PROVIDER` 时，按已配置的 API key / `MERIS_BASE_URL` 推断（例如仅有 `DEEPSEEK_API_KEY` → DeepSeek；仅有 `OPENAI_API_KEY` → OpenAI）。

## Windows

```powershell
$env:MERIS_PROVIDER = "deepseek"
$env:DEEPSEEK_API_KEY = "sk-..."
```

或复制 [.env.example](../.env.example) 为 `.env`。

## 相关

- [LOCAL_SETUP.md](LOCAL_SETUP.md) — 本机开发环境  
- [README.md](../README.md) — Quick start
