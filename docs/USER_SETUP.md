# Meris 入门指南

> **English quick start:** [README](../README.md)  
> **模型配置大全:** [MODELS.md](MODELS.md)

从零到在自己的项目里运行 `meris ask` / `plan` / `run`。

---

## 你需要准备

| 项 | 要求 |
|----|------|
| Python | **3.11+** |
| 终端 | PowerShell / bash / IDE 集成终端 |
| LLM | 任一厂商 API Key，或本机 Ollama / vLLM 等 **OpenAI 兼容** 端点 |
| 项目目录 | 要用 Meris 问答或改代码的**仓库根目录**（`init-harness` 所在 cwd） |

Meris **不附带模型**，只连接你配置的 API。

---

## 1. 安装

```bash
pip install meris-agent
# 可选
pip install "meris-agent[tui]"        # 交互界面 meris tui
pip install "meris-agent[anthropic]"  # Claude 原生 API
```

验证：

```bash
meris version
```

---

## 2. 配置模型

任选一种方式。

### 方式 A — 项目根 `.env`（推荐）

在项目根或 clone 目录：

```bash
cp .env.example .env   # 从仓库复制模板后改
```

编辑 `.env`（**不要提交**，已在 `.gitignore`）：

```env
MERIS_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxxxxxxx
```

换厂商只改两行。查看预设与变量名：

```bash
meris models list
meris models show qwen
meris models show local     # 自部署
```

### 方式 B — 系统环境变量

**Linux / macOS：**

```bash
export MERIS_PROVIDER=openai
export OPENAI_API_KEY=sk-...
```

**Windows PowerShell（当前窗口）：**

```powershell
$env:MERIS_PROVIDER = "openai"
$env:OPENAI_API_KEY = "sk-..."
```

### 方式 C — 本机自部署（无云 Key）

```env
MERIS_PROVIDER=ollama
# 或 vLLM：
# MERIS_PROVIDER=local
# MERIS_BASE_URL=http://127.0.0.1:8000/v1
# MERIS_MODEL=your-model
```

---

## 3. 初始化 Harness

在**目标项目根**执行：

```bash
cd /path/to/your-repo
meris init-harness .
```

会生成（若不存在）：

| 文件 | 作用 |
|------|------|
| `AGENTS.md` | 项目规则、目录说明、验收标准 |
| `PROGRESS.md` | 跨会话进度 |
| `.meris/settings.yaml` | 工具权限、传感器、MCP、models（见 `templates/settings.example.yaml`） |

请根据项目**编辑 `AGENTS.md`**（路径、测试命令、禁止操作）。模板只是起点。

### 个人 models 覆盖

团队仓库里的 `.meris/settings.yaml` 可提交占位模型。在本机创建 **`.meris/settings.local.yaml`**（已 gitignore），只写要覆盖的字段：

```yaml
models:
  profiles:
    code:
      provider: volcengine
      model: ep-你的接入点
  dynamic:
    enabled: true
```

深合并保留团队的 `byMode`、`rules` 等 — 详见 [MODELS.md](MODELS.md)。

可选：扫描项目生成规则提案：

```bash
meris ratchet learn --init
meris ratchet review
```

---

## 4. 自检

```bash
meris doctor
```

期望：API key、Model、API probe 为 **ok**；缺 `AGENTS.md` 等为 **warn** 时运行 `init-harness`。

---

## 5. 开始使用

```bash
meris ask "认证逻辑在哪个文件？"
meris plan "给 session 加 prune 子命令，3 条 checkbox"
meris run --approve "修 tests/test_xxx.py 里失败的用例"
```

| 场景 | 命令 |
|------|------|
| 只问不改 | `meris ask` |
| 只要计划 | `meris plan` |
| 自动改代码 | `meris run` 或 `meris run --approve` |
| 图形界面 | `meris tui` 或 VS Code 扩展 |
| 跑完沉淀规则 | `meris run --ratchet "..."` |

**cwd 很重要**：在**目标项目根**执行。多根目录（如笔记库 + 嵌套代码仓库）见 [harness/concepts.md](harness/concepts.md)。

---

## 常见厂商速查

| 厂商 | `MERIS_PROVIDER` | Key 环境变量 | 备注 |
|------|------------------|--------------|------|
| DeepSeek | `deepseek` | `DEEPSEEK_API_KEY` | |
| OpenAI | `openai` | `OPENAI_API_KEY` | |
| Claude | `anthropic` | `ANTHROPIC_API_KEY` | 需 `[anthropic]` |
| 阿里百炼 / 通义 | `qwen` | `DASHSCOPE_API_KEY` | 别名 `bailian` |
| 火山 / 豆包 | `volcengine` | `ARK_API_KEY` | `MERIS_MODEL=ep-...` |
| 智谱 | `glm` | `ZHIPU_API_KEY` | |
| Kimi | `moonshot` | `MOONSHOT_API_KEY` | |
| 本地 Ollama | `ollama` | 通常不需要 | |
| 自部署 vLLM 等 | `local` | 可填占位 | 必设 `MERIS_BASE_URL` |

---

## 团队协作

**建议提交到 git：**

- `AGENTS.md`、`.meris/settings.yaml`、`.meris/rules/`、`.meris/skills/`

**不要提交：**

- `.env`、`.meris/settings.local.yaml`
- `.meris/sessions/`、`.meris/plan/`、`.meris/ratchet/`

**给新成员的三步：**

1. `pip install meris-agent`
2. 复制 `.env.example` → `.env` 填 Key
3. `cd 项目 && meris doctor && meris ask "..."`

可在项目 README 里链接本文或 [MODELS.md](MODELS.md)。

---

## 可选：Rust 加速

```bash
meris native build
meris native status
```

| 变量 | 含义 |
|------|------|
| `MERIS_NATIVE` | 默认 auto：有二进制则启用 |
| `MERIS_NATIVE=0` | 强制纯 Python |

详见 [NATIVE_BINARY.md](NATIVE_BINARY.md) · [LOCAL_SETUP.md](LOCAL_SETUP.md)（贡献者本机构建）。

---

## 常见问题

| 现象 | 处理 |
|------|------|
| `doctor` API 401 | Key 错或 `MERIS_BASE_URL` 不匹配；`meris models show <厂商>` |
| 改了 `.env` 不生效 | 新开终端；确认 cwd 下有 `.env` |
| Agent 改错目录 | cwd 改到项目根；补 `AGENTS.md` 路径表 |
| 不绑 DeepSeek | 设 `MERIS_PROVIDER` 即可换任意厂商 |

---

## 下一步

| 目标 | 文档 |
|------|------|
| 命令大全 | [README](../README.md) |
| Harness 概念 | [harness/concepts.md](harness/concepts.md) |
| Ratchet 原理 | [RATCHET_DESIGN.md](RATCHET_DESIGN.md) |
| 贡献代码 | [CONTRIBUTING.md](../CONTRIBUTING.md) |
| 文档索引 | [docs/README.md](README.md) |
