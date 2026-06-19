(function () {
  function createStandaloneBridge() {
    const stateKey = "meris-agent-state";
    const listeners = [];
    const es = new EventSource("/api/events");
    es.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        window.dispatchEvent(new MessageEvent("message", { data: msg }));
      } catch {
        // ignore
      }
    };
    return {
      getState() {
        try {
          return JSON.parse(localStorage.getItem(stateKey) || "{}");
        } catch {
          return {};
        }
      },
      setState(s) {
        localStorage.setItem(stateKey, JSON.stringify(s));
      },
      postMessage(msg) {
        fetch("/api/cmd", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(msg),
        }).catch(() => {});
      },
    };
  }

  const vscode =
    typeof acquireVsCodeApi !== "undefined" ? acquireVsCodeApi() : createStandaloneBridge();

  const timeline = document.getElementById("timeline");
  const taskInput = document.getElementById("task-input");
  const submitBtn = document.getElementById("submit-btn");
  const stopBtn = document.getElementById("stop-btn");
  const statusEl = document.getElementById("status");
  const modeSelect = document.getElementById("mode-select");
  const approveCheck = document.getElementById("approve-check");
  const sessionList = document.getElementById("session-list");
  const refreshSessionsBtn = document.getElementById("refresh-sessions");
  const ratchetList = document.getElementById("ratchet-list");
  const refreshRatchetBtn = document.getElementById("refresh-ratchet");
  const ratchetScanBtn = document.getElementById("ratchet-scan");
  const errorBanner = document.getElementById("error-banner");
  const approvalBar = document.getElementById("approval-bar");
  const approvalTool = document.getElementById("approval-tool");
  const approvalArgs = document.getElementById("approval-args");
  const approveYes = document.getElementById("approve-yes");
  const approveNo = document.getElementById("approve-no");

  let running = false;
  let currentAssistantEl = null;
  let currentReasoningEl = null;
  let reasoningRaw = "";
  /** @type {Map<string, HTMLDetailsElement>} */
  const pendingTools = new Map();
  let activeSessionId = null;
  let pendingApprovalId = null;

  const RESUMABLE = new Set(["running", "cancelled", "error"]);

  const saved = vscode.getState() || {};
  if (saved.taskDraft) {
    taskInput.value = saved.taskDraft;
  }
  if (saved.approve) {
    approveCheck.checked = true;
  }
  if (saved.mode && modeSelect.querySelector('option[value="' + saved.mode + '"]')) {
    modeSelect.value = saved.mode;
  }

  function persistState() {
    vscode.setState({
      taskDraft: taskInput.value,
      approve: approveCheck.checked,
      mode: modeSelect.value,
    });
  }

  function showErrorBanner(text) {
    if (!text) {
      errorBanner.classList.add("hidden");
      errorBanner.textContent = "";
      document.body.classList.remove("has-error");
      return;
    }
    errorBanner.textContent = text.slice(0, 500);
    errorBanner.classList.remove("hidden");
    document.body.classList.add("has-error");
  }

  function setStatus(text, cls) {
    statusEl.textContent = text;
    statusEl.className = "status " + (cls || "idle");
  }

  function setRunning(isRunning) {
    running = isRunning;
    submitBtn.disabled = isRunning;
    stopBtn.disabled = !isRunning;
    modeSelect.disabled = isRunning;
    approveCheck.disabled = isRunning;
    updateSessionItemsDisabled(isRunning);
    ratchetList.querySelectorAll(".ratchet-item").forEach((el) => {
      if (isRunning) el.classList.add("disabled");
      else el.classList.remove("disabled");
    });
  }

  function updateSessionItemsDisabled(disabled) {
    sessionList.querySelectorAll(".session-item").forEach((el) => {
      if (!RESUMABLE.has(el.dataset.status || "")) {
        el.classList.add("disabled");
        return;
      }
      if (disabled) el.classList.add("disabled");
      else el.classList.remove("disabled");
    });
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  let assistantRaw = "";
  let markdownRAF = null;

  function scheduleAssistantMarkdown() {
    if (markdownRAF) return;
    markdownRAF = requestAnimationFrame(() => {
      markdownRAF = null;
      if (!currentAssistantEl || !assistantRaw) return;
      const body = currentAssistantEl.querySelector(".entry-body");
      if (body) body.innerHTML = renderMarkdownLite(assistantRaw);
    });
  }

  function appendReasoningEntry(initial) {
    const details = document.createElement("details");
    details.className = "entry entry-reasoning";
    details.open = true;
    details.innerHTML =
      '<summary><span class="reasoning-label">reasoning</span></summary>' +
      '<pre class="entry-body reasoning-body"></pre>';
    const body = details.querySelector(".reasoning-body");
    body.textContent = initial;
    timeline.appendChild(details);
    timeline.scrollTop = timeline.scrollHeight;
    return details;
  }

  function renderMarkdownLite(text) {
    const escaped = escapeHtml(text);
    let html = escaped.replace(
      /```([\s\S]*?)```/g,
      (_, code) => '<pre class="md-code">' + code + "</pre>"
    );
    html = html.replace(/`([^`\n]+)`/g, '<code class="md-inline">$1</code>');
    html = html.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/\n/g, "<br>");
    return html;
  }

  function renderDiffHtml(text) {
    return text
      .split("\n")
      .map((line) => {
        const esc = escapeHtml(line);
        if (line.startsWith("+++") || line.startsWith("---")) {
          return '<div class="diff-line diff-meta">' + esc + "</div>";
        }
        if (line.startsWith("@@")) {
          return '<div class="diff-line diff-hunk">' + esc + "</div>";
        }
        if (line.startsWith("+")) {
          return '<div class="diff-line diff-add">' + esc + "</div>";
        }
        if (line.startsWith("-")) {
          return '<div class="diff-line diff-del">' + esc + "</div>";
        }
        return '<div class="diff-line diff-ctx">' + esc + "</div>";
      })
      .join("");
  }

  function finalizeAssistantMarkdown() {
    if (!currentAssistantEl) return;
    const body = currentAssistantEl.querySelector(".entry-body");
    if (body && assistantRaw) {
      body.innerHTML = renderMarkdownLite(assistantRaw);
    }
    assistantRaw = "";
  }

  function appendAssistantEntry(initial) {
    const el = document.createElement("div");
    el.className = "entry entry-assistant";
    el.innerHTML =
      '<div class="entry-meta">assistant</div><div class="entry-body md-body"></div>';
    const body = el.querySelector(".entry-body");
    body.textContent = initial;
    timeline.appendChild(el);
    timeline.scrollTop = timeline.scrollHeight;
    return el;
  }

  function formatArgs(args) {
    if (!args || typeof args !== "object") return "(no args)";
    try {
      return JSON.stringify(args, null, 2).slice(0, 1200);
    } catch {
      return String(args).slice(0, 600);
    }
  }

  function toolKey(ev) {
    return (ev.tool || "?") + ":" + (ev.turn ?? "");
  }

  function appendEntry(kind, meta, body) {
    const el = document.createElement("div");
    el.className = "entry entry-" + kind;
    el.innerHTML =
      '<div class="entry-meta">' +
      escapeHtml(meta) +
      "</div>" +
      '<pre class="entry-body">' +
      escapeHtml(body) +
      "</pre>";
    timeline.appendChild(el);
    timeline.scrollTop = timeline.scrollHeight;
    return el;
  }

  function createToolCard(ev) {
    const tool = ev.tool || "?";
    const details = document.createElement("details");
    details.className = "entry entry-tool tool-card tool-running";
    details.open = true;
    details.dataset.toolKey = toolKey(ev);
    details.innerHTML =
      '<summary><span class="tool-icon">▶</span> ' +
      escapeHtml(tool) +
      ' <span class="tool-state">running</span></summary>' +
      '<div class="tool-section"><div class="tool-label">args</div><pre class="entry-body">' +
      escapeHtml(formatArgs(ev.args)) +
      '</pre></div><div class="tool-section tool-output"><div class="tool-label">output</div><pre class="entry-body tool-output-body">…</pre></div>';
    timeline.appendChild(details);
    timeline.scrollTop = timeline.scrollHeight;
    pendingTools.set(toolKey(ev), details);
    return details;
  }

  function finishToolCard(ev, msg) {
    const key = toolKey(ev);
    let card = pendingTools.get(key);
    const preview = (ev.preview || msg || "").slice(0, 4000);
    if (!card) {
      card = document.createElement("details");
      card.className = "entry entry-tool tool-card tool-done";
      card.innerHTML =
        '<summary><span class="tool-icon">✓</span> ' +
        escapeHtml(ev.tool || "?") +
        ' <span class="tool-state">done</span></summary>' +
        '<div class="tool-section tool-output"><div class="tool-label">output</div><pre class="entry-body">' +
        escapeHtml(preview) +
        "</pre></div>";
      timeline.appendChild(card);
    } else {
      card.classList.remove("tool-running");
      card.classList.add("tool-done");
      const state = card.querySelector(".tool-state");
      const icon = card.querySelector(".tool-icon");
      if (state) state.textContent = "done";
      if (icon) icon.textContent = "✓";
      const out = card.querySelector(".tool-output-body");
      if (out) out.textContent = preview || "(empty)";
      card.open = false;
      pendingTools.delete(key);
    }
    timeline.scrollTop = timeline.scrollHeight;
    currentAssistantEl = null;
  }

  function clearEmptyHint() {
    const hint = timeline.querySelector(".empty-hint");
    if (hint) hint.remove();
  }

  function renderSessions(sessions) {
    sessionList.innerHTML = "";
    if (!sessions || !sessions.length) {
      sessionList.innerHTML = '<li class="sessions-empty">No sessions yet</li>';
      return;
    }
    for (const s of sessions) {
      const li = document.createElement("li");
      li.className = "session-item";
      if (s.id === activeSessionId) li.classList.add("active");
      if (!RESUMABLE.has(s.status)) li.classList.add("disabled");
      li.dataset.sessionId = s.id;
      li.dataset.status = s.status;
      li.dataset.mode = s.mode;
      li.innerHTML =
        '<div class="session-id">' +
        escapeHtml(s.id.slice(0, 8)) +
        "</div>" +
        '<div class="session-meta">' +
        escapeHtml(s.status) +
        " · " +
        escapeHtml(s.mode) +
        " · t" +
        escapeHtml(String(s.turn)) +
        "</div>" +
        '<div class="session-task" title="' +
        escapeHtml(s.task) +
        '">' +
        escapeHtml(s.task.slice(0, 48)) +
        "</div>";
      li.addEventListener("click", () => {
        if (running) return;
        if (!RESUMABLE.has(s.status)) return;
        vscode.postMessage({
          type: "resumeSession",
          sessionId: s.id,
          approve: approveCheck.checked,
        });
      });
      sessionList.appendChild(li);
    }
  }

  function renderRatchet(data) {
    ratchetList.innerHTML = "";
    const proposals = (data && data.proposals) || [];
    const insightsPending = (data && data.insightsPending) || 0;
    if (!proposals.length && !insightsPending) {
      ratchetList.innerHTML = '<li class="ratchet-empty">None pending</li>';
      return;
    }
    if (insightsPending) {
      const hint = document.createElement("li");
      hint.className = "ratchet-insight-hint";
      hint.textContent = insightsPending + " insight(s) — run meris ratchet digest";
      ratchetList.appendChild(hint);
    }
    for (const p of proposals) {
      const li = document.createElement("li");
      li.className = "ratchet-item";
      li.innerHTML =
        '<div class="ratchet-lesson">' +
        escapeHtml(p.lesson) +
        "</div>" +
        '<div class="ratchet-summary" title="' +
        escapeHtml(p.summary) +
        '">' +
        escapeHtml(p.summary.slice(0, 56)) +
        "</div>" +
        '<div class="ratchet-target">' +
        escapeHtml(p.target) +
        "</div>" +
        '<div class="ratchet-actions">' +
        '<button type="button" class="ratchet-apply-btn">Apply</button>' +
        '<button type="button" class="ratchet-reject-btn">Reject</button>' +
        "</div>";
      if (running) {
        li.classList.add("disabled");
      }
      li.querySelector(".ratchet-apply-btn").addEventListener("click", (e) => {
        e.stopPropagation();
        if (running) return;
        vscode.postMessage({ type: "ratchetApply", proposalId: p.id });
      });
      li.querySelector(".ratchet-reject-btn").addEventListener("click", (e) => {
        e.stopPropagation();
        if (running) return;
        vscode.postMessage({ type: "ratchetReject", proposalId: p.id });
      });
      ratchetList.appendChild(li);
    }
  }

  function hideApprovalBar() {
    pendingApprovalId = null;
    approvalBar.classList.add("hidden");
  }

  function showApprovalBar(ev) {
    pendingApprovalId = ev.request_id || null;
    approvalTool.textContent = ev.tool || "?";
    approvalArgs.textContent = formatArgs(ev.args);
    approvalBar.classList.remove("hidden");
  }

  function appendFileChange(ev) {
    const rel = ev.path || "";
    const diff = ev.diff_preview || "";
    const details = document.createElement("details");
    details.className = "entry entry-file file-change-card";
    details.open = true;
    const summary = document.createElement("summary");
    summary.innerHTML =
      '<span class="file-change-label">file_change</span> ' + escapeHtml(ev.tool || "edit");
    details.appendChild(summary);

    const pathEl = document.createElement("pre");
    pathEl.className = "entry-body file-path";
    pathEl.textContent = rel;
    details.appendChild(pathEl);

    if (diff) {
      const diffEl = document.createElement("div");
      diffEl.className = "entry-body diff-preview";
      diffEl.innerHTML = renderDiffHtml(diff.slice(0, 5000));
      details.appendChild(diffEl);
    }

    const btn = document.createElement("button");
    btn.className = "file-open-btn";
    btn.type = "button";
    btn.textContent = "Open in editor";
    btn.addEventListener("click", () => {
      vscode.postMessage({ type: "openFile", path: rel });
    });
    details.appendChild(btn);
    timeline.appendChild(details);
    timeline.scrollTop = timeline.scrollHeight;
  }

  function handleEvent(ev) {
    if (!ev || ev.type !== "event") return;
    const kind = ev.kind || "status";
    const msg = ev.message || "";

    switch (kind) {
      case "submission":
        clearEmptyHint();
        appendEntry("user", "task", ev.task || msg || "(task)");
        currentAssistantEl = null;
        break;

      case "session_start":
        if (ev.session) activeSessionId = ev.session;
        appendEntry(
          "meta",
          "session " + (ev.session ? ev.session.slice(0, 8) : ""),
          (ev.model ? "model=" + ev.model + "\n" : "") + (msg || "").slice(0, 300)
        );
        break;

      case "token": {
        clearEmptyHint();
        const text = msg || "";
        assistantRaw += text;
        if (currentAssistantEl) {
          scheduleAssistantMarkdown();
        } else {
          currentAssistantEl = appendAssistantEntry("");
          assistantRaw = text;
          scheduleAssistantMarkdown();
        }
        timeline.scrollTop = timeline.scrollHeight;
        break;
      }

      case "reasoning": {
        clearEmptyHint();
        const text = msg || "";
        reasoningRaw += text;
        if (currentReasoningEl) {
          const body = currentReasoningEl.querySelector(".reasoning-body");
          if (body) body.textContent = reasoningRaw;
        } else {
          currentReasoningEl = appendReasoningEntry(text);
          reasoningRaw = text;
        }
        timeline.scrollTop = timeline.scrollHeight;
        break;
      }

      case "thinking": {
        const details = document.createElement("details");
        details.className = "entry entry-thinking";
        details.innerHTML =
          "<summary>thinking</summary><pre class=\"entry-body\">" +
          escapeHtml(msg.slice(0, 600)) +
          "</pre>";
        timeline.appendChild(details);
        timeline.scrollTop = timeline.scrollHeight;
        break;
      }

      case "tool_start":
        finalizeAssistantMarkdown();
        currentReasoningEl = null;
        reasoningRaw = "";
        currentAssistantEl = null;
        createToolCard(ev);
        break;

      case "tool_end":
        finishToolCard(ev, msg);
        break;

      case "approval_request":
        showApprovalBar(ev);
        appendEntry("meta", "approval", "waiting for " + (ev.tool || "tool"));
        break;

      case "file_change":
        appendFileChange(ev);
        break;

      case "sensor":
        appendEntry(
          "sensor",
          "sensor " + (ev.ok === false ? "FAIL" : "PASS"),
          msg.slice(0, 1200)
        );
        break;

      case "status":
        if (msg) appendEntry("meta", "status", msg.slice(0, 400));
        break;

      case "done":
        finalizeAssistantMarkdown();
        currentAssistantEl = null;
        pendingTools.clear();
        appendEntry("done", "done", "status: " + (ev.status || msg || "completed"));
        break;

      default:
        if (msg) appendEntry("meta", kind, msg.slice(0, 400));
    }
  }

  submitBtn.addEventListener("click", () => {
    const task = taskInput.value.trim();
    if (!task || running) return;
    vscode.postMessage({
      type: "submit",
      task,
      mode: modeSelect.value,
      approve: approveCheck.checked,
    });
  });

  stopBtn.addEventListener("click", () => {
    if (!running) return;
    vscode.postMessage({ type: "stop" });
  });

  refreshSessionsBtn.addEventListener("click", () => {
    vscode.postMessage({ type: "refreshSessions" });
  });

  refreshRatchetBtn.addEventListener("click", () => {
    vscode.postMessage({ type: "refreshRatchet" });
  });

  ratchetScanBtn.addEventListener("click", () => {
    if (running) return;
    vscode.postMessage({ type: "ratchetScan" });
  });

  taskInput.addEventListener("input", persistState);
  approveCheck.addEventListener("change", persistState);
  modeSelect.addEventListener("change", persistState);

  approveYes.addEventListener("click", () => {
    if (!pendingApprovalId) return;
    vscode.postMessage({
      type: "approvalResponse",
      requestId: pendingApprovalId,
      approved: true,
    });
    hideApprovalBar();
  });

  approveNo.addEventListener("click", () => {
    if (!pendingApprovalId) return;
    vscode.postMessage({
      type: "approvalResponse",
      requestId: pendingApprovalId,
      approved: false,
    });
    hideApprovalBar();
  });

  taskInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      submitBtn.click();
    }
  });

  window.addEventListener("message", (event) => {
    const msg = event.data;
    if (!msg || !msg.type) return;

    switch (msg.type) {
      case "runStart":
        if (!msg.resume) timeline.innerHTML = "";
        clearEmptyHint();
        showErrorBanner("");
        if (msg.resume) {
          appendEntry(
            "meta",
            "resume",
            "session " + (msg.sessionId || "").slice(0, 8) + "\n" + (msg.task || "")
          );
          activeSessionId = msg.sessionId || null;
        } else {
          appendEntry("user", "you · " + (msg.mode || "run"), msg.task || "");
          activeSessionId = null;
        }
        setRunning(true);
        setStatus("Running…", "running");
        currentAssistantEl = null;
        assistantRaw = "";
        currentReasoningEl = null;
        reasoningRaw = "";
        pendingTools.clear();
        break;

      case "event":
        handleEvent(msg.event);
        break;

      case "sessions":
        renderSessions(msg.sessions);
        break;

      case "ratchet":
        renderRatchet(msg);
        break;

      case "ratchetResult":
        appendEntry(
          "meta",
          "ratchet " + (msg.action || ""),
          (msg.ok ? "OK" : "FAIL") + " " + (msg.proposalId || "") + "\n" + (msg.detail || "")
        );
        break;

      case "status":
        setRunning(msg.status === "running");
        if (msg.status === "done") {
          setStatus("Done", "done");
          showErrorBanner("");
        } else if (msg.status === "error") {
          setStatus("Error", "error");
          if (msg.stderr) {
            showErrorBanner(msg.stderr);
            appendEntry("error", "stderr", msg.stderr);
          }
        } else if (msg.status === "cancelled") {
          setStatus("Cancelled", "error");
          showErrorBanner("");
        } else if (msg.status === "running") {
          setStatus("Running…", "running");
          showErrorBanner("");
        }
        if (msg.status !== "running") hideApprovalBar();
        break;
    }
  });

  timeline.innerHTML =
    '<div class="empty-hint">Describe a task below and press Run.<br>Ctrl+Enter to submit · click session to resume.</div>';
  vscode.postMessage({ type: "refreshSessions" });
  vscode.postMessage({ type: "refreshRatchet" });
})();
