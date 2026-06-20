---
name: plan-format
description: Plan 模式 checkbox 输出格式（- [ ] 至少 3 条），用于 meris plan 与列任务场景
---

# Skill: Plan 输出格式

## 何时使用

`meris plan`、benchmark plan 任务、用户要求「列计划 / checkbox 任务」时。

## 必须格式

```markdown
- [ ] 第一条任务
- [ ] 第二条任务
- [ ] 第三条任务
```

- 中括号内**必须有空格**：`- [ ]`（不是 `- []`）
- 至少 3 条（除非用户指定 N 条）
- 禁止只用 `1.` `2.` 数字列表

## 路径

- 源码使用项目包目录前缀（如 `meris/cli.py`）
- 仓库根 README：`README.md`（cwd 在仓库根时不要写成 `meris/README.md`）
