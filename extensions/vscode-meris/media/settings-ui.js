/* Settings center overlay */
(function () {
  const vscode = window.__merisVscode || {
    postMessage: () => {},
    getState: () => ({}),
    setState: () => {},
  };

  const standalone = typeof acquireVsCodeApi === "undefined";
  const $ = (id) => document.getElementById(id);

  const overlay = $("settings-overlay");
  const settingsBtn = $("settings-btn");
  const settingsClose = $("settings-close");
  const settingsSearch = $("settings-search");
  const navItems = document.querySelectorAll(".settings-nav-item");
  const pages = document.querySelectorAll(".settings-page");

  const mcpList = $("mcp-list");
  const mcpJsonInput = $("mcp-json-input");
  const mcpSaveBtn = $("mcp-save-btn");
  const mcpMigrateBtn = $("mcp-migrate-btn");
  const mcpJsonError = $("mcp-json-error");
  const mcpSourceHint = $("mcp-source-hint");
  const settingsSkillCards = $("settings-skill-cards");
  const skillEditorPanel = $("skill-editor-panel");
  const skillEditorTitle = $("skill-editor-title");
  const skillEditorClose = $("skill-editor-close");
  const skillsRefreshBtn = $("skills-refresh-btn");
  const skillImportPath = $("skill-import-path");
  const pickSkillImportDirBtn = $("pick-skill-import-dir-btn");
  const importSkillsBtn = $("import-skills-btn");
  const importCursorSkillsBtn = $("import-cursor-skills-btn");
  const skillsImportStatus = $("skills-import-status");
  const skillImportBrowse = $("skill-import-browse");
  const skillBrowsePath = $("skill-browse-path");
  const skillBrowseList = $("skill-browse-list");
  const skillBrowseRefreshBtn = $("skill-browse-refresh-btn");
  const skillBrowseUseBtn = $("skill-browse-use-btn");
  const skillBrowseCloseBtn = $("skill-browse-close-btn");
  const skillsOpenCommandsBtn = $("skills-open-commands-btn");
  const skillsCommandsPreview = $("skills-commands-preview");
  const skillNameInput = $("skill-name-input");
  const skillContentInput = $("skill-content-input");
  const skillCreateBtn = $("skill-create-btn");
  const skillGlobalCreateBtn = $("skill-global-create-btn");
  const skillSaveBtn = $("skill-save-btn");
  const settingsRuleList = $("settings-rule-list");
  const ruleContentInput = $("rule-content-input");
  const ruleSaveBtn = $("rule-save-btn");
  const modelsSummary = $("models-summary");
  const defaultModeSelect = $("default-mode-select");
  const defaultApproveCheck = $("default-approve-check");
  const importCursorMcpBtn = $("import-cursor-mcp-btn");
  const importCursorRulesBtn = $("import-cursor-rules-btn");
  const importMcpPathInput = $("import-mcp-path");
  const importRulesPathInput = $("import-rules-path");
  const pickImportMcpBtn = $("pick-import-mcp-btn");
  const pickImportRulesBtn = $("pick-import-rules-btn");
  const importMcpPathBtn = $("import-mcp-path-btn");
  const importRulesPathBtn = $("import-rules-path-btn");
  const importStatus = $("import-status");
  const quickMcpLink = $("quick-mcp-link");
  const composerToolsBtn = $("composer-tools-btn");
  const composerSettingsBtn = $("composer-settings-btn");
  const docsIndexList = $("docs-index-list");
  const docsPreview = $("docs-preview");
  const commandsGroups = $("commands-groups");
  const commandsSearch = $("commands-search");
  const composerHelpBtn = $("composer-help-btn");
  const settingsProjectBanner = $("settings-project-banner");
  const settingsProjectRoot = $("settings-project-root");

  const HARNESS_SETTINGS_PAGES = new Set([
    "agent",
    "models",
    "mcp",
    "skills",
    "rules",
    "commands",
    "import",
  ]);

  if (!overlay) return;

  let mcpDraft = [];
  const selectedMcp = new Set();
  let activeSkill = "";
  /** @type {"installed"|"global"|"builtin"} */
  let activeSkillTarget = "installed";
  let activeRule = "";
  let activeDocId = "";
  /** @type {object[]} */
  let skillsCatalog = [];
  /** @type {{disabled?: string[], importSourcePath?: string}} */
  let skillPrefs = { disabled: [], importSourcePath: "" };
  /** @type {{groups: object[]}} */
  let commandsCatalog = { groups: [] };

  function post(msg) {
    if (standalone) {
      fetch("/api/cmd", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(msg),
      }).catch(() => {});
      return;
    }
    vscode.postMessage(msg);
  }

  function fetchJson(url) {
    return fetch(url).then((r) => (r.ok ? r.json() : {}));
  }

  function loadProjectRootLabel() {
    if (!settingsProjectRoot) return;
    if (standalone) {
      fetchJson("/api/health").then((h) => {
        if (h && h.cwd) settingsProjectRoot.textContent = h.cwd;
      });
      return;
    }
    post({ type: "getWorkspace" });
  }

  function updateHarnessBanner(page) {
    if (!settingsProjectBanner) return;
    settingsProjectBanner.classList.toggle("hidden", !HARNESS_SETTINGS_PAGES.has(page));
  }

  function openSettings(page) {
    overlay.classList.remove("hidden");
    overlay.setAttribute("aria-hidden", "false");
    if (page) switchPage(page);
    loadProjectRootLabel();
    post({ type: "listMcp" });
    post({ type: "listSkills" });
    post({ type: "listRules" });
    post({ type: "getModels" });
    post({ type: "listDocs" });
  }

  function closeSettings() {
    overlay.classList.add("hidden");
    overlay.setAttribute("aria-hidden", "true");
  }

  window.__merisOpenSettings = openSettings;

  function switchPage(name) {
    navItems.forEach((n) => n.classList.toggle("active", n.dataset.settings === name));
    pages.forEach((p) => {
      const on = p.dataset.settings === name;
      p.classList.toggle("hidden", !on);
      p.classList.toggle("active", on);
    });
    updateHarnessBanner(name);
  }

  navItems.forEach((btn) => {
    btn.addEventListener("click", () => {
      const page = btn.dataset.settings || "general";
      switchPage(page);
      if (page === "docs") post({ type: "listDocs" });
      if (page === "commands") loadCommandsCatalog();
      if (page === "skills") {
        post({ type: "listSkills" });
        loadSkillsCommandsPreview();
      }
      if (page === "mcp") post({ type: "listMcp" });
    });
  });

  if (settingsBtn) {
    settingsBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (overlay.classList.contains("hidden")) openSettings("general");
      else closeSettings();
    });
  }
  if (settingsClose) settingsClose.addEventListener("click", closeSettings);
  if (quickMcpLink) quickMcpLink.addEventListener("click", () => openSettings("mcp"));
  if (composerToolsBtn) {
    composerToolsBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openSettings("mcp");
    });
  }
  if (composerSettingsBtn) {
    composerSettingsBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (overlay.classList.contains("hidden")) openSettings("general");
      else closeSettings();
    });
  }
  if (composerHelpBtn) {
    composerHelpBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openSettings("commands");
    });
  }

  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) closeSettings();
  });

  if (settingsSearch) {
    settingsSearch.addEventListener("input", () => {
      const q = settingsSearch.value.trim().toLowerCase();
      navItems.forEach((n) => {
        const label = (n.textContent || "").toLowerCase();
        n.classList.toggle("hidden", Boolean(q) && !label.includes(q));
      });
    });
  }

  function mcpItemsToJsonText(items) {
    const servers = {};
    (items || []).forEach((srv) => {
      if (!srv.name) return;
      const entry = {};
      if (srv.url) entry.url = srv.url;
      else {
        if (srv.command) entry.command = srv.command;
        if (srv.args && srv.args.length) entry.args = srv.args;
      }
      if (srv.env && Object.keys(srv.env).length) entry.env = srv.env;
      if (srv.enabled === false) entry.enabled = false;
      servers[srv.name] = entry;
    });
    return JSON.stringify({ mcpServers: servers }, null, 2);
  }

  function parseMcpJsonText(text) {
    const data = JSON.parse(text);
    const raw = data.mcpServers || data;
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw new Error("需要 mcpServers 对象");
    return Object.entries(raw).map(([name, cfg]) => {
      const c = cfg && typeof cfg === "object" ? cfg : {};
      return {
        name,
        enabled: c.enabled !== false && !c.disabled,
        transport: c.url ? "sse" : "stdio",
        command: c.command || "",
        args: Array.isArray(c.args) ? c.args : [],
        url: c.url || "",
        env: c.env || {},
      };
    });
  }

  function showMcpError(text) {
    if (!mcpJsonError) return;
    if (!text) {
      mcpJsonError.classList.add("hidden");
      mcpJsonError.textContent = "";
      return;
    }
    mcpJsonError.textContent = text;
    mcpJsonError.classList.remove("hidden");
  }

  function updateMcpQuickLink() {
    if (!quickMcpLink) return;
    const n = (window.__merisSelectedMcp || []).length;
    quickMcpLink.textContent = n ? `MCP (${n})` : "MCP";
  }

  function refreshHarnessSettings() {
    loadProjectRootLabel();
    post({ type: "listMcp" });
    post({ type: "listSkills" });
    post({ type: "listRules" });
    post({ type: "getModels" });
    if (commandsGroups && !commandsGroups.innerHTML) loadCommandsCatalog();
  }

  window.__merisRefreshHarnessSettings = refreshHarnessSettings;

  function updateMcpSourceHint(source) {
    if (!mcpSourceHint) return;
    const base =
      "外挂工具服务。绿点=已连接，红点=失败，灰点=已禁用。";
    if (source === "settings") {
      mcpSourceHint.textContent =
        "当前读取自 settings.yaml 的 mcpServers（尚未在 UI 保存过）。在下方编辑并保存后将写入 .meris/ui/mcp-servers.json 并优先生效。 " +
        base;
      return;
    }
    mcpSourceHint.textContent =
      "当前读取自 .meris/ui/mcp-servers.json（覆盖 settings.yaml）。在下方编辑后点保存。 " + base;
  }

  function renderMcp(info) {
    if (info && info.source) updateMcpSourceHint(info.source);
    if (mcpMigrateBtn) {
      const showMigrate =
        info && info.source === "settings" && info.servers && info.servers.length > 0;
      mcpMigrateBtn.classList.toggle("hidden", !showMigrate);
    }
    mcpDraft = (info && info.servers ? [...info.servers] : mcpDraft) || [];
    if (mcpList) {
      mcpList.innerHTML = "";
      if (!mcpDraft.length) {
        mcpList.innerHTML = '<li class="empty-hint">未配置 MCP — 在下方 JSON 添加</li>';
      }
      mcpDraft.forEach((srv, idx) => {
        const li = document.createElement("li");
        li.className = "settings-mcp-item";
        const dot = document.createElement("span");
        const conn = srv.connection || (srv.enabled === false ? "disabled" : "unknown");
        dot.className = "mcp-status-dot mcp-status-" + conn;
        dot.title = srv.connectionDetail || conn;
        const cb = document.createElement("input");
        cb.type = "checkbox";
        cb.checked = srv.enabled !== false;
        cb.addEventListener("change", () => {
          mcpDraft[idx].enabled = cb.checked;
          if (cb.checked) selectedMcp.add(srv.name);
          else selectedMcp.delete(srv.name);
          window.__merisSelectedMcp = Array.from(selectedMcp);
          updateMcpQuickLink();
        });
        const label = document.createElement("span");
        label.textContent = srv.name + " — " + (srv.command || srv.url || "");
        if (srv.connectionDetail && conn === "ok") {
          label.title = srv.connectionDetail;
        }
        li.appendChild(dot);
        li.appendChild(cb);
        li.appendChild(label);
        mcpList.appendChild(li);
        if (cb.checked) selectedMcp.add(srv.name);
      });
    }
    window.__merisSelectedMcp = Array.from(selectedMcp);
    if (mcpJsonInput) {
      mcpJsonInput.value = mcpItemsToJsonText(mcpDraft);
      showMcpError("");
    }
    updateMcpQuickLink();
  }

  function postJson(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    }).then(async (r) => {
      let data = {};
      try {
        data = await r.json();
      } catch {
        data = {};
      }
      return { ok: r.ok, data };
    });
  }

  let skillBrowseCurrentPath = "";

  function setSkillImportPathDisplay(path) {
    if (!skillImportPath) return;
    const p = (path || "").trim();
    skillImportPath.textContent = p || "未选择目录";
    skillImportPath.title = p || "";
  }

  function loadSkillBrowse(absPath) {
    if (!standalone || !skillBrowseList) return;
    const q = absPath ? "?path=" + encodeURIComponent(absPath) : "";
    fetch("/api/browse" + q)
      .then((r) => {
        if (!r.ok) throw new Error("browse " + r.status);
        return r.json();
      })
      .then((data) => {
        skillBrowseCurrentPath = data.path || "";
        if (skillBrowsePath) {
          skillBrowsePath.textContent = data.label || data.path || "此电脑";
          skillBrowsePath.title = data.path || "";
        }
        skillBrowseList.innerHTML = "";
        (data.entries || []).forEach((ent) => {
          const li = document.createElement("li");
          li.className = "folder-browse-item" + (ent.isParent ? " is-parent" : "");
          li.textContent = ent.isParent ? ent.name : "📁 " + ent.name;
          li.title = ent.path;
          li.addEventListener("dblclick", () => loadSkillBrowse(ent.path));
          li.addEventListener("click", () => {
            if (ent.isParent) {
              loadSkillBrowse(ent.path);
              return;
            }
            skillBrowseCurrentPath = ent.path;
          });
          skillBrowseList.appendChild(li);
        });
        if (!(data.entries || []).length && data.path) {
          skillBrowseCurrentPath = data.path;
          skillBrowseList.innerHTML =
            '<li class="empty-hint">无子文件夹 — 可点「使用此目录」选中当前路径</li>';
        }
      })
      .catch(() => {
        if (skillBrowseList) {
          skillBrowseList.innerHTML =
            '<li class="empty-hint">目录浏览失败 — 请重启 meris ui 后刷新页面</li>';
        }
      });
  }

  function toggleSkillBrowse(show) {
    if (!skillImportBrowse) return;
    const on = show !== false;
    skillImportBrowse.classList.toggle("hidden", !on);
    if (on) {
      fetchJson("/api/health")
        .then((h) => loadSkillBrowse((h && h.cwd) || skillBrowseCurrentPath || ""))
        .catch(() => loadSkillBrowse(skillBrowseCurrentPath || ""));
    }
  }

  function applySkillImportResult(data) {
    if (!data) return;
    if (data.prefs) applySkillPrefs(data.prefs);
    else if (data.path) setSkillImportPathDisplay(data.path);
    if (data.skills) renderSkills(data.skills, data.prefs);
    if (data.detail && skillsImportStatus) skillsImportStatus.textContent = data.detail;
  }

  function applySkillPrefs(prefs) {
    skillPrefs = prefs || { disabled: [], importSourcePath: "" };
    setSkillImportPathDisplay(skillPrefs.importSourcePath || "");
  }

  function appendSkillCard(container, sk) {
    const card = document.createElement("article");
    card.className = "skill-card";
    if (!sk.enabled) card.classList.add("skill-card-disabled");
    if (sk.readonly) card.classList.add("skill-card-readonly");

    const head = document.createElement("div");
    head.className = "skill-card-head";
    const icon = document.createElement("span");
    icon.className = "skill-card-icon";
    icon.textContent = sk.icon || "📋";
    const meta = document.createElement("div");
    meta.className = "skill-card-meta";
    const title = document.createElement("h4");
    title.className = "skill-card-title";
    title.textContent = sk.title || sk.name;
    if (sk.source === "global") {
      const badge = document.createElement("span");
      badge.className = "skill-source-badge";
      badge.textContent = "全局";
      title.appendChild(document.createTextNode(" "));
      title.appendChild(badge);
    }
    const desc = document.createElement("p");
    desc.className = "skill-card-desc";
    desc.textContent = sk.description || "";
    meta.appendChild(title);
    meta.appendChild(desc);
    head.appendChild(icon);
    head.appendChild(meta);

    const actions = document.createElement("div");
    actions.className = "skill-card-actions";

    if (sk.source === "installed" || sk.source === "global") {
      const toggleLabel = document.createElement("label");
      toggleLabel.className = "skill-toggle";
      toggleLabel.title = sk.enabled ? "禁用技能" : "启用技能";
      const toggle = document.createElement("input");
      toggle.type = "checkbox";
      toggle.checked = Boolean(sk.enabled);
      toggle.addEventListener("change", (e) => {
        e.stopPropagation();
        post({ type: "toggleSkillEnabled", name: sk.name, enabled: toggle.checked });
      });
      const slider = document.createElement("span");
      slider.className = "skill-toggle-slider";
      toggleLabel.appendChild(toggle);
      toggleLabel.appendChild(slider);
      actions.appendChild(toggleLabel);
    } else if (!sk.installed) {
      const installBtn = document.createElement("button");
      installBtn.type = "button";
      installBtn.className = "skill-install-btn";
      installBtn.textContent = "安装到项目";
      installBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        post({ type: "installBundledSkill", name: sk.name, forEditor: true, target: "installed" });
      });
      actions.appendChild(installBtn);
      const installGlobalBtn = document.createElement("button");
      installGlobalBtn.type = "button";
      installGlobalBtn.className = "skill-install-btn secondary-btn";
      installGlobalBtn.textContent = "安装到全局";
      installGlobalBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        post({ type: "installBundledToGlobal", name: sk.name, forEditor: true });
      });
      actions.appendChild(installGlobalBtn);
    }

    const gearBtn = document.createElement("button");
    gearBtn.type = "button";
    gearBtn.className = "icon-btn skill-gear-btn";
    gearBtn.title = sk.readonly ? "预览" : "编辑";
    gearBtn.textContent = "⚙";
    gearBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openSkillEditor(sk);
    });
    actions.appendChild(gearBtn);

    card.appendChild(head);
    card.appendChild(actions);
    card.addEventListener("click", () => openSkillEditor(sk));
    container.appendChild(card);
  }

  function renderSkillCards() {
    if (!settingsSkillCards) return;
    const installed = (skillsCatalog || []).filter((sk) => sk.source === "installed");
    const global = (skillsCatalog || []).filter((sk) => sk.source === "global");
    const templates = (skillsCatalog || []).filter((sk) => sk.source === "builtin");
    settingsSkillCards.innerHTML = "";

    if (!installed.length && !global.length && !templates.length) {
      const empty = document.createElement("p");
      empty.className = "empty-hint";
      empty.textContent = ".meris/skills/ 为空 — 点「+ 创建」或从本地目录导入";
      settingsSkillCards.appendChild(empty);
      return;
    }

    function appendGroup(title, items, emptyText) {
      if (!items.length) {
        if (emptyText) {
          const empty = document.createElement("p");
          empty.className = "empty-hint";
          empty.textContent = emptyText;
          settingsSkillCards.appendChild(empty);
        }
        return;
      }
      const h = document.createElement("h4");
      h.className = "skills-group-title";
      h.textContent = title;
      settingsSkillCards.appendChild(h);
      const grid = document.createElement("div");
      grid.className = "skill-cards-grid";
      items.forEach((sk) => appendSkillCard(grid, sk));
      settingsSkillCards.appendChild(grid);
    }

    appendGroup(
      "已安装（当前项目）",
      installed,
      "尚无项目技能 — 可创建、导入或从模板安装"
    );
    appendGroup("全局", global, null);
    appendGroup("内置模板", templates, null);
  }

  function openSkillEditor(sk) {
    if (!skillEditorPanel) return;
    activeSkill = sk.name;
    activeSkillTarget =
      sk.source === "global" ? "global" : sk.source === "builtin" ? "builtin" : "installed";
    if (skillEditorTitle) {
      const label = sk.title || sk.name;
      skillEditorTitle.textContent =
        activeSkillTarget === "global" ? `${label}（全局）` : label;
    }
    if (skillContentInput) {
      skillContentInput.readOnly = sk.source === "builtin";
    }
    if (skillSaveBtn) {
      skillSaveBtn.classList.toggle("hidden", sk.source === "builtin");
    }
    skillEditorPanel.classList.remove("hidden");
    post({ type: "readSkill", name: sk.name, forEditor: true });
  }

  function openNewSkillEditor(target) {
    activeSkillTarget = target === "global" ? "global" : "installed";
    const name = skillNameInput ? skillNameInput.value.trim() : "";
    const template = name
      ? `---\nname: ${name}\ndescription: 简要说明何时使用此技能\n---\n\n# ${name}\n\n`
      : `---\nname: my-skill\ndescription: 简要说明何时使用此技能\n---\n\n# My Skill\n\n`;
    if (skillEditorPanel) skillEditorPanel.classList.remove("hidden");
    if (skillContentInput) {
      skillContentInput.value = template;
      skillContentInput.readOnly = false;
    }
    if (skillSaveBtn) skillSaveBtn.classList.remove("hidden");
    if (skillEditorTitle) {
      skillEditorTitle.textContent =
        activeSkillTarget === "global" ? "新建全局技能" : "新建项目技能";
    }
    activeSkill = name || "";
  }

  function closeSkillEditor() {
    activeSkill = "";
    activeSkillTarget = "installed";
    if (skillEditorPanel) skillEditorPanel.classList.add("hidden");
    if (skillContentInput) {
      skillContentInput.value = "";
      skillContentInput.readOnly = false;
    }
    if (skillSaveBtn) skillSaveBtn.classList.remove("hidden");
  }

  function renderSkills(skills, prefs) {
    skillsCatalog = skills || [];
    if (prefs) applySkillPrefs(prefs);
    renderSkillCards();
    const enabledInstalled = skillsCatalog.filter(
      (sk) => (sk.source === "installed" || sk.source === "global") && sk.enabled
    );
    if (window.__merisRenderAtSkills) window.__merisRenderAtSkills(enabledInstalled);
  }

  const SKILLS_PREVIEW_CMDS = [
    "meris doctor",
    "meris harness check",
    "meris dogfood",
    "meris ratchet status",
    "meris mcp list",
    "meris session list",
  ];

  function loadSkillsCommandsPreview() {
    if (!skillsCommandsPreview) return;
    const render = (groups) => {
      skillsCommandsPreview.innerHTML = "";
      const byCmd = new Map();
      (groups || []).forEach((g) => {
        (g.commands || []).forEach((c) => {
          if (c.cmd) byCmd.set(c.cmd, c);
        });
      });
      const ul = document.createElement("ul");
      ul.className = "commands-list skills-cmd-preview-list";
      SKILLS_PREVIEW_CMDS.forEach((cmd) => {
        const info = byCmd.get(cmd) || { cmd, summary: cmd, ui: false };
        const li = document.createElement("li");
        li.className = "command-row";
        const code = document.createElement("code");
        code.className = "command-cmd";
        code.textContent = info.cmd;
        code.title = "点击复制";
        code.addEventListener("click", (e) => {
          e.stopPropagation();
          copyText(info.cmd).then(() => {
            code.classList.add("copied");
            setTimeout(() => code.classList.remove("copied"), 900);
          });
        });
        const span = document.createElement("span");
        span.className = "command-summary";
        span.textContent = info.summary || "";
        li.appendChild(code);
        li.appendChild(span);
        if (info.ui) {
          const runBtn = document.createElement("button");
          runBtn.type = "button";
          runBtn.className = "command-run-btn";
          runBtn.title = "在终端运行";
          runBtn.textContent = "▶";
          runBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            post({ type: "runCliCommand", cmd: info.cmd });
            closeSettings();
          });
          li.appendChild(runBtn);
        }
        ul.appendChild(li);
      });
      skillsCommandsPreview.appendChild(ul);
    };
    if (commandsCatalog.groups && commandsCatalog.groups.length) {
      render(commandsCatalog.groups);
      return;
    }
    if (standalone) {
      fetchJson("/api/commands").then((data) => {
        commandsCatalog = data || { groups: [] };
        render(commandsCatalog.groups || []);
      });
      return;
    }
    post({ type: "listCommands" });
    const onMsg = (ev) => {
      const msg = ev.data || {};
      if (msg.type === "commandsList") {
        commandsCatalog = { groups: msg.groups || [] };
        render(commandsCatalog.groups || []);
        window.removeEventListener("message", onMsg);
      }
    };
    window.addEventListener("message", onMsg);
  }

  function renderRules(rules) {
    if (!settingsRuleList) return;
    settingsRuleList.innerHTML = "";
    if (!rules || !rules.length) {
      settingsRuleList.innerHTML = '<li class="empty-hint">.meris/rules/ 为空</li>';
      return;
    }
    rules.forEach((r) => {
      const li = document.createElement("li");
      li.textContent = r.name;
      li.classList.toggle("active", r.name === activeRule);
      li.addEventListener("click", () => {
        activeRule = r.name;
        post({ type: "readRule", name: r.name });
      });
      settingsRuleList.appendChild(li);
    });
  }

  function loadCommandsCatalog() {
    if (standalone) {
      fetchJson("/api/commands").then((data) => {
        commandsCatalog = data || { groups: [] };
        renderCommands(commandsCatalog.groups || []);
      });
      return;
    }
    post({ type: "listCommands" });
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    return Promise.resolve();
  }

  function renderCommands(groups, filter) {
    if (!commandsGroups) return;
    const q = (filter || "").trim().toLowerCase();
    commandsGroups.innerHTML = "";
    if (!groups || !groups.length) {
      commandsGroups.innerHTML = '<p class="empty-hint">无命令索引</p>';
      return;
    }
    groups.forEach((group) => {
      const cmds = (group.commands || []).filter((c) => {
        if (!q) return true;
        const hay = [c.cmd, c.summary, c.ui, group.title].join(" ").toLowerCase();
        return hay.includes(q);
      });
      if (!cmds.length) return;

      const section = document.createElement("section");
      section.className = "commands-group";
      const h3 = document.createElement("h3");
      h3.className = "commands-group-title";
      h3.textContent = group.title || group.id || "命令";
      section.appendChild(h3);
      if (group.hint) {
        const hint = document.createElement("p");
        hint.className = "commands-group-hint";
        hint.textContent = group.hint;
        section.appendChild(hint);
      }
      const ul = document.createElement("ul");
      ul.className = "commands-list";
      cmds.forEach((c) => {
        const li = document.createElement("li");
        li.className = "commands-item";
        const row = document.createElement("div");
        row.className = "commands-item-row";
        const main = document.createElement("button");
        main.type = "button";
        main.className = "commands-item-btn";
        const cmdEl = document.createElement("code");
        cmdEl.className = "commands-cmd";
        cmdEl.textContent = c.cmd || "";
        const sum = document.createElement("span");
        sum.className = "commands-summary";
        sum.textContent = c.summary || "";
        main.appendChild(cmdEl);
        main.appendChild(sum);
        if (c.ui) {
          const badge = document.createElement("span");
          badge.className = "cmd-ui-badge";
          badge.textContent = "UI · " + c.ui;
          main.appendChild(badge);
        }
        main.addEventListener("click", () => {
          copyText(c.cmd || "").then(() => {
            main.classList.add("copied");
            setTimeout(() => main.classList.remove("copied"), 1200);
          });
        });
        row.appendChild(main);
        if (c.runnable) {
          const runBtn = document.createElement("button");
          runBtn.type = "button";
          runBtn.className = "commands-run-btn";
          runBtn.title = "在 Terminal 运行";
          runBtn.setAttribute("aria-label", "运行");
          runBtn.textContent = "▶";
          runBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            runCliCommand(c.id);
          });
          row.appendChild(runBtn);
        }
        li.appendChild(row);
        ul.appendChild(li);
      });
      section.appendChild(ul);
      commandsGroups.appendChild(section);
    });
    if (!commandsGroups.children.length) {
      commandsGroups.innerHTML = '<p class="empty-hint">无匹配命令</p>';
    }
  }

  function runCliCommand(id) {
    if (!id) return;
    closeSettings();
    if (window.__merisClearTerminal) window.__merisClearTerminal();
    post({ type: "runCliCommand", id });
  }

  if (commandsSearch) {
    commandsSearch.addEventListener("input", () => {
      renderCommands(commandsCatalog.groups || [], commandsSearch.value);
    });
  }

  function renderDocs(docs) {
    if (!docsIndexList) return;
    docsIndexList.innerHTML = "";
    if (!docs || !docs.length) {
      docsIndexList.innerHTML = '<li class="empty-hint">无文档索引</li>';
      return;
    }
    docs.forEach((doc) => {
      const li = document.createElement("li");
      li.innerHTML =
        "<strong>" +
        (doc.title || doc.id) +
        "</strong><br><span class=\"settings-doc-blurb\">" +
        (doc.blurb || doc.path || "") +
        "</span>";
      li.classList.toggle("active", doc.id === activeDocId);
      li.addEventListener("click", () => {
        activeDocId = doc.id;
        post({ type: "readDoc", id: doc.id });
        docsIndexList.querySelectorAll("li").forEach((el) => el.classList.remove("active"));
        li.classList.add("active");
      });
      docsIndexList.appendChild(li);
    });
  }

  function renderModels(info) {
    if (!modelsSummary || !info) return;
    const lines = [];
    lines.push("<div><strong>默认</strong> " + (info.defaultModel || "auto") + "</div>");
    const bm = info.byMode || {};
    Object.keys(bm).forEach((mode) => {
      lines.push("<div><strong>byMode." + mode + "</strong> " + (bm[mode] || "—") + "</div>");
    });
    (info.rules || []).forEach((r) => {
      lines.push("<div><strong>rule " + r.name + "</strong> " + (r.model || r.profile || "—") + "</div>");
    });
    modelsSummary.innerHTML = lines.join("") || '<div class="empty-hint">未配置 models 路由</div>';
  }

  if (mcpSaveBtn) {
    mcpSaveBtn.addEventListener("click", () => {
      if (!mcpJsonInput) return;
      try {
        post({ type: "saveMcpServers", servers: parseMcpJsonText(mcpJsonInput.value.trim()) });
        showMcpError("");
      } catch (e) {
        showMcpError("JSON 无效: " + (e.message || e));
      }
    });
  }

  if (mcpMigrateBtn) {
    mcpMigrateBtn.addEventListener("click", () => {
      post({ type: "migrateMcpToUi" });
    });
  }

  if (skillCreateBtn) {
    skillCreateBtn.addEventListener("click", () => openNewSkillEditor("installed"));
  }

  if (skillGlobalCreateBtn) {
    skillGlobalCreateBtn.addEventListener("click", () => openNewSkillEditor("global"));
  }

  if (skillEditorClose) {
    skillEditorClose.addEventListener("click", closeSkillEditor);
  }

  if (skillsRefreshBtn) {
    skillsRefreshBtn.addEventListener("click", () => post({ type: "listSkills" }));
  }

  if (pickSkillImportDirBtn) {
    pickSkillImportDirBtn.addEventListener("click", () => {
      if (standalone) {
        toggleSkillBrowse(true);
        if (skillsImportStatus) skillsImportStatus.textContent = "在下方浏览并选中目录";
        return;
      }
      post({ type: "pickSkillImportDir" });
      if (skillsImportStatus) skillsImportStatus.textContent = "请选择目录…";
    });
  }

  if (skillBrowseRefreshBtn) {
    skillBrowseRefreshBtn.addEventListener("click", () => loadSkillBrowse(skillBrowseCurrentPath || ""));
  }

  if (skillBrowseCloseBtn) {
    skillBrowseCloseBtn.addEventListener("click", () => toggleSkillBrowse(false));
  }

  if (skillBrowseUseBtn) {
    skillBrowseUseBtn.addEventListener("click", () => {
      const path = (skillBrowseCurrentPath || "").trim();
      if (!path) {
        if (skillsImportStatus) skillsImportStatus.textContent = "请先浏览并选中目录";
        return;
      }
      if (standalone) {
        postJson("/api/skills/set-source", { path }).then(({ ok, data }) => {
          if (!ok) {
            if (skillsImportStatus) skillsImportStatus.textContent = data.error || "设置目录失败";
            return;
          }
          applySkillImportResult(data);
          if (skillsImportStatus) skillsImportStatus.textContent = "已选择目录";
          toggleSkillBrowse(false);
        });
        return;
      }
      post({ type: "saveSkillPrefs", importSourcePath: path });
      setSkillImportPathDisplay(path);
      if (skillsImportStatus) skillsImportStatus.textContent = "已选择目录";
      toggleSkillBrowse(false);
    });
  }

  if (importSkillsBtn) {
    importSkillsBtn.addEventListener("click", () => {
      if (skillsImportStatus) skillsImportStatus.textContent = "正在导入…";
      if (standalone) {
        const path = (skillPrefs.importSourcePath || skillBrowseCurrentPath || "").trim();
        postJson("/api/skills/import", path ? { path } : {}).then(({ ok, data }) => {
          applySkillImportResult(data);
          if (!ok && skillsImportStatus) {
            skillsImportStatus.textContent = data.detail || data.error || "导入失败";
          }
        });
        return;
      }
      post({ type: "importSkills" });
    });
  }

  if (importCursorSkillsBtn) {
    importCursorSkillsBtn.addEventListener("click", () => {
      if (skillsImportStatus) skillsImportStatus.textContent = "正在从 .cursor/skills 导入…";
      post({ type: "importCursorSkills" });
    });
  }

  if (skillsOpenCommandsBtn) {
    skillsOpenCommandsBtn.addEventListener("click", () => switchPage("commands"));
  }

  if (skillSaveBtn) {
    skillSaveBtn.addEventListener("click", () => {
      const content = skillContentInput ? skillContentInput.value : "";
      let name = activeSkill;
      if (!name && skillNameInput) name = skillNameInput.value.trim();
      if (!name) {
        const m = content.match(/^---[\s\S]*?^name:\s*(.+)$/m);
        if (m) name = m[1].trim().replace(/^['"]|['"]$/g, "");
      }
      if (!name) return;
      activeSkill = name;
      const saveType = activeSkillTarget === "global" ? "saveGlobalSkill" : "saveSkill";
      post({ type: saveType, name, content, forEditor: true, target: activeSkillTarget });
    });
  }

  if (ruleSaveBtn) {
    ruleSaveBtn.addEventListener("click", () => {
      if (!activeRule) return;
      post({
        type: "saveRule",
        name: activeRule,
        content: ruleContentInput ? ruleContentInput.value : "",
      });
    });
  }

  if (importCursorMcpBtn) {
    importCursorMcpBtn.addEventListener("click", () => {
      post({ type: "importCursorMcp" });
      if (importStatus) importStatus.textContent = "正在导入 MCP…";
    });
  }

  if (importCursorRulesBtn) {
    importCursorRulesBtn.addEventListener("click", () => {
      post({ type: "importCursorRules" });
      if (importStatus) importStatus.textContent = "正在导入规则…";
    });
  }

  if (importMcpPathBtn) {
    importMcpPathBtn.addEventListener("click", () => {
      const p = importMcpPathInput ? importMcpPathInput.value.trim() : "";
      if (!p) {
        if (importStatus) importStatus.textContent = "请填写 MCP 文件路径";
        return;
      }
      post({ type: "importMcpFromPath", path: p });
      if (importStatus) importStatus.textContent = "正在导入 MCP…";
    });
  }

  if (importRulesPathBtn) {
    importRulesPathBtn.addEventListener("click", () => {
      const p = importRulesPathInput ? importRulesPathInput.value.trim() : "";
      if (!p) {
        if (importStatus) importStatus.textContent = "请填写规则目录路径";
        return;
      }
      post({ type: "importRulesFromPath", path: p });
      if (importStatus) importStatus.textContent = "正在导入规则…";
    });
  }

  if (pickImportMcpBtn) {
    pickImportMcpBtn.addEventListener("click", () => {
      post({ type: "pickImportMcpFile" });
    });
  }

  if (pickImportRulesBtn) {
    pickImportRulesBtn.addEventListener("click", () => {
      post({ type: "pickImportRulesDir" });
    });
  }

  const saved = vscode.getState() || {};
  if (defaultModeSelect && saved.defaultMode) {
    defaultModeSelect.value = saved.defaultMode;
    const modeSelect = $("mode-select");
    if (modeSelect) modeSelect.value = saved.defaultMode;
  }
  if (defaultApproveCheck && saved.defaultApprove) {
    defaultApproveCheck.checked = true;
    const approveCheck = $("approve-check");
    if (approveCheck) approveCheck.checked = true;
  }

  if (defaultModeSelect) {
    defaultModeSelect.addEventListener("change", () => {
      const modeSelect = $("mode-select");
      if (modeSelect) modeSelect.value = defaultModeSelect.value;
      const s = vscode.getState() || {};
      s.defaultMode = defaultModeSelect.value;
      vscode.setState(s);
    });
  }
  if (defaultApproveCheck) {
    defaultApproveCheck.addEventListener("change", () => {
      const approveCheck = $("approve-check");
      if (approveCheck) approveCheck.checked = defaultApproveCheck.checked;
      const s = vscode.getState() || {};
      s.defaultApprove = defaultApproveCheck.checked;
      vscode.setState(s);
    });
  }

  window.addEventListener("message", (event) => {
    const msg = event.data;
    if (!msg || !msg.type) return;
    switch (msg.type) {
      case "mcpInfo":
        renderMcp(msg);
        break;
      case "mcpImportError":
        showMcpError(msg.error || "导入失败");
        if (importStatus) importStatus.textContent = msg.error || "导入失败";
        break;
      case "skillsList":
        renderSkills(msg.skills || [], msg.prefs);
        break;
      case "skillImportSource":
        applySkillImportResult(msg);
        if (skillsImportStatus && msg.path) skillsImportStatus.textContent = "已选择目录";
        break;
      case "skillContent":
        activeSkill = msg.name || activeSkill;
        if (skillContentInput) skillContentInput.value = msg.content || "";
        if (msg.skills) renderSkills(msg.skills, msg.prefs);
        if (skillEditorPanel) skillEditorPanel.classList.remove("hidden");
        if (skillEditorTitle && activeSkill) skillEditorTitle.textContent = activeSkill;
        break;
      case "rulesList":
        renderRules(msg.rules || []);
        break;
      case "ruleContent":
        activeRule = msg.name || activeRule;
        if (ruleContentInput) ruleContentInput.value = msg.content || "";
        break;
      case "modelsInfo":
        renderModels(msg);
        break;
      case "commandsList":
        commandsCatalog = { groups: msg.groups || [] };
        renderCommands(commandsCatalog.groups, commandsSearch ? commandsSearch.value : "");
        break;
      case "docsList":
        renderDocs(msg.docs || []);
        break;
      case "docContent":
        if (docsPreview) {
          docsPreview.value =
            "# " + (msg.title || msg.id || "") + "\n# " + (msg.path || "") + "\n\n" + (msg.content || "");
        }
        break;
      case "importPathPicked":
        if (msg.kind === "mcp" && importMcpPathInput) importMcpPathInput.value = msg.path || "";
        if (msg.kind === "rules" && importRulesPathInput) importRulesPathInput.value = msg.path || "";
        break;
      case "importResult":
        if (importStatus) importStatus.textContent = msg.detail || (msg.ok ? "导入完成" : "导入失败");
        if (msg.kind === "skills" && skillsImportStatus) {
          skillsImportStatus.textContent = msg.detail || (msg.ok ? "导入完成" : "导入失败");
        }
        if (msg.ok && msg.kind === "rules") post({ type: "listRules" });
        if (msg.ok && msg.kind === "mcp") post({ type: "listMcp" });
        break;
      case "workspacePickError":
        if (skillsImportStatus) skillsImportStatus.textContent = msg.error || "选择目录失败";
        break;
      case "workspaceInfo":
        if (settingsProjectRoot && msg.cwd) settingsProjectRoot.textContent = msg.cwd;
        refreshHarnessSettings();
        break;
    }
  });

  window.__merisMcpPrefix = function () {
    const names = window.__merisSelectedMcp || [];
    if (!names.length) return "";
    return (
      "Use MCP servers configured for this workspace: " +
      names.join(", ") +
      ". Call MCP tools when they help.\n\n---\n\n"
    );
  };

  if (standalone) {
    fetchJson("/api/mcp").then((d) => renderMcp(d));
    fetchJson("/api/skills").then((d) => renderSkills(d.skills || [], d.prefs));
    fetchJson("/api/rules").then((d) => renderRules(d.rules || []));
    fetchJson("/api/models").then((d) => {
      renderModels(d);
      window.dispatchEvent(new MessageEvent("message", { data: { type: "modelsInfo", ...d } }));
    });
  } else {
    post({ type: "getModels" });
  }
})();
