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

- 源码：`meris/cli.py`、`meris/harness/...`
- 本仓库 README：`README.md`（不是 `meris/README.md`）
