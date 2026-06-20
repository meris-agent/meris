# 项目进度

## 已完成
- [x] P1–P4 + 阶段 A（doctor、permissions、plan、interrupt、git_commit、CI）
- [x] **阶段 B（v0.4.0）** — spec、session、hooks、benchmark
- [x] **阶段 C（v0.5.0）** — token 压缩、Anthropic、MCP extras、TUI 面板
- [x] **阶段 D（v0.6.0）** — meris-rs、BRAND、VS Code/Cursor 扩展
- [x] **Ratchet** — scan/analyze + digest/insights（`575d619`）
- [x] **Phase E（E1–E6）** — 见 [docs/PLAN_PHASE_E.md](docs/PLAN_PHASE_E.md)

## 线路 B — Dogfood（当前）

见 [docs/ROUTE_B_DOGFOOD.md](docs/ROUTE_B_DOGFOOD.md) · `.env.example` 推荐 `MERIS_NATIVE_LOOP=auto`

- [x] release workflow 验证 + `install_meris_rs_from_ci.ps1`
- [x] env 就绪（`MERIS_NATIVE_LOOP=auto` · native status 全 True · doctor 全绿）
- [x] live benchmark Route B 3 task 标准（`read_hello` + `docs_smoke` + `list_tools`）
- [ ] 日常真实任务 dogfood（1–2 周）— `meris dogfood` · [`docs/DOGFOOD_DAILY.md`](docs/DOGFOOD_DAILY.md)
- [x] Ratchet 30 分钟闭环（2026-06-07 · 见下方）

## Phase G — Codex CLI 对标（✅ 完成）

见 [docs/PLAN_PHASE_G.md](docs/PLAN_PHASE_G.md) · 发版 [docs/RELEASE_v0.0.2.md](docs/RELEASE_v0.0.2.md)

- [x] **G1** — Codex 风格 `sandbox.preset`（workspace-write 默认 · network isolated）
- [x] **G2** — network allowlist（命令级 + bwrap share-net）
- [x] **G3** — 平台矩阵 + doctor Codex preset 提示
- [x] **G4** — Route B 完成标准（`.env` 默认 auto · live 3 task · doctor native loop）
- [x] **G5** — E0 发版 `v0.0.2`（Phase G 完整 · Route B 就绪）
- [x] **G6** — macOS Seatbelt spike + **G6.2 MVP**（`sandbox-exec` · read-only / workspace-write）

## Phase I — Vibe Coding 对标（✅ I1–I8 + I+）

见 [docs/PLAN_PHASE_I.md](docs/PLAN_PHASE_I.md) · 扩展 `v0.3.0`

- [x] Plan 勾选智能回写（`meris plan-sync` · 保留标题/正文）
- [x] Parallel 多任务 JSONL 事件流 + UI 分栏
- [x] 功能优先级三问 → `.meris/rules/feature-prioritization.md`

## Phase J — TRAE 对标 UI（✅ J1–J7）

见 [docs/PLAN_PHASE_J.md](docs/PLAN_PHASE_J.md)

- [x] 设置中心 overlay（通用/智能体/模型/MCP/Skill/规则/导入）
- [x] 右栏历史 + Ratchet；历史按时间分组
- [x] Composer：`@` Skill、`#` 文件、模型下拉；MCP/Skill 配置迁入设置
- [x] J7：语音输入（Web Speech）+ 截图/粘贴图片 context
- [x] Composer v2：卡片式输入框（@Agent 顶栏 · 内嵌工具栏 · ↑ 发送）
- [x] 设置中心「CLI 命令」速查 + Composer `?` 快捷入口
- [x] CLI 命令 **▶ 一键运行**（输出 → 底部 Terminal，如 `meris doctor`）
- [x] **Harness 概念文档** — [docs/harness/concepts.md](docs/harness/concepts.md)（工作区/项目/Skill/MCP）
- [x] 设置页显示当前项目根；Skill `source: installed`；导航「技能」与「CLI 命令」分离
- [x] cwd 切换自动刷新 Harness 设置；MCP 双源提示；导入页与技能导入职责分离
- [x] 全局 Skill `~/.meris/skills/`；顶栏 cwd 短标签（`#composer-cwd-chip`）
- [x] MCP 扩展双源 parity；settings→UI 迁移；Composer `@` 分组；全局技能编辑/安装
- [x] 左栏改「文件」仅当前项目树；过滤 Skill/.system 误入项目列表；顶栏去冗余 chip
- [x] **多仓库 task scope** — 左栏「本次涉及」勾选 · Composer chips · prompt 前缀 · [multi-repo.md](docs/harness/multi-repo.md)
- [x] **Git 改动面板 G1–G4** — `git_summary` API · Stage/Commit/提交全部 · scope 提交记录 · [git-workflow.md](docs/harness/git-workflow.md)
- [x] **Parallel --isolate** — worktree 勾选 + server/extension 传参

## Phase S — 公网 SaaS（S0–S5 ✅，S6 持续）

见 [docs/PLAN_SAAS.md](docs/PLAN_SAAS.md) · **顺序路线** [docs/cloud/ROADMAP.md](docs/cloud/ROADMAP.md) · Harness [docs/harness/saas-sandbox.md](docs/harness/saas-sandbox.md)

**已拍板**：首期即 **可写沙箱**（非只读 MVP）；不做单进程多用户妥协。

| 阶段 | 状态 | 核心 |
|------|------|------|
| S0 设计冻结 | ✅ 完成 | OpenAPI、威胁模型、ADR、`meris-cloud/` 脚手架、CI |
| S1 身份/租户 | ✅ 完成 | GitHub OAuth 路由、JWT、MySQL 会话、ui_state、audit |
| S2 可写 Worker | ✅ 完成 | 容器 clone、run、文件/Preview UI、idle 回收、task scope |
| S3 Git Ship & Harness | ✅ 完成 | git API、Plan/Run plan、DoD、Ratchet UI |
| S4 生产化 | ✅ 核心完成 | K8s、计费/配额、Prometheus、runbook/DR |
| S5 团队/生态 | ✅ 完成 | RBAC、workspace/分享、CLI/SDK、Enterprise Helm |
| S6 合规 | 进行中 | 模板 ✅、Redis SSE、Stripe 验签、审计导出、合规文档 |

**S6+ 近期落地（2026-06-20）**

- [x] Postgres → MySQL 迁移脚本（`meris-cloud/scripts/migrate_pg_to_mysql.py`）
- [x] Worker **每 session 独立目录**（`/workspace/sessions/{id}`）+ idle 时清理 FS
- [x] `POST /v1/sessions/{id}/stop` + Worker 进程终止
- [x] Worker `done` 事件 → session 状态回 `ready`（`wait_session` 可用）
- [x] RBAC：viewer 可 `ask`/`plan`，不可 `run`
- [x] CLI `meris cloud sessions stop`
- [x] `GET/POST /v1/repos` — 绑定 Git 仓库 + 平台 token 私有 clone
- [x] Web **Push** / **停止** 按钮；OpenAPI 同步至 0.6.0-s6

**批次 A（合规与身份）** — 见 [docs/cloud/ROADMAP.md](docs/cloud/ROADMAP.md)

- [x] A1 `GET /v1/me/export`（GDPR 元数据导出）
- [x] A2 `DELETE /v1/org`（owner 级联注销）
- [x] A3 API Key `meris_sk_`（签发/撤销/鉴权）
- [x] A4 OAuth state → Redis（内存回退）
- [x] B1–B4 Stripe Checkout/Plans/Portal、session 分钟计量、并发与时长配额

**批次 C（Git 与沙箱隔离）** — 见 [docs/cloud/ROADMAP.md](docs/cloud/ROADMAP.md)

- [x] C1 GitHub App 安装回调 + installation token（`GET /v1/auth/github/app/*`）
- [x] C2 `credential_encrypted` + `MERIS_CLOUD_CREDENTIAL_KEY`；`connect` 支持 `git_token` / `use_github_app`
- [x] C3 K8s Job/session（`k8s_session.py` + Helm `sessionJobs` + RBAC）
- [x] C4 Worker ingest HMAC（`X-Meris-Ingest-Signature`）

**批次 E（产品与生态）** — 见 [docs/cloud/ROADMAP.md](docs/cloud/ROADMAP.md)

- [x] E1 模板 registry（`templates` 表 + `/v1/admin/templates` CRUD）
- [x] E2 Web「本次涉及」task scope UI + `ui-state/task_scope`
- [x] E3 Ratchet apply/reject API + Web 按钮
- [x] E4 CLI/SDK：`usage`、`regions`、`members`、`shares`、`billing`
- [x] E5 `GET /v1/regions` + org region 校验 + [regions.md](docs/cloud/regions.md) checklist

**S6 合规路线 A→E 已全部落地**；后续为生产渗透测试与 GA 运维。

**批次 D（生产运维与安全）** — 见 [docs/cloud/ROADMAP.md](docs/cloud/ROADMAP.md)

- [x] D1 `load_test_sessions.py`（100 session 压测 + CI workflow_dispatch smoke）
- [x] D2 ServiceMonitor 默认开启 + `meris_cloud_http_requests_total`
- [x] D3 `X-Trace-Id` / W3C traceparent + 可选 OTLP；audit `meta.trace_id`
- [x] D4 `security_checklist.py` + Helm `security.*`（non-root、只读根 FS、gVisor runtimeClass）
- [x] D5 `audit_worm_etl.py` → 日 JSONL + 可选 S3（[dr.md](docs/cloud/dr.md)）

**Cloud 待办（后续批次）**

## Phase K — 设计模式闭环（✅ P0/P1 + J5–J7）

对照 `Articles/Meris-Agent设计模式对照.md`：

- [x] Plan → Run plan：自动切嵌套 `meris/` 根 + `--from-plan` + checkbox 回写
- [x] DoD 失败 → Ratchet 面板高亮 + 自动 scan（loop + UI）
- [x] Parallel 结束汇总条
- [x] `docs/harness/routing.md` 意图→mode→model 决策表
- [x] Phase J5 设置中心 Harness 文档索引
- [x] Phase J6 MCP 连接状态指示点
- [x] Phase J7 Composer 语音输入 + 截图/粘贴图片 context chip
- [x] 网络隔离（`network: isolated`）+ `.env` 遮罩（`maskSecrets`）
- [x] Windows `doctor` WSL/bwrap 检测
- [x] **Live benchmark** — `run_benchmark_live.py` + GitHub workflow_dispatch
- [x] **E0 发布准备** — `meris release check` 全绿（不打 tag）
- [x] **E0 发布** — tag `v0.0.2` · [RELEASE_v0.0.2.md](docs/RELEASE_v0.0.2.md)
- [x] **P5-3** — Rust tools + schemas + bash native
- [x] **P5-4 M1** — Rust agent loop（read-only）+ [PLAN_P5_4.md](docs/PLAN_P5_4.md)
- [x] **P5-4 M2** — run 模式写工具 + postEdit/onComplete sensors
- [x] **P5-4 M3** — MCP JSONL 桥 + native loop 工具合并
- [x] **P5-4 M4** — hooks / EventStream / plan 模式
- [x] **P5-4 M5** — system-prompt 桥 + `meris-rs run` 原生入口
- [x] **Phase F** — native 稳定化与发布准备（F1–F4 + F3-M2 ✅；F5 tag 暂缓）· [PLAN_PHASE_F.md](docs/PLAN_PHASE_F.md)
- [x] PyPI 发布流程文档化（实际上传暂缓）— [`docs/PYPI_PUBLISH_READY.md`](docs/PYPI_PUBLISH_READY.md)

## 近期落地（E0 / P5-1）
- [x] `settings.local` 文档（[USER_SETUP.md](docs/USER_SETUP.md)）
- [x] `MERIS_NATIVE` 二进制存在时自动启用（`MERIS_NATIVE=0` 关闭）
- [x] TUI Ratchet apply/reject（Enter → a/r）
- [x] VS Code：`review` / `exec --json` / `run --event-stream`
- [x] GitHub Release workflow + 多平台 `meris-rs` 二进制

## Phase E 摘要

| 阶段 | 交付 |
|------|------|
| E1 | `docs/harness/`、rules 按需注入、`meris harness check` |
| E2 | DoD 解析、Ratchet `L-harness-check`、benchmark local/reject |
| E3 | sandbox warn/strict、bubblewrap（Linux）、`meris-rs sandbox run/check/probe` |
| E4 | JSONL 事件流、`--event-stream`、`meris exec --json`、TUI 事件 |
| E5 | `meris review`、`review` 路由 |
| E6 | `user-prefs.md`、TUI Ratchet 面板、rules 按 name 合并 |

## Dogfood 复盘

| # | 错误类型 | Harness 改动 |
|---|----------|----------------|
| 1 | 路径规范 | `.meris/rules/paths.md` |
| 2 | Plan 格式 | `.meris/skills/plan-format.md` + benchmark |
| 3 | cwd 错误 | `.meris/rules/workspace.md` |
| 4 | bash 乱用 | `.meris/rules/bash-permissions.md` |

## 常用命令

```bash
pytest tests/ -m "not integration" -q
meris harness check
python scripts/run_benchmark_mock.py
python scripts/run_benchmark_mock.py --native-only   # native bridge smokes
python scripts/run_benchmark_mock.py --native        # mock + native (11 tasks)
python scripts/run_benchmark_live.py    # 需 API
meris benchmark run --local-only
meris release check                     # E0 发布前自检
# 详见 docs/E0_RELEASE_CHECKLIST.md
meris doctor
meris run "…" --event-stream .meris/events/run.jsonl
meris exec "…" --json
meris review --staged
meris ratchet digest
meris dogfood                         # 日常 dogfood 环境检查
```

## Ratchet 摘要

- [L-bash-verify] pytest 用 `pytest tests/ -m "not integration" -q`；禁止 find/pwd/`/workspace` bash。
- [L-path] 路径/命名不规范（meris/README、错误包目录前缀等）

## Ratchet 闭环 @2026-06-07

**基线**

- pytest: 232 passed
- benchmark: 7/8（`harness_paths_smoke` fail · 曾误写嵌套 README 路径，已 reject）
- pending: 0 → benchmark 自动生成 `ratchet-20260607-120350-f0d0bc`

**Applied**

- `ratchet-20260607-120350-f0d0bc` → `.meris/rules/paths.md`（L-path · append `<!-- ratchet:L-path -->`）
- 手动迭代：`L-path-answer` — 路径问答只答一行 `README.md`，禁止对比句（否则 benchmark reject 误杀）

**After benchmark**

- `harness_paths_smoke`: fail → **pass**
- 全量 benchmark: **8/8 (100%)**
- `meris ratchet status`: pending 0

**第二次同类任务预期**：问根 README 路径时 agent 只输出 `README.md`，不再写「不是 meris/README.md」。

## Session note (2026-06-07 02:42 UTC)
- **Task**: Reply with exactly: pong
- **Status**: dod_failed — superseded by later harness work; close on next dogfood review

## Session note (2026-06-07 02:48 UTC)
- **Task**: List top-level files in meris/ as bullet points
- **Status**: dod_failed — superseded; paths rule applied (see Ratchet 闭环)
