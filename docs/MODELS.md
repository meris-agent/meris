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

> **问句用便宜模型，大改用强模型** — 写进 Harness，而不是每次让模型猜。

在 **`.meris/settings.json`** 里配置团队共享项（权限、传感器、`models` 模板等）。

模型路由以 [templates/settings.models.example.json](../templates/settings.models.example.json) 为模板：

- **`.meris/settings.json`** — 团队共享的 `models`（占位 `ep-xxxxxxxx`，可提交）
- **`.meris/settings.local.json`** — 个人覆盖（真实 `ep-...` 等，已在 `.gitignore`）

```powershell
# 个人接入点 ID 等：复制模板再改 run.model
copy templates\settings.models.example.json .meris\settings.local.json
```

`.env` 里仍需各厂商 API Key。`models` 结构示例（与模板相同）：

```json
{
  "models": {
    "byMode": {
      "ask": { "provider": "openai", "model": "gpt-4o-mini" },
      "plan": { "provider": "deepseek", "model": "deepseek-chat" },
      "run": { "provider": "deepseek", "model": "deepseek-reasoner" }
    },
    "rules": [
      {
        "name": "heavy-refactor",
        "match": { "mode": "run", "taskContains": ["重构", "refactor", "架构"] },
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514"
      }
    ]
  }
}
```

**优先级**：`rules`（从上到下第一条命中）→ `byMode[mode]` → `models.default` → 仅环境变量。

预览某条任务会选谁：

```bash
meris models route "大规模重构 auth 模块" --mode run
meris ask "..."   # 运行时日志会出现 route=byMode:ask ...
```

说明：

- 这是 **规则路由**（快、可测、无额外 LLM 调用），不是「让模型自己挑厂商」。
- 未配 `models` 时行为与以前相同：只用 `MERIS_PROVIDER` / `.env`。
- 未来可选：用便宜模型做意图分类再路由（需另开 API 调用，暂未内置）。
- 完整示例见 [templates/settings.models.example.json](../templates/settings.models.example.json)；`settings.json` 与 `settings.local.json` 的 `models` 均由此复制/对齐，local 覆盖 team 默认值。

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
