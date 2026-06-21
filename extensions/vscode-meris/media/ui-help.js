/* Contextual help popovers — view tabs & composer modes */
(function () {
  const $ = (id) => document.getElementById(id);

  const popover = $("ui-help-popover");
  const titleEl = $("ui-help-title");
  const bodyEl = $("ui-help-body");
  const closeBtn = $("ui-help-close");
  const viewHelpBtn = $("view-tabs-help");
  const modeHelpBtn = $("mode-help-btn");

  if (!popover || !bodyEl) return;

  const HELP = {
    views: {
      title: "视图标签 — 看什么",
      body:
        "<p class=\"ui-help-lead\">切换中间主区域显示内容，<strong>不改变</strong> Agent 如何执行。</p>" +
        "<dl class=\"ui-help-dl\">" +
        "<dt>Chat</dt><dd>对话时间线、工具调用、文件 diff、终端输出。</dd>" +
        "<dt>Plan</dt><dd>查看<strong>已生成</strong>的任务清单（<code>.meris/plan/tasks.md</code>），勾选后可 Run plan。</dd>" +
        "<dt>Parallel</dt><dd>多任务并行输入与 lanes 状态；可选 <code>--isolate</code> worktree。</dd>" +
        "<dt>Preview</dt><dd>左侧打开的文件预览（语法高亮 / Markdown），支持多标签切换。</dd>" +
        "</dl>",
    },
    modes: {
      title: "运行模式 — 怎么跑",
      body:
        "<p class=\"ui-help-lead\">决定<strong>下一条消息</strong>用哪种 <code>meris</code> 模式执行。</p>" +
        "<dl class=\"ui-help-dl\">" +
        "<dt>Agent <span class=\"ui-help-tag\">run</span></dt><dd>可读写 scope 内文件、跑命令，完整执行。</dd>" +
        "<dt>Ask <span class=\"ui-help-tag\">ask</span></dt><dd>只读问答，不修改仓库。</dd>" +
        "<dt>Plan <span class=\"ui-help-tag\">plan</span></dt><dd>生成 <code>- [ ]</code> 任务清单，<strong>不直接改代码</strong>；完成后在上方 Plan 视图查看。</dd>" +
        "</dl>" +
        "<p class=\"ui-help-note\">⚠ 上方 <strong>Plan 视图</strong> = 看已有计划；下方 <strong>Plan 模式</strong> = 让 Agent 新建计划。</p>",
    },
  };

  let openKey = "";

  function showHelp(key) {
    const ent = HELP[key];
    if (!ent) return;
    if (openKey === key && !popover.classList.contains("hidden")) {
      hideHelp();
      return;
    }
    openKey = key;
    if (titleEl) titleEl.textContent = ent.title;
    bodyEl.innerHTML = ent.body;
    popover.classList.remove("hidden");
    popover.setAttribute("aria-hidden", "false");
  }

  function hideHelp() {
    openKey = "";
    popover.classList.add("hidden");
    popover.setAttribute("aria-hidden", "true");
  }

  if (viewHelpBtn) {
    viewHelpBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      showHelp("views");
    });
  }
  if (modeHelpBtn) {
    modeHelpBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      showHelp("modes");
    });
  }
  if (closeBtn) closeBtn.addEventListener("click", hideHelp);
  popover.addEventListener("click", (e) => {
    if (e.target === popover) hideHelp();
  });
  document.addEventListener("click", (e) => {
    if (popover.classList.contains("hidden")) return;
    const t = e.target;
    if (popover.contains(t) || t === viewHelpBtn || t === modeHelpBtn) return;
    hideHelp();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") hideHelp();
  });
})();
