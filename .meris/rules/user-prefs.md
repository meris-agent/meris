---
inject: always
---

# 用户偏好（唯一入口）

- 语言：中文回复；代码注释可英文
- 模型：个人 ep 写在 `.meris/settings.local.yaml`，不要改团队 `settings.yaml` 的 `profiles.code`
- 提交：完成前跑 `pytest tests/ -m "not integration" -q` 与 `meris harness check`
- Ratchet：周末跑 `meris ratchet digest` → `meris ratchet insights review`

<!-- digest 可 append 到此文件 -->
