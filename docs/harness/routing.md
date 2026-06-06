# 模型路由（Meris 本仓库）

配置：`.meris/settings.yaml` + 个人 `.meris/settings.local.yaml`（gitignore）。

## 原则

- **问句 / 只读** → `fast` profile（如 deepseek-chat）  
- **改代码 / run** → `code` 或 `dynamic` 候选池  
- **大重构** → `rules` 命中 `heavy-refactor` → `heavy` profile  

见 [docs/MODELS.md](../MODELS.md)。

## local 覆盖（重要）

`settings.local.yaml` **只写少量字段**，例如：

```yaml
models:
  profiles:
    code:
      model: ep-your-endpoint
  dynamic:
    enabled: true
```

**不要**在 local 里整段复制 `byMode` / 整表 `rules` — 会**替换** YAML 列表。

**E6.5**：`models.rules` 按 `name` 深合并（local 只覆盖同名 rule 的字段）；其它列表仍为替换。

## 验证

```bash
meris models route --json "你的任务描述"
meris doctor
```
