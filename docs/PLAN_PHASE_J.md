# Phase J — Agent UI 对标 TRAE（设置中心 + 输入体验）

> 参考 TRAE / Cursor 信息架构：配置进设置中心，聊天区只管聊天。

## J1 — 设置中心（P0）✅ 本阶段

- [x] **J1.1** 全屏设置 overlay + 左侧分类导航 + 搜索过滤
- [x] **J1.2** 通用（主题/背景）
- [x] **J1.3** 智能体（默认 mode / approve）
- [x] **J1.4** 模型（路由摘要 + Auto 说明）
- [x] **J1.5** MCP（启用列表 + JSON 编辑 + 保存）
- [x] **J1.6** 技能与命令（列表 + Markdown 编辑）
- [x] **J1.7** 规则（`.meris/rules/` 列表 + 编辑）
- [x] **J1.8** 导入配置（Cursor mcp.json + .cursor/rules）

## J2 — 布局重组（P1）

- [x] **J2.1** 左栏仅 Files（去掉 Sessions tab）
- [x] **J2.2** 右栏 History + Ratchet 分 tab
- [x] **J2.3** 历史按时间分组 + 任务标题优先展示

## J3 — Composer 精简（P1）

- [x] **J3.1** `@` → Skill 选择
- [x] **J3.2** `#` → 文件选择（复用 context files API）
- [x] **J3.3** 模型下拉（Auto + 路由信息）
- [x] **J3.4** 移除 composer 内 MCP/Skill 重配置下拉
- [x] **J3.5** TRAE 式卡片 Composer（顶栏 @Agent · 内嵌底栏 · ↑ 发送）
- [x] **J3.6** CLI 命令速查（设置 → CLI 命令 · Composer `?` · 点击复制）

## J4 — 后端 API

- [x] rules list/read/save
- [x] models info
- [x] importCursorRules
- [x] `/api/rules` `/api/models`

## 后续（✅ J5–J7）

- [x] J5 索引与文档页 — 设置中心「文档」+ `/api/docs` · `/api/doc`
- [x] J6 MCP 连接状态绿/红点 — `probe_mcp_connections` + 设置列表状态点
## J7 — Composer 多媒体（P2）✅

- [x] **J7.1** 语音输入（Web Speech API → task textarea）
- [x] **J7.2** 截图/图片：粘贴 · 拖拽 · 文件选择
- [x] **J7.3** 保存至 `.meris/context/images/` + context chip 缩略图
- [x] **J7.4** `saveContextImage` API + `contextImageError` 反馈
