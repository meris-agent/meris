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
        })
          .then(async (r) => {
            const ct = r.headers.get("content-type") || "";
            if (!ct.includes("application/json")) return null;
            try {
              return await r.json();
            } catch {
              return null;
            }
          })
          .then((data) => {
            if (data && data.type) {
              window.dispatchEvent(new MessageEvent("message", { data }));
            }
          })
          .catch(() => {});
      },
    };
  }

  const vscode =
    typeof acquireVsCodeApi !== "undefined" ? acquireVsCodeApi() : createStandaloneBridge();
  window.__merisVscode = vscode;
  window.__merisStandalone = typeof acquireVsCodeApi === "undefined";

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
  const settingsBtn = document.getElementById("settings-btn");
  const bgColorPicker = document.getElementById("bg-color-picker");
  const bgColorText = document.getElementById("bg-color-text");
  const settingsResetBtn = document.getElementById("settings-reset");
  const themePresetsEl = document.getElementById("theme-presets");

  const THEMES = {
    vibe: {
      bg: "#0b0d11",
      surface: "#12141a",
      border: "#262a33",
      text: "#e8eaee",
      muted: "#8a8f9a",
      accent: "#6c8cff",
      userBg: "#1a1d26",
      assistantBg: "transparent",
      toolBg: "#161920",
    },
    dark: {
      bg: "#18181b",
      surface: "#1f1f23",
      border: "#2e2e33",
      text: "#fafafa",
      muted: "#a1a1aa",
      accent: "#7c6cff",
      userBg: "#27272a",
      assistantBg: "transparent",
      toolBg: "#1c1c1f",
    },
    midnight: {
      bg: "#0d1117",
      surface: "#161b22",
      border: "#30363d",
      text: "#c9d1d9",
      muted: "#8b949e",
      accent: "#58a6ff",
      userBg: "#21262d",
      assistantBg: "transparent",
      toolBg: "#1c2128",
    },
    light: {
      bg: "#fafafa",
      surface: "#ffffff",
      border: "#e4e4e7",
      text: "#18181b",
      muted: "#71717a",
      accent: "#5b5bd6",
      userBg: "#f4f4f5",
      assistantBg: "transparent",
      toolBg: "#f4f4f5",
    },
  };

  let themePreset = "vibe";
  let customBg = "";

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
  updateComposerModeLabel();
  if (saved.themePreset && THEMES[saved.themePreset]) {
    themePreset = saved.themePreset;
  }
  if (saved.customBg) {
    customBg = saved.customBg;
  }

  function normalizeHex(color) {
    if (!color || typeof color !== "string") return "#0b0d11";
    const c = color.trim();
    if (/^#[0-9a-fA-F]{6}$/.test(c)) return c.toLowerCase();
    if (/^#[0-9a-fA-F]{3}$/.test(c)) {
      return (
        "#" +
        c[1] + c[1] +
        c[2] + c[2] +
        c[3] + c[3]
      ).toLowerCase();
    }
    return "#0b0d11";
  }

  function hexToRgb(hex) {
    const h = normalizeHex(hex).slice(1);
    return {
      r: parseInt(h.slice(0, 2), 16),
      g: parseInt(h.slice(2, 4), 16),
      b: parseInt(h.slice(4, 6), 16),
    };
  }

  function rgbToHex(r, g, b) {
    const clamp = (n) => Math.max(0, Math.min(255, Math.round(n)));
    return (
      "#" +
      [clamp(r), clamp(g), clamp(b)]
        .map((n) => n.toString(16).padStart(2, "0"))
        .join("")
    );
  }

  function mixHex(c1, c2, weight) {
    const a = hexToRgb(c1);
    const b = hexToRgb(c2);
    const w = Math.max(0, Math.min(1, weight));
    return rgbToHex(
      a.r * (1 - w) + b.r * w,
      a.g * (1 - w) + b.g * w,
      a.b * (1 - w) + b.b * w
    );
  }

  function bgLuminance(hex) {
    const { r, g, b } = hexToRgb(hex);
    const lin = [r, g, b].map((c) => {
      const s = c / 255;
      return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2];
  }

  function isDarkBg(hex) {
    return bgLuminance(hex) < 0.45;
  }

  function accentSoft(accent) {
    const { r, g, b } = hexToRgb(accent);
    return `rgba(${r}, ${g}, ${b}, 0.14)`;
  }

  function paletteFromBg(bg, accentHint) {
    const dark = isDarkBg(bg);
    const lift = dark ? "#ffffff" : "#000000";
    const accent = accentHint || (dark ? "#6c8cff" : "#5b5bd6");
    return {
      bg,
      surface: mixHex(bg, lift, dark ? 0.07 : 0.04),
      surface2: mixHex(bg, lift, dark ? 0.12 : 0.08),
      border: mixHex(bg, lift, dark ? 0.16 : 0.14),
      borderSubtle: mixHex(bg, lift, dark ? 0.09 : 0.07),
      text: dark ? "#e8eaee" : "#18181b",
      textSecondary: dark ? "#d1d5db" : "#374151",
      muted: dark ? "#9ca3af" : "#6b7280",
      userBg: mixHex(bg, lift, dark ? 0.1 : 0.06),
      toolBg: mixHex(bg, lift, dark ? 0.06 : 0.04),
      codeBg: mixHex(bg, lift, dark ? 0.03 : 0.05),
      assistantBg: "transparent",
      accent,
      onAccent: "#ffffff",
      errorText: dark ? "#fecaca" : "#b91c1c",
      successText: dark ? "#86efac" : "#15803d",
      inlineCode: dark ? "#c4b5fd" : "#6d28d9",
    };
  }

  function applyPalette(palette) {
    const root = document.documentElement;
    root.style.setProperty("--bg", palette.bg);
    root.style.setProperty("--surface", palette.surface);
    root.style.setProperty("--surface-2", palette.surface2);
    root.style.setProperty("--border", palette.border);
    root.style.setProperty("--border-subtle", palette.borderSubtle);
    root.style.setProperty("--text", palette.text);
    root.style.setProperty("--text-secondary", palette.textSecondary);
    root.style.setProperty("--muted", palette.muted);
    root.style.setProperty("--user-bg", palette.userBg);
    root.style.setProperty("--assistant-bg", palette.assistantBg);
    root.style.setProperty("--tool-bg", palette.toolBg);
    root.style.setProperty("--code-bg", palette.codeBg);
    root.style.setProperty("--accent", palette.accent);
    root.style.setProperty("--accent-soft", accentSoft(palette.accent));
    root.style.setProperty("--on-accent", palette.onAccent);
    root.style.setProperty("--error-text", palette.errorText);
    root.style.setProperty("--success-text", palette.successText);
    root.style.setProperty("--inline-code", palette.inlineCode);
    document.body.classList.toggle("theme-dark", isDarkBg(palette.bg));
    document.body.classList.toggle("theme-light", !isDarkBg(palette.bg));
  }

  function applyTheme() {
    const theme = THEMES[themePreset] || THEMES.vibe;
    const bg = normalizeHex(customBg || theme.bg);
    const palette = customBg
      ? paletteFromBg(bg, theme.accent)
      : paletteFromBg(bg, theme.accent);
    if (!customBg) {
      palette.surface = theme.surface;
      palette.border = theme.border;
      palette.text = theme.text;
      palette.muted = theme.muted;
      palette.userBg = theme.userBg;
      palette.toolBg = theme.toolBg;
      palette.textSecondary = isDarkBg(bg) ? "#d1d5db" : "#374151";
      palette.surface2 = mixHex(bg, isDarkBg(bg) ? "#ffffff" : "#000000", isDarkBg(bg) ? 0.12 : 0.08);
      palette.borderSubtle = mixHex(bg, isDarkBg(bg) ? "#ffffff" : "#000000", isDarkBg(bg) ? 0.09 : 0.07);
      palette.codeBg = mixHex(bg, "#000000", isDarkBg(bg) ? 0.25 : 0.06);
    }
    applyPalette(palette);
    if (bgColorPicker) bgColorPicker.value = bg;
    if (bgColorText) bgColorText.textContent = bg;
    if (themePresetsEl) {
      themePresetsEl.querySelectorAll(".theme-chip").forEach((chip) => {
        chip.classList.toggle("active", chip.dataset.theme === themePreset && !customBg);
      });
    }
  }

  function persistState() {
    vscode.setState({
      taskDraft: taskInput.value,
      approve: approveCheck.checked,
      mode: modeSelect.value,
      themePreset: themePreset,
      customBg: customBg,
    });
  }

  applyTheme();

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
  window.__merisShowError = showErrorBanner;

  function setStatus(text, cls) {
    statusEl.textContent = text;
    statusEl.className = "status " + (cls || "idle");
  }

  function setRunning(isRunning) {
    running = isRunning;
    const submit = document.getElementById("submit-btn");
    const stop = document.getElementById("stop-btn");
    if (submit) {
      submit.disabled = isRunning;
      submit.classList.toggle("hidden", isRunning);
    }
    if (stop) {
      stop.disabled = !isRunning;
      stop.classList.toggle("hidden", !isRunning);
    }
    modeSelect.disabled = isRunning;
    approveCheck.disabled = isRunning;
    updateSessionItemsDisabled(isRunning);
    ratchetList.querySelectorAll(".ratchet-item").forEach((el) => {
      if (isRunning) el.classList.add("disabled");
      else el.classList.remove("disabled");
    });
  }

  function updateComposerModeLabel() {
    const pill = document.getElementById("composer-agent-pill");
    const label = document.getElementById("composer-mode-label");
    if (!label || !modeSelect) return;
    const mode = modeSelect.value || "run";
    const names = { run: "@Agent", ask: "@Ask", plan: "@Plan" };
    label.textContent = names[mode] || "@Agent";
    if (pill) {
      pill.classList.remove("mode-ask", "mode-plan");
      if (mode === "ask") pill.classList.add("mode-ask");
      if (mode === "plan") pill.classList.add("mode-plan");
    }
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
    function inlineFmt(s) {
      let h = escapeHtml(s);
      h = h.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
      h = h.replace(/`([^`]+)`/g, '<code class="md-inline">$1</code>');
      return h;
    }

    const parts = [];
    const lines = text.split("\n");
    let i = 0;
    let inCode = false;
    let codeBuf = [];
    let tableRows = [];

    function flushTable() {
      if (tableRows.length < 2) {
        parts.push('<p class="md-p">' + inlineFmt(tableRows.join(" ")) + "</p>");
        tableRows = [];
        return;
      }
      let html = '<table class="md-table"><thead><tr>';
      tableRows[0]
        .split("|")
        .map((c) => c.trim())
        .filter(Boolean)
        .forEach((c) => {
          html += "<th>" + inlineFmt(c) + "</th>";
        });
      html += "</tr></thead><tbody>";
      for (let r = 2; r < tableRows.length; r++) {
        const cells = tableRows[r]
          .split("|")
          .map((c) => c.trim())
          .filter(Boolean);
        if (!cells.length) continue;
        html += "<tr>";
        cells.forEach((c) => {
          html += "<td>" + inlineFmt(c) + "</td>";
        });
        html += "</tr>";
      }
      html += "</tbody></table>";
      parts.push(html);
      tableRows = [];
    }

    while (i < lines.length) {
      const line = lines[i];
      if (line.trim().startsWith("```")) {
        if (inCode) {
          parts.push('<pre class="md-code">' + escapeHtml(codeBuf.join("\n")) + "</pre>");
          codeBuf = [];
          inCode = false;
        } else {
          inCode = true;
        }
        i++;
        continue;
      }
      if (inCode) {
        codeBuf.push(line);
        i++;
        continue;
      }
      if (line.includes("|") && line.trim().startsWith("|")) {
        tableRows.push(line);
        i++;
        if (i >= lines.length || !lines[i].includes("|")) flushTable();
        continue;
      }
      if (tableRows.length) flushTable();

      const h3 = line.match(/^### (.+)$/);
      const h2 = line.match(/^## (.+)$/);
      const h1 = line.match(/^# (.+)$/);
      if (h3) {
        parts.push('<h3 class="md-h3">' + inlineFmt(h3[1]) + "</h3>");
        i++;
        continue;
      }
      if (h2) {
        parts.push('<h2 class="md-h2">' + inlineFmt(h2[1]) + "</h2>");
        i++;
        continue;
      }
      if (h1) {
        parts.push('<h1 class="md-h1">' + inlineFmt(h1[1]) + "</h1>");
        i++;
        continue;
      }
      if (/^[-*] /.test(line)) {
        let ul = '<ul class="md-ul">';
        while (i < lines.length && /^[-*] /.test(lines[i])) {
          ul += "<li>" + inlineFmt(lines[i].replace(/^[-*] /, "")) + "</li>";
          i++;
        }
        ul += "</ul>";
        parts.push(ul);
        continue;
      }
      if (/^\d+\. /.test(line)) {
        let ol = '<ol class="md-ol">';
        while (i < lines.length && /^\d+\. /.test(lines[i])) {
          ol += "<li>" + inlineFmt(lines[i].replace(/^\d+\. /, "")) + "</li>";
          i++;
        }
        ol += "</ol>";
        parts.push(ol);
        continue;
      }
      if (line.trim() === "") {
        parts.push('<div class="md-spacer"></div>');
        i++;
        continue;
      }
      parts.push('<p class="md-p">' + inlineFmt(line) + "</p>");
      i++;
    }
    if (inCode && codeBuf.length) {
      parts.push('<pre class="md-code">' + escapeHtml(codeBuf.join("\n")) + "</pre>");
    }
    if (tableRows.length) flushTable();
    return parts.join("");
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
    el.innerHTML = '<div class="entry-body md-body"></div>';
    const body = el.querySelector(".entry-body");
    if (initial) body.textContent = initial;
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

  function sessionGroupLabel(mtime) {
    if (!mtime) return "更早";
    const diff = Date.now() / 1000 - mtime;
    if (diff < 86400) return "今天";
    if (diff < 86400 * 7) return "本周";
    if (diff < 86400 * 365) return "今年内";
    return "更早";
  }

  function renderSessions(sessions) {
    if (!sessionList) return;
    sessionList.innerHTML = "";
    if (!sessions || !sessions.length) {
      sessionList.innerHTML = '<div class="sessions-empty">暂无历史记录</div>';
      return;
    }
    const groups = new Map();
    for (const s of sessions) {
      const label = sessionGroupLabel(s.mtime);
      if (!groups.has(label)) groups.set(label, []);
      groups.get(label).push(s);
    }
    const order = ["今天", "本周", "今年内", "更早"];
    for (const label of order) {
      const items = groups.get(label);
      if (!items || !items.length) continue;
      const section = document.createElement("div");
      section.className = "history-group";
      const head = document.createElement("div");
      head.className = "history-group-title";
      head.textContent = label;
      section.appendChild(head);
      const ul = document.createElement("ul");
      ul.className = "history-group-list";
      for (const s of items) {
        const li = document.createElement("li");
        li.className = "session-item";
        if (s.id === activeSessionId) li.classList.add("active");
        if (!RESUMABLE.has(s.status)) li.classList.add("disabled");
        li.dataset.sessionId = s.id;
        const task = (s.task || "").trim() || "(无任务描述)";
        li.innerHTML =
          '<div class="session-task" title="' +
          escapeHtml(task) +
          '">' +
          escapeHtml(task.slice(0, 80)) +
          "</div>" +
          '<div class="session-meta">' +
          escapeHtml(s.mode) +
          " · " +
          escapeHtml(s.status) +
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
        ul.appendChild(li);
      }
      section.appendChild(ul);
      sessionList.appendChild(section);
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

    if (
      window.__merisPhaseI &&
      (kind.startsWith("parallel_") || ev.parallel_index !== undefined)
    ) {
      window.__merisPhaseI.handleParallelEvent(ev);
      return;
    }

    switch (kind) {
      case "submission":
        clearEmptyHint();
        appendEntry("user", "task", ev.task || msg || "(task)");
        currentAssistantEl = null;
        break;

      case "session_start":
        if (ev.session) activeSessionId = ev.session;
        if (ev.model) {
          window.dispatchEvent(
            new MessageEvent("message", {
              data: { type: "modelBar", model: "model: " + ev.model, route: "" },
            })
          );
        }
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
        if ((msg || "").includes("model route")) {
          window.dispatchEvent(
            new MessageEvent("message", {
              data: { type: "modelBar", route: msg.slice(0, 100) },
            })
          );
        }
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
        if (window.__merisAppendFileChange) {
          window.__merisAppendFileChange(timeline, ev, renderDiffHtml);
        } else {
          appendFileChange(ev);
        }
        if (window.__merisPhaseI) window.__merisPhaseI.handlePlanEvent(ev);
        break;

      case "sensor":
        appendEntry(
          "sensor",
          "sensor " + (ev.ok === false ? "FAIL" : "PASS"),
          msg.slice(0, 1200)
        );
        if (ev.ok === false) {
          vscode.postMessage({ type: "refreshRatchet" });
        }
        break;

      case "status":
        if (msg) appendEntry("meta", "status", msg.slice(0, 400));
        break;

      case "done":
        finalizeAssistantMarkdown();
        currentAssistantEl = null;
        pendingTools.clear();
        appendEntry("done", "done", "status: " + (ev.status || msg || "completed"));
        if (ev.status === "dod_failed" || ev.status === "error") {
          vscode.postMessage({ type: "ratchetScan" });
        }
        break;

      case "plan":
        window.dispatchEvent(
          new MessageEvent("message", {
            data: { type: "plan", items: ev.items || [], path: ev.path || "" },
          })
        );
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
  modeSelect.addEventListener("change", () => {
    updateComposerModeLabel();
    persistState();
  });

  if (themePresetsEl) {
    themePresetsEl.addEventListener("click", (e) => {
      const chip = e.target.closest(".theme-chip");
      if (!chip || !chip.dataset.theme || !THEMES[chip.dataset.theme]) return;
      themePreset = chip.dataset.theme;
      customBg = "";
      applyTheme();
      persistState();
    });
  }

  if (bgColorPicker) {
    bgColorPicker.addEventListener("input", () => {
      customBg = normalizeHex(bgColorPicker.value);
      applyTheme();
      persistState();
    });
  }

  if (settingsResetBtn) {
    settingsResetBtn.addEventListener("click", () => {
      themePreset = "vibe";
      customBg = "";
      applyTheme();
      persistState();
    });
  }

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
        if (msg.highlight && window.__merisOpenRatchet) window.__merisOpenRatchet(true);
        break;

      case "ratchetAlert":
        if (window.__merisOpenRatchet) window.__merisOpenRatchet(true);
        appendEntry(
          "meta",
          "ratchet",
          "DoD/运行失败 — 已扫描 Harness 提案，见右侧 Ratchet 面板"
        );
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
    '<div class="empty-hint"><strong>开始一个任务</strong>在下方描述你想做的事，按 <kbd>Ctrl</kbd>+<kbd>Enter</kbd> 或点 Run。<br>右侧「历史」可恢复过往任务。</div>';
  vscode.postMessage({ type: "refreshSessions" });
  vscode.postMessage({ type: "refreshRatchet" });
  if (window.__merisStandalone) {
    fetch("/api/sessions")
      .then(async (r) => {
        const ct = r.headers.get("content-type") || "";
        if (!r.ok || !ct.includes("application/json")) return { sessions: [] };
        return r.json();
      })
      .then((data) => {
        if (data && data.sessions) renderSessions(data.sessions);
      })
      .catch(() => {});
  }
})();
