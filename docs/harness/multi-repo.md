# 多仓库 / 多项目任务（通用）

> Meris **不假设**你是 monorepo、微服务还是 vault+子仓库。本文给**任意多路径**场景的通用流程。  
> 概念对照：[concepts.md](concepts.md)

## 三个层次（不要混）

| 层次 | 含义 | UI |
|------|------|-----|
| **项目（左栏）** | 注册 + 勾选范围 + ★ 主项目；`+` / `⋯` / 仅当前 / 全选 |

```text
已注册：A, B, C, D
本次涉及：☑ A  ☑ B  ☐ C  ☐ D
当前 cwd：A  → 只有 A 的文件会出现在左栏「文件」树；run 默认只改 A
```

- **ask**：在 scope 内只读探索。  
- **plan**：条目可按 scope 内项目分组。  
- **run**：**仅可修改 scope 内项目**；shell/pytest 仍在顶栏 cwd。

## 推荐流程

### 1. 探索（ask）

1. 在左栏勾选「本次涉及」的项目。  
2. 对每个项目：切换 cwd → `ask` → 问接口、调用链、测试位置。  
3. 结论记到 `PROGRESS.md`、vault 笔记，或接下来的 Plan。

### 2. 计划（plan）

- cwd 放在**主项目**（通常是被依赖方或改动最大者）。  
- prompt 附上探索笔记；让 Plan 按 **scope 内项目** 列 checkbox。

### 3. 执行（run）

- 按 Plan 逐项：**切换 cwd** → `run` → 本仓 pytest。  
- 未在 scope 里的项目，Agent 不应擅自改动。

## 「共享契约」是什么（可选）

多个模块共同遵守的接口约定，可能在：

- OpenAPI / proto 独立文件  
- 被调用方 `docs/`、路由代码  
- 调用方 `client/`、集成测试  

Meris **不会自动发现**契约位置；在 `AGENTS.md`、Rule 或 Skill 里写明即可。  
见 Skill 模板 `multi-repo-workflow`。

## Harness 建议

在用户自己的仓库（或产品母目录）添加：

```markdown
## 多仓库
- 跨项目任务：先 ask 探索，再 plan，再按项目切换 cwd run。
- 实现顺序：被调用方 → 调用方 → 网关/BFF。
- 未勾选进「本次涉及」的项目，不要改。
```

## UI 行为

| 控件 | 作用 |
|------|------|
| 左栏「项目」 | ☑ 勾选 = Agent 读写范围；★ = 主项目 (cwd) |
| Composer chips | 发送时注入已勾选项目 |

## 相关

- [concepts.md](concepts.md)  
- [routing.md](routing.md)  
- `templates/skills/multi-repo-workflow.md`
