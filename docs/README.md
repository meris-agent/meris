# Meris 文档

面向**用户与贡献者**的公开文档。维护者规划、进度、发版清单在 Obsidian 知识库 `docs-meris/`（不在本仓库）。

## 入门

| 文档 | 说明 |
|------|------|
| [USER_SETUP.md](USER_SETUP.md) | 安装、API Key、`init-harness` |
| [LOCAL_SETUP.md](LOCAL_SETUP.md) | 扩展、Rust 本机构建 |
| [MODELS.md](MODELS.md) | 多厂商模型路由 |

## Harness（Agent 机制）

索引：[harness/README.md](harness/README.md)

| 文档 | 说明 |
|------|------|
| [harness/concepts.md](harness/concepts.md) | 工作区、项目、Skill、MCP |
| [harness/architecture.md](harness/architecture.md) | 包布局、CLI |
| [harness/testing.md](harness/testing.md) | pytest、DoD |
| [harness/plan-format.md](harness/plan-format.md) | Plan `- [ ]` 格式 |
| [harness/sandbox.md](harness/sandbox.md) | Bash 沙箱 |
| [harness/saas-sandbox.md](harness/saas-sandbox.md) | Cloud 沙箱与 Harness 映射 |

## 功能设计

| 文档 | 说明 |
|------|------|
| [RATCHET_DESIGN.md](RATCHET_DESIGN.md) | Ratchet 自我进化 |
| [NATIVE_BINARY.md](NATIVE_BINARY.md) | `meris-rs` 与 native loop |

## Meris Cloud（自建）

| 文档 | 说明 |
|------|------|
| [cloud/deploy-baota.md](cloud/deploy-baota.md) | 宝塔单机部署 |
| [cloud/runbook.md](cloud/runbook.md) | 运维 |
| [cloud/dr.md](cloud/dr.md) | 备份与 DR |
| [cloud/threat-model.md](cloud/threat-model.md) | 威胁模型 |
| [cloud/compliance.md](cloud/compliance.md) | 合规 |

## 其他

| 文档 | 说明 |
|------|------|
| [adr/](adr/) | 架构决策记录 |
| [examples/ainote-vault/](examples/ainote-vault/) | Obsidian vault 示例 Harness |

## 品牌与宗旨（摘要）

- **Meris** · CLI `meris` · PyPI `meris-agent` · Harness 目录 `.meris/`
- **宗旨**：会自我进化的 coding agent — 进化写在 Harness，不是只改模型输出（详见仓库 [README.md](../README.md)）
