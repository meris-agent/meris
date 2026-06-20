/* Phase I — vibe coding UX (loaded after agent.js) */
(function () {
  const vscode = window.__merisVscode || {
    postMessage: () => {},
    getState: () => ({}),
    setState: () => {},
  };

  const $ = (id) => document.getElementById(id);

  const contextChips = $("context-chips");
  const atBtn = $("at-btn");
  const hashBtn = $("hash-btn");
  const atDropdown = $("at-dropdown");
  const hashDropdown = $("hash-dropdown");
  const atSkillList = $("at-skill-list");
  const hashSearch = $("hash-search");
  const hashFileList = $("hash-file-list");
  const hashSelection = $("hash-selection");
  const modelSelect = $("model-select");
  const modelBar = $("model-bar");
  const modelLabel = $("model-label");
  const routeLabel = $("route-label");
  const sessionSearch = $("session-search");
  const terminalOutput = $("terminal-output");
  const terminalPanel = $("terminal-panel");
  const planList = $("plan-list");
  const planRunBtn = $("plan-run-btn");
  const planPanel = $("plan-panel");
  const parallelInput = $("parallel-input");
  const parallelRunBtn = $("parallel-run-btn");
  const parallelLanes = $("parallel-lanes");
  const parallelSummary = $("parallel-summary");
  const previewFrame = $("preview-frame");
  const previewPath = $("preview-path");
  const previewRefresh = $("preview-refresh");
  const viewTabs = document.querySelectorAll(".view-tab");
  const chatView = $("chat-view");
  const planView = $("plan-view");
  const parallelView = $("parallel-view");
  const previewView = $("preview-view");

  if (!atBtn && !hashBtn) return;

  let contextItems = [];
  let sessionsCache = [];
  let planPath = "";
  let planItems = [];
  let currentPreviewPath = "";
  /** @type {Record<number, {task: string, body: HTMLElement, assistantRaw: string, currentEl: HTMLElement|null, statusEl: HTMLElement|null}>} */
  let laneState = {};

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function buildContextPrefix() {
    let p = "";
    if (window.__merisMcpPrefix) p += window.__merisMcpPrefix();
    if (!contextItems.length) return p;
    p += "The user attached context:\n";
    for (const item of contextItems) {
      if (item.kind === "image") {
        p += `\n### Image: ${item.path}\n${item.content || "[screenshot attached]"}\n`;
        continue;
      }
      p += `\n### ${item.path}`;
      if (item.startLine) p += ` (L${item.startLine}-${item.endLine})`;
      p += `\n\`\`\`\n${(item.content || "").slice(0, 10000)}\n\`\`\`\n`;
    }
    return p + "\n---\n\n";
  }

  window.__merisAddContextItem = function (item) {
    if (!item) return;
    contextItems.push(item);
    renderContextChips();
  };

  function renderContextChips() {
    if (!contextChips) return;
    contextChips.innerHTML = "";
    for (let i = 0; i < contextItems.length; i++) {
      const chip = document.createElement("span");
      const item = contextItems[i];
      chip.className = "context-chip" + (item.kind === "image" ? " context-chip-image" : "");

      if (item.kind === "image") {
        const img = document.createElement("img");
        img.className = "context-chip-thumb";
        img.alt = "";
        if (item.previewUrl) {
          img.src = item.previewUrl;
        } else if (window.__merisStandalone) {
          img.src =
            "/api/workspace-file?path=" +
            encodeURIComponent(item.path);
        }
        chip.appendChild(img);
      }

      const label = document.createElement("span");
      label.className = "context-chip-label";
      label.textContent = item.kind === "image" ? item.path.split("/").pop() : item.path;
      chip.appendChild(label);

      const btn = document.createElement("button");
      btn.type = "button";
      btn.setAttribute("data-idx", String(i));
      btn.textContent = "×";
      btn.addEventListener("click", () => {
        contextItems.splice(i, 1);
        renderContextChips();
      });
      chip.appendChild(btn);
      contextChips.appendChild(chip);
    }
  }

  function updateModelBar(model, route) {
    if (!modelBar) return;
    if (modelLabel && model) modelLabel.textContent = model;
    if (routeLabel) routeLabel.textContent = route || "";
    modelBar.classList.toggle("hidden", !model && !route);
  }

  function appendTerminal(stream, chunk) {
    if (!terminalOutput) return;
    const span = document.createElement("span");
    span.className = stream === "stderr" ? "term-err" : "term-out";
    span.textContent = chunk;
    terminalOutput.appendChild(span);
    terminalOutput.scrollTop = terminalOutput.scrollHeight;
    if (terminalPanel) terminalPanel.open = true;
  }

  function clearTerminal() {
    if (terminalOutput) terminalOutput.textContent = "";
  }

  function switchView(name) {
    const map = { chat: chatView, plan: planView, parallel: parallelView, preview: previewView };
    viewTabs.forEach((t) => t.classList.toggle("active", t.dataset.view === name));
    Object.keys(map).forEach((k) => {
      const el = map[k];
      if (!el) return;
      const on = k === name;
      el.classList.toggle("hidden", !on);
      el.classList.toggle("active", on);
    });
  }

  viewTabs.forEach((tab) => {
    tab.addEventListener("click", () => switchView(tab.dataset.view || "chat"));
  });

  function showPlanSaved() {
    if (!planPanel) return;
    let el = planPanel.querySelector(".plan-saved");
    if (!el) {
      el = document.createElement("div");
      el.className = "plan-saved";
      planPanel.insertBefore(el, planList);
    }
    el.textContent = "已保存到 " + (planPath || "tasks.md");
    el.classList.add("visible");
    setTimeout(() => el.classList.remove("visible"), 2000);
  }

  function initParallelLanes(tasks) {
    if (!parallelLanes) return;
    laneState = {};
    parallelLanes.innerHTML = "";
    parallelLanes.classList.remove("hidden");
    if (parallelSummary) {
      parallelSummary.classList.add("hidden");
      parallelSummary.textContent = "";
    }
    tasks.forEach((task, index) => {
      const lane = document.createElement("div");
      lane.className = "parallel-lane";
      lane.innerHTML =
        '<div class="parallel-lane-head"><span class="parallel-lane-idx">#' +
        index +
        '</span><span class="parallel-lane-task"></span><span class="parallel-lane-status">running</span></div><div class="parallel-lane-body"></div>';
      lane.querySelector(".parallel-lane-task").textContent = task.slice(0, 120);
      const body = lane.querySelector(".parallel-lane-body");
      const statusEl = lane.querySelector(".parallel-lane-status");
      laneState[index] = {
        task,
        body,
        assistantRaw: "",
        currentEl: null,
        statusEl,
      };
      parallelLanes.appendChild(lane);
    });
    switchView("parallel");
  }

  function appendLaneEntry(index, kind, text) {
    const lane = laneState[index];
    if (!lane || !lane.body) return;
    if (kind === "token") {
      lane.assistantRaw += text;
      if (!lane.currentEl) {
        lane.currentEl = document.createElement("div");
        lane.currentEl.className = "parallel-lane-msg";
        lane.body.appendChild(lane.currentEl);
      }
      lane.currentEl.textContent = lane.assistantRaw.slice(-2500);
    } else {
      const el = document.createElement("div");
      el.className = "parallel-lane-entry parallel-lane-" + kind;
      el.textContent = (kind + ": " + text).slice(0, 500);
      lane.body.appendChild(el);
      if (kind === "tool_start" || kind === "done") {
        lane.currentEl = null;
        lane.assistantRaw = "";
      }
    }
    lane.body.scrollTop = lane.body.scrollHeight;
  }

  function renderPlan(items, path) {
    if (!planList) return;
    planPath = path || planPath;
    planItems = items || planItems;
    const empty = planPanel && planPanel.querySelector(".plan-empty");
    if (empty) empty.classList.toggle("hidden", planItems.length > 0);
    planList.innerHTML = "";
    planItems.forEach((item, idx) => {
      const li = document.createElement("li");
      li.className = "plan-item";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = !!item.done;
      cb.addEventListener("change", () => {
        planItems[idx].done = cb.checked;
        vscode.postMessage({ type: "savePlan", path: planPath, items: planItems });
      });
      const label = document.createElement("span");
      label.textContent = item.text;
      li.appendChild(cb);
      li.appendChild(label);
      planList.appendChild(li);
    });
    if (planRunBtn) planRunBtn.classList.toggle("hidden", planItems.length === 0);
    switchView("plan");
  }

  function parseDiffHunks(diff) {
    const hunks = [];
    let cur = null;
    const lines = diff.split("\n");
    let fileHeader = [];
    for (const line of lines) {
      if (line.startsWith("---") || line.startsWith("+++")) {
        fileHeader.push(line);
        continue;
      }
      if (line.startsWith("@@")) {
        if (cur) hunks.push(cur);
        cur = { header: line, lines: [...fileHeader, line], fileHeader: [...fileHeader] };
      } else if (cur) {
        cur.lines.push(line);
      }
    }
    if (cur) hunks.push(cur);
    return hunks;
  }

  function renderHunkActions(container, filePath, hunk) {
    const actions = document.createElement("div");
    actions.className = "hunk-actions";
    const accept = document.createElement("button");
    accept.type = "button";
    accept.textContent = "Accept hunk";
    accept.addEventListener("click", () => {
      vscode.postMessage({
        type: "applyHunk",
        path: filePath,
        patch: hunk.lines.join("\n"),
      });
    });
    const reject = document.createElement("button");
    reject.type = "button";
    reject.textContent = "Skip";
    reject.className = "hunk-skip";
    actions.appendChild(accept);
    actions.appendChild(reject);
    container.appendChild(actions);
  }

  window.__merisAppendFileChange = function (timeline, ev, renderDiffHtml) {
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
      const hunks = parseDiffHunks(diff);
      if (hunks.length > 1) {
        hunks.forEach((h, i) => {
          const block = document.createElement("div");
          block.className = "hunk-block";
          block.innerHTML =
            '<div class="hunk-title">Hunk ' +
            (i + 1) +
            "</div><div class=\"diff-preview\">" +
            renderDiffHtml(h.lines.join("\n").slice(0, 2000)) +
            "</div>";
          renderHunkActions(block, rel, h);
          details.appendChild(block);
        });
      } else {
        const diffEl = document.createElement("div");
        diffEl.className = "entry-body diff-preview";
        diffEl.innerHTML = renderDiffHtml(diff.slice(0, 5000));
        details.appendChild(diffEl);
        if (hunks[0]) renderHunkActions(details, rel, hunks[0]);
      }
    }
    const row = document.createElement("div");
    row.className = "file-actions";
    const openBtn = document.createElement("button");
    openBtn.className = "file-open-btn";
    openBtn.textContent = "Open";
    openBtn.addEventListener("click", () => vscode.postMessage({ type: "openFile", path: rel }));
    row.appendChild(openBtn);
    if (/\.(html?|htm)$/i.test(rel)) {
      const prevBtn = document.createElement("button");
      prevBtn.className = "file-preview-btn";
      prevBtn.textContent = "Preview";
      prevBtn.addEventListener("click", () => {
        vscode.postMessage({ type: "loadPreview", path: rel });
      });
      row.appendChild(prevBtn);
    }
    details.appendChild(row);
    timeline.appendChild(details);
    timeline.scrollTop = timeline.scrollHeight;
  };

  window.__merisRenderAtSkills = function (skills) {
    if (!atSkillList) return;
    atSkillList.innerHTML = "";
    if (!skills || !skills.length) {
      atSkillList.innerHTML = '<li class="empty-hint">无 skill — 在设置中创建</li>';
      return;
    }
    const project = skills.filter((s) => s.source === "installed");
    const global = skills.filter((s) => s.source === "global");
    const other = skills.filter((s) => s.source !== "installed" && s.source !== "global");

    function appendGroup(title, items) {
      if (!items.length) return;
      const head = document.createElement("li");
      head.className = "at-skill-group-title";
      head.textContent = title;
      atSkillList.appendChild(head);
      items.forEach((sk) => {
        const li = document.createElement("li");
        li.textContent = sk.title ? `${sk.title} (${sk.name})` : sk.name;
        li.addEventListener("click", () => {
          vscode.postMessage({ type: "readSkill", name: sk.name });
          if (atDropdown) atDropdown.classList.add("hidden");
        });
        atSkillList.appendChild(li);
      });
    }

    appendGroup("当前项目", project);
    appendGroup("全局", global);
    appendGroup("其他", other);
  };

  if (atBtn && atDropdown) {
    atBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      atDropdown.classList.toggle("hidden");
      if (hashDropdown) hashDropdown.classList.add("hidden");
      if (!atDropdown.classList.contains("hidden")) {
        vscode.postMessage({ type: "listSkills" });
      }
    });
  }

  if (hashBtn && hashDropdown) {
    hashBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      hashDropdown.classList.toggle("hidden");
      if (atDropdown) atDropdown.classList.add("hidden");
      if (!hashDropdown.classList.contains("hidden")) {
        vscode.postMessage({ type: "listContextFiles", query: "" });
        if (hashSearch) hashSearch.focus();
      }
    });
  }

  if (hashSearch) {
    let debounce = null;
    hashSearch.addEventListener("input", () => {
      clearTimeout(debounce);
      debounce = setTimeout(() => {
        vscode.postMessage({ type: "listContextFiles", query: hashSearch.value.trim() });
      }, 200);
    });
  }

  if (hashSelection) {
    hashSelection.addEventListener("click", () => {
      vscode.postMessage({ type: "addContextSelection" });
      if (hashDropdown) hashDropdown.classList.add("hidden");
    });
  }

  document.addEventListener("click", (e) => {
    if (!e.target.closest("#at-btn") && !e.target.closest("#at-dropdown") && atDropdown) {
      atDropdown.classList.add("hidden");
    }
    if (!e.target.closest("#hash-btn") && !e.target.closest("#hash-dropdown") && hashDropdown) {
      hashDropdown.classList.add("hidden");
    }
  });

  if (modelSelect) {
    modelSelect.addEventListener("change", () => {
      const s = vscode.getState() || {};
      s.modelOverride = modelSelect.value;
      vscode.setState(s);
    });
    const saved = vscode.getState() || {};
    if (saved.modelOverride && modelSelect.querySelector('option[value="' + saved.modelOverride + '"]')) {
      modelSelect.value = saved.modelOverride;
    }
  }

  if (sessionSearch) {
    sessionSearch.addEventListener("input", () => {
      const q = sessionSearch.value.trim().toLowerCase();
      const filtered = sessionsCache.filter(
        (s) =>
          !q ||
          (s.task || "").toLowerCase().includes(q) ||
          (s.id || "").toLowerCase().includes(q)
      );
      window.dispatchEvent(
        new MessageEvent("message", { data: { type: "sessions", sessions: filtered } })
      );
    });
  }

  function renderParallelSummary(code) {
    if (!parallelSummary) return;
    const lanes = Object.keys(laneState)
      .map(Number)
      .sort((a, b) => a - b);
    if (!lanes.length) return;
    const rows = lanes.map((i) => {
      const lane = laneState[i];
      const status = (lane.statusEl && lane.statusEl.textContent) || "unknown";
      const task = (lane.task || "").slice(0, 80);
      return `#${i} ${status} — ${task}`;
    });
    const ok = lanes.filter((i) => {
      const s = (laneState[i].statusEl && laneState[i].statusEl.textContent) || "";
      return s === "completed" || s === "done";
    }).length;
    parallelSummary.classList.remove("hidden");
    parallelSummary.innerHTML =
      `<strong>Parallel 汇总</strong> · ${ok}/${lanes.length} 完成` +
      (code !== 0 ? " · 进程退出码 " + code : "") +
      `<ul class="parallel-summary-list">${rows
        .map((r) => "<li>" + escapeHtml(r) + "</li>")
        .join("")}</ul>`;
  }

  if (planRunBtn) {
    planRunBtn.addEventListener("click", () => {
      const pending = planItems.filter((i) => !i.done);
      if (!pending.length) return;
      const task =
        pending.length === planItems.length
          ? "implement the plan"
          : "Implement plan:\n" + pending.map((i) => "- [ ] " + i.text).join("\n");
      vscode.postMessage({
        type: "planRun",
        task,
        planPath: planPath || ".meris/plan/tasks.md",
        markDone: pending.map((i) => i.text),
        approve: false,
      });
      switchView("chat");
    });
  }

  if (parallelRunBtn && parallelInput) {
    parallelRunBtn.addEventListener("click", () => {
      const tasks = parallelInput.value
        .split("\n")
        .map((t) => t.trim())
        .filter(Boolean);
      if (!tasks.length) return;
      initParallelLanes(tasks);
      vscode.postMessage({ type: "parallelRun", tasks, mode: "ask" });
    });
  }

  if (previewRefresh) {
    previewRefresh.addEventListener("click", () => {
      if (currentPreviewPath) {
        vscode.postMessage({ type: "loadPreview", path: currentPreviewPath });
      }
    });
  }

  const submitBtn = $("submit-btn");
  if (submitBtn && submitBtn.parentNode) {
    const newSubmit = submitBtn.cloneNode(true);
    submitBtn.parentNode.replaceChild(newSubmit, submitBtn);
    newSubmit.addEventListener("click", () => {
      const taskInput = $("task-input");
      const modeSelect = $("mode-select");
      const approveCheck = $("approve-check");
      const task = (taskInput && taskInput.value.trim()) || "";
      if (!task || newSubmit.disabled) return;
      const fullTask = buildContextPrefix() + task;
      vscode.postMessage({
        type: "submit",
        task: fullTask,
        displayTask: task,
        mode: modeSelect ? modeSelect.value : "run",
        approve: approveCheck ? approveCheck.checked : false,
        context: contextItems,
      });
    });
  }

  window.addEventListener("message", (event) => {
    const msg = event.data;
    if (!msg || !msg.type) return;
    switch (msg.type) {
      case "cliRunStart":
        clearTerminal();
        appendTerminal("stdout", "$ " + (msg.cmd || "meris") + "\n");
        break;
      case "cliRunDone":
        if (window.__merisComposerHint) {
          const label = msg.ok ? "命令完成" : "命令失败 (exit " + (msg.code ?? "?") + ")";
          window.__merisComposerHint(label, msg.ok ? "ok" : "error");
        }
        break;
      case "terminal":
        appendTerminal(msg.stream || "stdout", msg.chunk || "");
        break;
      case "contextFiles":
        if (!hashFileList) break;
        hashFileList.innerHTML = "";
        (msg.files || []).forEach((f) => {
          const li = document.createElement("li");
          li.textContent = f;
          li.addEventListener("click", () => {
            vscode.postMessage({ type: "readContextFile", path: f });
            if (hashDropdown) hashDropdown.classList.add("hidden");
          });
          hashFileList.appendChild(li);
        });
        break;
      case "skillsList":
        if (window.__merisRenderAtSkills) window.__merisRenderAtSkills(msg.skills || []);
        break;
      case "modelsInfo":
        if (modelSelect) {
          const cur = modelSelect.value;
          modelSelect.innerHTML = '<option value="auto">Auto</option>';
          const bm = msg.byMode || {};
          Object.keys(bm).forEach((mode) => {
            if (!bm[mode]) return;
            const opt = document.createElement("option");
            opt.value = "mode:" + mode;
            opt.textContent = mode + " → " + bm[mode];
            modelSelect.appendChild(opt);
          });
          if (msg.defaultModel && msg.defaultModel !== "auto") {
            const opt = document.createElement("option");
            opt.value = "default";
            opt.textContent = "default → " + msg.defaultModel;
            modelSelect.appendChild(opt);
          }
          if (cur && modelSelect.querySelector('option[value="' + cur + '"]')) modelSelect.value = cur;
        }
        break;
      case "contextItem":
        if (msg.item) {
          contextItems.push(msg.item);
          renderContextChips();
          if (msg.item.kind === "image" && window.__merisComposerHint) {
            window.__merisComposerHint("已添加图片", "ok");
          }
        }
        break;
      case "contextImageError":
        if (window.__merisComposerHint) {
          window.__merisComposerHint(msg.error || "图片保存失败", "error");
        }
        break;
      case "modelBar":
        updateModelBar(msg.model, msg.route);
        break;
      case "plan":
        renderPlan(msg.items || [], msg.path || "");
        break;
      case "planSaved":
        if (msg.path) planPath = msg.path;
        if (msg.items) planItems = msg.items;
        showPlanSaved();
        break;
      case "parallelStart":
        initParallelLanes(msg.tasks || []);
        break;
      case "preview":
        currentPreviewPath = msg.path || "";
        if (previewPath) previewPath.textContent = currentPreviewPath;
        if (previewFrame) previewFrame.srcdoc = msg.html || "";
        switchView("preview");
        break;
      case "sessions":
        sessionsCache = msg.sessions || [];
        break;
      case "parallelDone":
        renderParallelSummary(msg.code);
        break;
      case "ratchetAlert":
        if (window.__merisOpenRatchet) window.__merisOpenRatchet(true);
        break;
      case "runStart":
        clearTerminal();
        contextItems = [];
        renderContextChips();
        break;
    }
  });

  window.__merisPhaseI = {
    handlePlanEvent(ev) {
      if (ev.kind === "plan") renderPlan(ev.items || [], ev.path || "");
      if (ev.kind === "session_start" && ev.model) {
        updateModelBar("model: " + ev.model, "");
        window.dispatchEvent(
          new MessageEvent("message", { data: { type: "modelBar", model: "model: " + ev.model } })
        );
      }
      if (ev.kind === "thinking" && (ev.message || "").includes("model route")) {
        updateModelBar(modelLabel ? modelLabel.textContent : "", ev.message.slice(0, 80));
      }
    },
    handleParallelEvent(ev) {
      const kind = ev.kind || "";
      const idx = ev.parallel_index;
      if (kind === "parallel_start") {
        const tasks = (ev.tasks || []).map((x) => x.task || String(x));
        if (tasks.length) initParallelLanes(tasks);
        return;
      }
      if (kind === "parallel_task_done" && idx !== undefined && laneState[idx]?.statusEl) {
        laneState[idx].statusEl.textContent = ev.status || "done";
        return;
      }
      if (kind === "parallel_done") {
        renderParallelSummary(0);
        return;
      }
      if (idx === undefined) return;
      const msg = ev.message || "";
      switch (kind) {
        case "token":
          appendLaneEntry(idx, "token", msg);
          break;
        case "tool_start":
          appendLaneEntry(idx, "tool_start", ev.tool || "tool");
          break;
        case "tool_end":
          appendLaneEntry(idx, "tool_end", msg.slice(0, 200));
          break;
        case "session_start":
          appendLaneEntry(idx, "session_start", (ev.session || "").slice(0, 8));
          break;
        case "done":
          appendLaneEntry(idx, "done", ev.status || "completed");
          if (laneState[idx]?.statusEl) laneState[idx].statusEl.textContent = ev.status || "done";
          break;
        default:
          if (msg) appendLaneEntry(idx, kind, msg.slice(0, 200));
      }
    },
  };

  window.__merisClearTerminal = clearTerminal;
  window.__merisAppendTerminal = appendTerminal;
})();
