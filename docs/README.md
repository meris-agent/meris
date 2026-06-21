# Meris 文档

面向**用户与贡献者**的公开文档。维护者进度、Phase 规划、Cloud GA/合规 backlog 在 Obsidian 知识库（不在本仓库）。

**新用户**：从 [USER_SETUP.md](USER_SETUP.md) 开始。

## 入门

| 文档 | 说明 |
|------|------|
| [USER_SETUP.md](USER_SETUP.md) | 安装、API Key、`init-harness` |
| [LOCAL_SETUP.md](LOCAL_SETUP.md) | 扩展、Rust 本机构建（贡献者） |
| [MODELS.md](MODELS.md) | 多厂商模型路由 |

## Harness（Agent 机制）

索引：[harness/README.md](harness/README.md)

| 文档 | 说明 |
|------|------|
| [harness/concepts.md](harness/concepts.md) | 工作区、项目、Skill、MCP |
| [harness/multi-repo.md](harness/multi-repo.md) | 多仓库 task scope |
| [harness/git-workflow.md](harness/git-workflow.md) | Agent Window 改动 / Commit |
| [harness/architecture.md](harness/architecture.md) | 包布局、CLI |
| [harness/routing.md](harness/routing.md) | 模型路由、local 覆盖 |
| [harness/testing.md](harness/testing.md) | pytest、DoD、benchmark |
| [harness/plan-format.md](harness/plan-format.md) | Plan `- [ ]` 格式 |
| [harness/sandbox.md](harness/sandbox.md) | Bash 沙箱 preset / allowlist |
| [harness/PLATFORM_MATRIX.md](harness/PLATFORM_MATRIX.md) | 各 OS 沙箱能力对照 |
| [harness/SEATBELT_DESIGN.md](harness/SEATBELT_DESIGN.md) | macOS Seatbelt 设计 |
| [harness/events.md](harness/events.md) | Loop JSONL 事件流 |
| [harness/saas-sandbox.md](harness/saas-sandbox.md) | Cloud 沙箱与 Harness 映射 |

## 功能设计

| 文档 | 说明 |
|------|------|
| [RATCHET_DESIGN.md](RATCHET_DESIGN.md) | Ratchet 自我进化 |
| [NATIVE_BINARY.md](NATIVE_BINARY.md) | `meris-rs` 与 native loop |

## Meris Cloud（自建）

索引：[cloud/README.md](cloud/README.md)

| 文档 | 说明 |
|------|------|
| [cloud/deploy-baota.md](cloud/deploy-baota.md) | 宝塔单机部署 |
| [cloud/runbook.md](cloud/runbook.md) | 运维 on-call |
| [cloud/dr.md](cloud/dr.md) | 备份与 DR |
| [cloud/threat-model.md](cloud/threat-model.md) | 威胁模型 |

## 其他

| 文档 | 说明 |
|------|------|
| [adr/](adr/) | 架构决策记录 |
| [examples/ainote-vault/](examples/ainote-vault/) | Obsidian vault 示例 Harness |

## 品牌与宗旨（摘要）

- **Meris** · CLI `meris` · PyPI `meris-agent` · Harness 目录 `.meris/`
- **宗旨**：会自我进化的 coding agent — 进化写在 Harness，不是只改模型输出（详见仓库 [README.md](../README.md)）
