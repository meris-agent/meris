# Meris — 给他人使用的配置指南

> 给同事、朋友或开源用户：从零到能在**自己的项目**里跑 `meris ask/plan/run`。  
> 模型厂商大全见 [MODELS.md](MODELS.md)。

---

## 他们需要准备什么

| 项 | 要求 |
|----|------|
| Python | **3.11+** |
| 终端 | PowerShell / bash / Cursor 集成终端均可 |
| LLM | 任一厂商 API Key，或本机 Ollama / vLLM 等 **OpenAI 兼容** 地址 |
| 项目目录 | 要用 Meris 改代码或问答的**那个仓库根目录**（含 `AGENTS.md` 的 cwd） |

Meris **不附带模型**，只连接你配置的 API。

---

## 第一步：安装 Meris

```bash
pip install meris-agent
# 可选
pip install "meris-agent[tui]"        # 交互界面 meris tui
pip install "meris-agent[anthropic]"  # 仅用 Claude 原生 API 时
```

验证：

```bash
meris version
```

---

## 第二步：配置模型（三选一）

### 方式 A — 项目根 `.env`（推荐）

在**常用项目根**或 Meris  clone 根目录：

```bash
cp .env.example .env   # 从仓库复制模板后改
```

编辑 `.env`（**不要提交到 git**，已在 `.gitignore`）：

```env
MERIS_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxxxxxxx
```

换厂商只改两行：`MERIS_PROVIDER` + 对应 Key 变量名。查看厂商与变量名：

```bash
meris models list
meris models show qwen      # 示例：阿里百炼 / 通义
meris models show volcengine
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

持久化可用系统「环境变量」设置，或把上面两行写入 PowerShell `$PROFILE`。

### 方式 C — 仅本机自部署（无云 Key）

```env
MERIS_PROVIDER=ollama
# 或 vLLM：
# MERIS_PROVIDER=local
# MERIS_BASE_URL=http://127.0.0.1:8000/v1
# MERIS_MODEL=your-model
```

---

## 第三步：在「他的项目」里初始化 Harness

```bash
cd /path/to/his-repo
meris init-harness .
```

会生成（若不存在）：

| 文件 | 作用 |
|------|------|
| `AGENTS.md` | 项目规则、目录说明、验收标准 |
| `PROGRESS.md` | 跨会话进度 |
| `.meris/settings.json` | 工具权限、传感器、MCP 等 |

维护者应**根据项目改 `AGENTS.md`**（路径、测试命令、禁止操作）。模板只是起点。

可选：扫描项目生成规则提案：

```bash
meris ratchet learn --init
meris ratchet review
```

---

## 第四步：自检

```bash
cd /path/to/his-repo
meris doctor
```

期望：API key、Model、API probe 为 **ok**；缺 `AGENTS.md` 等为 **warn** 时补 `init-harness`。

---

## 第五步：开始使用

```bash
meris ask "认证逻辑在哪个文件？"
meris plan "给 session 加 prune 子命令，3 条 checkbox"
meris run --approve "修 tests/test_xxx.py 里失败的用例"
```

| 场景 | 建议命令 |
|------|----------|
| 只问不改 | `meris ask` |
| 只要计划 | `meris plan` |
| 自动改代码 | `meris run` 或 `meris run --approve` |
| 图形界面 | `meris tui` |
| 跑完后沉淀规则 | `meris run --ratchet "..."` |

**cwd 很重要**：必须在**目标项目根**执行，不要在 Obsidian vault 父目录跑 Meris 子目录里的代码任务（见 `AGENTS.md` / `.meris/rules/workspace.md`）。

---

## 常见厂商速查（给别人复制）

| 他用谁 | `MERIS_PROVIDER` | Key 环境变量 | 备注 |
|--------|------------------|--------------|------|
| DeepSeek | `deepseek` | `DEEPSEEK_API_KEY` | |
| OpenAI | `openai` | `OPENAI_API_KEY` | |
| Claude | `anthropic` | `ANTHROPIC_API_KEY` | 需 `[anthropic]` 扩展 |
| 阿里百炼 / 通义 | `qwen` | `DASHSCOPE_API_KEY` | 别名 `bailian` |
| 火山 / 豆包 | `volcengine` | `ARK_API_KEY` | `MERIS_MODEL=ep-...` 接入点 ID |
| 智谱 | `glm` | `ZHIPU_API_KEY` | |
| Kimi | `moonshot` | `MOONSHOT_API_KEY` | |
| 本地 Ollama | `ollama` | 通常不需要 | |
| 自部署 vLLM 等 | `local` | `OPENAI_API_KEY` 可填占位 | 必设 `MERIS_BASE_URL` |

覆盖默认模型或区域：

```env
MERIS_MODEL=qwen-max
MERIS_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
```

---

## 团队 / 开源仓库怎么交接

**建议提交到 git：**

- `AGENTS.md`、`PROGRESS.md`（若希望共享进度）
- `.meris/settings.json`（权限、DoD、MCP 配置）
- `.meris/rules/`、`.meris/skills/`（项目规则）

**不要提交：**

- `.env`（含 API Key）
- `.meris/sessions/`、`.meris/ratchet/events.jsonl`（本地运行时，见仓库 `.gitignore`）

**给新同事的一句话：**

1. `pip install meris-agent`  
2. 复制 `.env.example` → `.env` 填 Key  
3. `cd 项目 && meris doctor && meris ask "..."`  

可在项目 `README` 里链到本文或 [MODELS.md](MODELS.md)。

---

## 常见问题

| 现象 | 处理 |
|------|------|
| `doctor` API 401 | Key 错或 `MERIS_BASE_URL` 与厂商不匹配；`meris models show <厂商>` |
| 改了 `.env` 不生效 | 在新终端重开，或确认 cwd 下有 `.env`（Meris 从 cwd / 包目录加载） |
| Agent 改错目录 | cwd 改到项目根；补 `AGENTS.md` 路径表 |
| 只有 DeepSeek 文档 | 设 `MERIS_PROVIDER` 即可换厂商，不绑 DeepSeek |
| 双击 `meris-rs.exe` 无界面 | 用终端命令 `meris`，不是 GUI 安装包 |

---

## 相关文档

- [MODELS.md](MODELS.md) — 全厂商与自部署  
- [README.md](../README.md) — 命令表与 Harness 说明  
- [RATCHET_30MIN.md](RATCHET_30MIN.md) — 进化闭环练手（进阶）  
- [LOCAL_SETUP.md](LOCAL_SETUP.md) — 维护者本机 Rust / VS Code 扩展
