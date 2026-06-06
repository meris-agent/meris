# Plan 模式格式

`meris plan` 与 benchmark `plan_smoke` 要求相同。

## 必须格式

```markdown
- [ ] 第一条任务
- [ ] 第二条任务
- [ ] 第三条任务
```

- 中括号内**必须有空格**：`- [ ]`（不是 `- []`）  
- 至少 3 条（用户指定 N 条时按 N 条）  
- 禁止只用 `1.` `2.` 数字列表  
- 路径：`meris/cli.py` 等；README 在本仓库 cwd 下为 `README.md`  
- **只输出计划，不改代码**

## Skill

可 `load_skill plan-format` 查看 `.meris/skills/plan-format.md`。
