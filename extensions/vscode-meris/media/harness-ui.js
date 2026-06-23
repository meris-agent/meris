/* Harness UI — workspace picker & file tree */
(function () {
  const vscode = window.__merisVscode || {
    postMessage: () => {},
    getState: () => ({}),
    setState: () => {},
  };

  const standalone = typeof acquireVsCodeApi === "undefined";
  const $ = (id) => document.getElementById(id);

  const workspaceSelect = $("workspace-select");
  const addWorkspaceRootBtn = $("add-workspace-root-btn");
  const manageWorkspaceRootsBtn = $("manage-workspace-roots-btn");
  const workspaceCollapseAllBtn = $("workspace-collapse-all-btn");
  const workspaceManagePopover = $("workspace-manage-popover");
  const workspaceRootsList = $("workspace-roots-list");
  const fileTree = $("file-tree");
  const filePanelTitle = $("file-panel-title");
  const projectList = $("project-list");
  const taskScopeCurrentBtn = $("task-scope-current-btn");
  const taskScopeAllBtn = $("task-scope-all-btn");
  const taskScopeChips = $("task-scope-chips");
  const historyPanel = $("history-panel");
  const ratchetPanel = $("ratchet-panel");
  const rightTabs = document.querySelectorAll(".right-tab");

  if (!fileTree) return;

  let currentCwd = "";
  let lastWorkspaceFolders = [];
  let lastPersistedRoots = [];
  /** @type {{name:string,path:string,selected?:boolean,isCwd?:boolean}[]} */
  let lastTaskScope = [];
  const expandedScopeRoots = new Set();
  const expandedDirs = new Set();
  /** @type {Record<string, object[]>} */
  let dirCache = {};

  function apiErrorMessage(status, text) {
    const t = String(text || "").trim();
    if (t.startsWith("<!") || t.includes("<html")) {
      return status === 404
        ? "API 不可用 — 请重启 meris ui 后 Ctrl+Shift+R 刷新"
        : `服务器错误 (${status}) — 请重启 meris ui`;
    }
    if (t.includes("Unexpected token '<'")) {
      return "API 返回了 HTML 而非 JSON — 请重启 meris ui";
    }
    return t.slice(0, 160) || `request failed (${status})`;
  }

  function post(msg) {
    if (standalone) {
      return fetch("/api/cmd", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(msg),
      })
        .then(async (r) => {
          const ct = r.headers.get("content-type") || "";
          let data = {};
          if (ct.includes("application/json")) {
            try {
              data = await r.json();
            } catch {
              data = {};
            }
          } else if (!r.ok) {
            const text = await r.text().catch(() => "");
            throw new Error(apiErrorMessage(r.status, text));
          }
          if (!r.ok) {
            throw new Error(apiErrorMessage(r.status, data.error || ""));
          }
          return data;
        })
        .catch((err) => {
          const quiet = msg.type === "setTaskScope";
          if (!quiet) setWorkspaceStatus(String(err.message || err), "err");
          return null;
        });
    }
    vscode.postMessage(msg);
    return Promise.resolve(null);
  }

  function samePath(a, b) {
    return (
      String(a || "")
        .replace(/\\/g, "/")
        .replace(/\/+$/, "")
        .toLowerCase() ===
      String(b || "")
        .replace(/\\/g, "/")
        .replace(/\/+$/, "")
        .toLowerCase()
    );
  }

  function formatFolderLabel(f) {
    const parts = String(f.path || "").replace(/\\/g, "/").split("/").filter(Boolean);
    const tail = parts.length > 2 ? parts.slice(-2).join("/") : f.path;
    return `${f.name || "project"} · ${tail}`;
  }

  function dedupeFolders(folders) {
    const seen = new Set();
    const out = [];
    (folders || []).forEach((f) => {
      if (!f || !f.path) return;
      const key = String(f.path).replace(/\\/g, "/").replace(/\/+$/, "").toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      out.push(f);
    });
    return out;
  }

  function folderOptionLabels(folders) {
    const unique = dedupeFolders(folders);
    const counts = {};
    unique.forEach((f) => {
      const lbl = formatFolderLabel(f);
      counts[lbl] = (counts[lbl] || 0) + 1;
    });
    return unique.map((f) => {
      let label = formatFolderLabel(f);
      if (counts[label] > 1) {
        const parts = String(f.path || "").replace(/\\/g, "/").split("/").filter(Boolean);
        const tail = parts.length > 3 ? parts.slice(-4).join("/") : f.path;
        label = `${f.name || "project"} · ${tail}`;
      }
      return { folder: f, label };
    });
  }

  function setWorkspaceStatus(text, kind) {
    const status = document.getElementById("status");
    if (!status) return;
    status.textContent = text;
    status.className = "status idle" + (kind ? " " + kind : "");
  }

  function isLikelySkillRoot(p) {
    const norm = String(p || "")
      .replace(/\\/g, "/")
      .toLowerCase();
    if (norm.includes("/.system/")) return true;
    if (
      norm.includes("/.cursor/skills/") ||
      norm.includes("/.meris/skills/") ||
      norm.includes("/templates/skills/") ||
      norm.includes("/.agents/skills/")
    ) {
      return true;
    }
    return false;
  }

  function filterProjectRoots(folders) {
    return (folders || []).filter((f) => f && f.path && !isLikelySkillRoot(f.path));
  }

  function broadcastWorkspaceInfo(info) {
    if (!info) return;
    window.dispatchEvent(new MessageEvent("message", { data: { type: "workspaceInfo", ...info } }));
  }

  function applyWorkspacePayload(info) {
    if (!info) return;
    renderWorkspace(info);
    broadcastWorkspaceInfo(info);
    const action = info.workspaceAction || "switch";
    if (action === "add") {
      const path = info.addedPath || "";
      const msg = info.alreadyExists
        ? `已在项目列表：${path}`
        : `已添加项目：${path}`;
      setWorkspaceStatus(msg, "ok");
      if (folderModalHint) {
        folderModalHint.textContent = `✓ ${msg}。可继续添加，或点「切换到此目录」。`;
      }
      return;
    }
    if (action === "switch") {
      hideFolderModal();
      hideManagePopover();
      setWorkspaceStatus(`当前项目：${info.cwdLabel || info.cwd || ""}`, "ok");
      rebuildTree();
      return;
    }
    renderManageRoots();
    rebuildTree();
  }

  function fetchJson(url) {
    return fetch(url).then((r) => (r.ok ? r.json() : {}));
  }

  function switchRightPanel(name) {
    rightTabs.forEach((t) => t.classList.toggle("active", t.dataset.right === name));
    if (historyPanel) historyPanel.classList.toggle("hidden", name !== "history");
    if (ratchetPanel) ratchetPanel.classList.toggle("hidden", name !== "ratchet");
  }

  window.__merisOpenRatchet = function (highlight) {
    switchRightPanel("ratchet");
    if (highlight && ratchetPanel) {
      ratchetPanel.classList.add("ratchet-highlight");
      setTimeout(() => ratchetPanel.classList.remove("ratchet-highlight"), 2400);
    }
  };

  rightTabs.forEach((tab) => {
    tab.addEventListener("click", () => switchRightPanel(tab.dataset.right || "history"));
  });

  function renderManageRoots() {
    if (!workspaceRootsList) return;
    const countEl = $("workspace-root-count");
    workspaceRootsList.innerHTML = "";
    const folders = filterProjectRoots(
      lastPersistedRoots.length
        ? lastPersistedRoots
        : currentCwd
          ? [{ name: currentCwd.split(/[/\\]/).pop() || "project", path: currentCwd }]
          : []
    );
    if (countEl) countEl.textContent = folders.length ? `(${folders.length})` : "";
    folders.forEach((f) => {
      const li = document.createElement("li");
      li.className = "workspace-root-item" + (samePath(f.path, currentCwd) ? " is-active" : "");
      const label = document.createElement("span");
      label.className = "workspace-root-path";
      label.textContent = samePath(f.path, currentCwd) ? `${f.path} （主项目）` : f.path;
      label.title = f.path;
      label.addEventListener("click", () => {
        if (!samePath(f.path, currentCwd)) {
          post({ type: "setWorkspace", path: f.path }).then((data) => {
            if (data && data.workspace) {
              applyWorkspacePayload({ ...data.workspace, workspaceAction: "switch" });
            }
          });
        }
        hideManagePopover();
      });
      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "workspace-root-remove";
      removeBtn.textContent = "×";
      removeBtn.title = "移除此文件夹";
      removeBtn.disabled = samePath(f.path, currentCwd);
      removeBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        removeWorkspaceRootPath(f.path);
      });
      li.appendChild(label);
      li.appendChild(removeBtn);
      workspaceRootsList.appendChild(li);
    });
  }

  function getProjectOptions() {
    const raw = lastPersistedRoots.length
      ? lastPersistedRoots
      : lastWorkspaceFolders.length
        ? lastWorkspaceFolders
        : currentCwd
          ? [{ name: currentCwd.split(/[/\\]/).pop() || "project", path: currentCwd }]
          : [];
    return dedupeFolders(filterProjectRoots(raw));
  }

  function getProjectScopeItems() {
    if (lastTaskScope.length) return lastTaskScope;
    return getProjectOptions().map((f) => ({
      name: f.name,
      path: f.path,
      selected: samePath(f.path, currentCwd),
      isCwd: samePath(f.path, currentCwd),
    }));
  }

  function getSelectedScopeRoots() {
    const selected = getProjectScopeItems()
      .filter((i) => i.selected)
      .map((i) => ({ path: i.path, name: i.name || i.path.split(/[/\\]/).pop() || "project" }));
    return dedupeFolders(selected);
  }

  function scopeRootKey(rootPath) {
    return String(rootPath || "")
      .replace(/\\/g, "/")
      .replace(/\/+$/, "")
      .toLowerCase();
  }

  function renderProjectList() {
    if (!projectList) return;
    projectList.innerHTML = "";
    const items = getProjectScopeItems();
    if (!items.length) {
      const empty = document.createElement("p");
      empty.className = "file-tree-empty";
      empty.textContent = "点 + 添加项目，勾选后下方显示文件";
      projectList.appendChild(empty);
      renderTaskScopeChips();
      rebuildTree();
      return;
    }
    const labeled = folderOptionLabels(items.map((i) => ({ name: i.name, path: i.path })));
    labeled.forEach(({ folder: f, label }, idx) => {
      const item = items[idx];
      const isMain = Boolean(item.isCwd);
      const row = document.createElement("div");
      row.className = "project-item" + (isMain ? " is-main" : "");
      row.title = item.path;

      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.className = "project-scope-check";
      cb.checked = Boolean(item.selected);
      cb.title = "纳入本轮 Agent 范围";
      cb.addEventListener("change", () => {
        const selected = [];
        const nextScope = getProjectScopeItems().map((ent, rowIdx) => {
          const rowEl = projectList.querySelectorAll(".project-item")[rowIdx];
          const input = rowEl && rowEl.querySelector(".project-scope-check");
          const on = Boolean(input && input.checked);
          if (on) selected.push(ent.path);
          return { ...ent, selected: on };
        });
        lastTaskScope = nextScope;
        renderTaskScopeChips();
        rebuildTree();
        persistTaskScope(selected);
      });

      const mainBtn = document.createElement("button");
      mainBtn.type = "button";
      mainBtn.className = "project-main-btn" + (isMain ? " is-active" : "");
      mainBtn.textContent = isMain ? "★" : "☆";
      mainBtn.title = isMain ? "主项目 (cwd)" : "设为主项目";
      mainBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        if (!isMain) {
          const paths = getProjectScopeItems()
            .filter((i) => i.selected || samePath(i.path, item.path))
            .map((i) => i.path);
          if (!paths.some((p) => samePath(p, item.path))) paths.push(item.path);
          lastTaskScope = getProjectOptions().map((f) => ({
            name: f.name,
            path: f.path,
            selected: paths.some((p) => samePath(p, f.path)),
            isCwd: samePath(f.path, item.path),
          }));
          persistTaskScope(paths);
          openWorkspacePath(item.path);
        }
      });

      const name = document.createElement("span");
      name.className = "project-item-label";
      name.textContent = label;

      row.appendChild(cb);
      row.appendChild(mainBtn);
      row.appendChild(name);
      if (isMain) {
        const badge = document.createElement("span");
        badge.className = "project-main-badge";
        badge.textContent = "主";
        badge.title = "主项目 (cwd)";
        row.appendChild(badge);
      }
      projectList.appendChild(row);
    });
    renderTaskScopeChips();
    rebuildTree();
  }

  function renderTaskScopeChips() {
    if (!taskScopeChips) return;
    const selected = getProjectScopeItems().filter((i) => i.selected);
    taskScopeChips.innerHTML = "";
    if (!selected.length) return;
    selected.forEach((item) => {
      const chip = document.createElement("span");
      chip.className = "task-scope-chip" + (item.isCwd ? " is-cwd" : "");
      chip.title = item.path;
      chip.textContent = (item.isCwd ? "主 · " : "") + (item.name || item.path);
      taskScopeChips.appendChild(chip);
    });
  }

  function persistTaskScope(paths) {
    post({ type: "setTaskScope", paths: paths || [] }).then((data) => {
      if (data && data.workspace) {
        applyWorkspacePayload({ ...data.workspace, workspaceAction: "update" });
      }
    });
  }

  window.__merisGetMainCwd = function () {
    return currentCwd;
  };

  window.__merisGetTaskScopeSelected = function () {
    return getProjectScopeItems().filter((i) => i.selected).map((i) => i.path);
  };

  window.__merisProjectLabelForPath = function (p) {
    const ent = getProjectScopeItems().find((i) => samePath(i.path, p));
    if (ent && ent.name) {
      const parts = String(p || "").replace(/\\/g, "/").split("/").filter(Boolean);
      const dupes = getProjectScopeItems().filter((i) => i.name === ent.name).length;
      if (dupes > 1) {
        const tail = parts.length > 3 ? parts.slice(-4).join("/") : p;
        return `${ent.name} · ${tail}`;
      }
      return ent.name;
    }
    const folder = getProjectOptions().find((f) => samePath(f.path, p));
    if (folder) {
      const labeled = folderOptionLabels([folder])[0];
      return labeled ? labeled.label : folder.name || p;
    }
    const name = String(p || "").replace(/\\/g, "/").split("/").filter(Boolean).pop();
    return name || p;
  };

  window.__merisTaskScopePrefix = function () {
    const selected = window.__merisGetTaskScopeSelected();
    if (!selected.length) {
      return (
        "Task scope is empty — no project checked in the left sidebar. " +
        "Do not edit files until the user checks at least one project in the left sidebar.\n\n---\n\n"
      );
    }
    const lines = selected.map((p) => {
      const ent = getProjectScopeItems().find((i) => samePath(i.path, p));
      const mark = ent && ent.isCwd ? " (主项目 — shell/pytest 默认在此)" : "";
      return `- ${ent && ent.name ? ent.name + ": " : ""}${p}${mark}`;
    });
    return (
      "Task scope — you may READ and WRITE only within these project roots:\n" +
      lines.join("\n") +
      "\n\nDo not modify files outside this scope.\n\n---\n\n"
    );
  };
  function getWorkspaceSelectOptions() {
    const raw = lastWorkspaceFolders.length
      ? lastWorkspaceFolders
      : lastPersistedRoots.length
        ? lastPersistedRoots
        : currentCwd
          ? [{ name: currentCwd.split(/[/\\]/).pop() || "project", path: currentCwd }]
          : [];
    return dedupeFolders(filterProjectRoots(raw));
  }

  function renderWorkspace(info) {
    if (!info) return;
    currentCwd = info.cwd || "";
    lastWorkspaceFolders = filterProjectRoots(info.folders || []);
    lastPersistedRoots = filterProjectRoots(info.persistedRoots || []);
    lastTaskScope = Array.isArray(info.taskScope) && info.taskScope.length ? info.taskScope : [];
    if (workspaceSelect) {
      workspaceSelect.innerHTML = "";
      const options = getWorkspaceSelectOptions();
      if (!options.length && currentCwd) {
        options.push({ name: info.cwdLabel || "project", path: currentCwd });
      }
      const labeled = folderOptionLabels(options);
      labeled.forEach(({ folder: f, label }) => {
        const opt = document.createElement("option");
        opt.value = f.path;
        opt.textContent = labeled.length > 1 ? label : f.name || f.path;
        opt.title = f.path;
        if (samePath(f.path, currentCwd)) opt.selected = true;
        workspaceSelect.appendChild(opt);
      });
      if (!options.length) {
        const opt = document.createElement("option");
        opt.textContent = "未打开项目";
        workspaceSelect.appendChild(opt);
      }
      workspaceSelect.title = currentCwd ? "主项目：" + currentCwd : "选择主项目 (cwd)";
    }
    if (filePanelTitle) {
      const n = getSelectedScopeRoots().length;
      filePanelTitle.textContent = n ? `文件 · ${n} 个项目` : "文件";
      filePanelTitle.title = n
        ? "已勾选项目的文件树（Agent 可读写范围）"
        : "勾选项目后显示";
    }
    renderManageRoots();
    renderProjectList();
    dirCache = {};
    expandedDirs.clear();
    rebuildTree();
  }

  function cacheKey(root, dir) {
    return String(root || "") + "\x00" + String(dir || "");
  }

  function requestDir(root, dir) {
    const key = cacheKey(root, dir);
    if (dirCache[key]) return;
    if (standalone) {
      const rootQ = root ? "&root=" + encodeURIComponent(root) : "";
      fetchJson("/api/dir?path=" + encodeURIComponent(dir || "") + rootQ)
        .then((data) => {
          dirCache[cacheKey(root, data.dir || dir || "")] = data.entries || [];
          rebuildTree();
        })
        .catch(() => {});
      return;
    }
    post({ type: "listDir", dir: dir || "", root: root || currentCwd });
  }

  function renderTreeLevel(root, dir, container) {
    const key = cacheKey(root, dir);
    const entries = dirCache[key];
    if (!entries) {
      requestDir(root, dir);
      return;
    }
    if (!entries.length && !dir) {
      const empty = document.createElement("p");
      empty.className = "file-tree-empty";
      empty.textContent = "此目录为空或无法读取";
      container.appendChild(empty);
      return;
    }
    const ul = document.createElement("ul");
    ul.className = "file-tree-level";
    entries.forEach((ent) => {
      const li = document.createElement("li");
      li.className = "file-tree-item" + (ent.isDir ? " is-dir" : " is-file");
      const row = document.createElement("div");
      row.className = "file-tree-row";
      const entKey = cacheKey(root, ent.path);
      if (ent.isDir) {
        const toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "file-tree-toggle";
        toggle.textContent = expandedDirs.has(entKey) ? "▾" : "▸";
        toggle.addEventListener("click", (e) => {
          e.stopPropagation();
          if (expandedDirs.has(entKey)) expandedDirs.delete(entKey);
          else {
            expandedDirs.add(entKey);
            if (!dirCache[entKey]) requestDir(root, ent.path);
          }
          rebuildTree();
        });
        row.appendChild(toggle);
      } else {
        const spacer = document.createElement("span");
        spacer.className = "file-tree-spacer";
        row.appendChild(spacer);
        row.addEventListener("click", (e) => {
          if (e.shiftKey) {
            post({ type: "readContextFile", path: ent.path, root: root });
            return;
          }
          post({ type: "openFile", path: ent.path, root: root });
        });
        row.title = "打开文件 · Shift+点击 加入上下文";
        row.classList.add("clickable");
      }
      const label = document.createElement("span");
      label.className = "file-tree-label";
      label.textContent = ent.name;
      label.title = ent.path;
      row.appendChild(label);
      li.appendChild(row);
      if (ent.isDir && expandedDirs.has(entKey)) {
        const child = document.createElement("div");
        child.className = "file-tree-children";
        li.appendChild(child);
        renderTreeLevel(root, ent.path, child);
      }
      ul.appendChild(li);
    });
    container.appendChild(ul);
  }

  function rebuildTree() {
    if (!fileTree) return;
    fileTree.innerHTML = "";
    const roots = getSelectedScopeRoots();
    if (!roots.length) {
      const empty = document.createElement("p");
      empty.className = "file-tree-empty";
      empty.textContent = "请勾选上方项目";
      fileTree.appendChild(empty);
      return;
    }
    const labeled = folderOptionLabels(roots);
    labeled.forEach(({ folder: f, label }) => {
      const rootKey = scopeRootKey(f.path);
      const isCwd = samePath(f.path, currentCwd);
      const expanded = expandedScopeRoots.has(rootKey);
      const block = document.createElement("div");
      block.className = "file-tree-root" + (isCwd ? " is-active-root" : "");

      const headerRow = document.createElement("div");
      headerRow.className = "file-tree-root-header-row";

      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "file-tree-root-toggle";
      toggle.textContent = expanded ? "▾" : "▸";
      toggle.title = expanded ? "收起" : "展开";

      const header = document.createElement("button");
      header.type = "button";
      header.className = "file-tree-root-header";
      header.textContent = label;
      header.title = f.path;

      const body = document.createElement("div");
      body.className = "file-tree-root-body" + (expanded ? "" : " hidden");

      const expandRoot = () => {
        expandedScopeRoots.add(rootKey);
        body.classList.remove("hidden");
        toggle.textContent = "▾";
        if (!dirCache[cacheKey(f.path, "")]) requestDir(f.path, "");
        else renderTreeLevel(f.path, "", body);
      };

      const collapseRoot = () => {
        expandedScopeRoots.delete(rootKey);
        body.classList.add("hidden");
        toggle.textContent = "▸";
        body.innerHTML = "";
      };

      toggle.addEventListener("click", (e) => {
        e.stopPropagation();
        if (expandedScopeRoots.has(rootKey)) collapseRoot();
        else expandRoot();
      });
      header.addEventListener("click", () => {
        if (!samePath(f.path, currentCwd)) openWorkspacePath(f.path);
        if (!expandedScopeRoots.has(rootKey)) expandRoot();
      });

      headerRow.appendChild(toggle);
      headerRow.appendChild(header);
      block.appendChild(headerRow);
      block.appendChild(body);
      fileTree.appendChild(block);

      if (expanded) {
        if (!dirCache[cacheKey(f.path, "")]) requestDir(f.path, "");
        else renderTreeLevel(f.path, "", body);
      }
    });
  }

  const folderModal = $("folder-modal");
  const folderModalCancelBtn = $("folder-modal-cancel-btn");
  const folderModalHint = $("folder-modal-hint");
  const folderBrowseList = $("folder-browse-list");
  const folderBrowsePath = $("folder-browse-path");
  const folderSelectCurrentBtn = $("folder-select-current-btn");
  const folderAddRootBtn = $("folder-add-root-btn");

  function setFolderActionEnabled(path) {
    const ok = Boolean((path || "").trim());
    if (folderSelectCurrentBtn) folderSelectCurrentBtn.disabled = !ok;
    if (folderAddRootBtn) folderAddRootBtn.disabled = !ok;
  }

  let browsePath = "";
  let serverCwd = "";

  if (standalone) {
    fetchJson("/api/health").then((h) => {
      if (h && h.cwd) serverCwd = h.cwd;
    });
  }

  function loadBrowse(absPath) {
    if (!standalone) return;
    const q = absPath ? "?path=" + encodeURIComponent(absPath) : "";
    fetch("/api/browse" + q)
      .then((r) => {
        if (!r.ok) throw new Error("browse API " + r.status);
        return r.json();
      })
      .then((data) => {
        if (!data || typeof data.entries === "undefined") {
          throw new Error("browse API unavailable");
        }
        browsePath = data.path || "";
        if (folderBrowsePath) {
          folderBrowsePath.textContent = data.label || data.path || "此电脑";
          folderBrowsePath.title = data.path || "";
        }
        setFolderActionEnabled(data.path);
        if (!folderBrowseList) return;
        folderBrowseList.innerHTML = "";
        (data.entries || []).forEach((ent) => {
          const li = document.createElement("li");
          li.className = "folder-browse-item" + (ent.isParent ? " is-parent" : "");
          li.textContent = ent.isParent ? ent.name : "📁 " + ent.name;
          li.title = ent.path;
          li.addEventListener("dblclick", () => loadBrowse(ent.path));
          li.addEventListener("click", () => {
            if (ent.isParent) {
              loadBrowse(ent.path);
              return;
            }
            browsePath = ent.path;
            setFolderActionEnabled(ent.path);
          });
          folderBrowseList.appendChild(li);
        });
        if (!(data.entries || []).length) {
          folderBrowseList.innerHTML =
            '<li class="empty-hint">此目录下没有子文件夹 — 可点「切换到此目录」或「添加根目录」</li>';
          if (data.path) setFolderActionEnabled(data.path);
        }
      })
      .catch(() => {
        if (folderBrowseList) {
          folderBrowseList.innerHTML =
            '<li class="empty-hint">文件夹浏览 API 不可用。请<strong>重启 meris ui</strong> 后 Ctrl+Shift+R 刷新。</li>';
        }
        if (folderModalHint) {
          folderModalHint.textContent =
            "浏览失败：请停掉终端里的 meris ui，重新运行 meris ui，再刷新本页。";
        }
        if (absPath) {
          browsePath = absPath;
          setFolderActionEnabled(absPath);
        }
      });
  }

  function showFolderModal() {
    if (!folderModal) return;
    folderModal.classList.remove("hidden");
    folderModal.setAttribute("aria-hidden", "false");
    if (folderModalHint) {
      folderModalHint.textContent = "双击进入文件夹；单击选中后「切换到此目录」或「添加根目录」。";
    }
    fetchJson("/api/health")
      .then((h) => {
        const start = (h && h.cwd) || currentCwd || "";
        if (start) {
          browsePath = start;
          setFolderActionEnabled(start);
        }
        loadBrowse(start || "");
      })
      .catch(() => loadBrowse(currentCwd || ""));
  }

  function hideManagePopover() {
    if (!workspaceManagePopover) return;
    workspaceManagePopover.classList.add("hidden");
    workspaceManagePopover.setAttribute("aria-hidden", "true");
  }

  function positionManagePopover() {
    if (!workspaceManagePopover || !manageWorkspaceRootsBtn) return;
    const rect = manageWorkspaceRootsBtn.getBoundingClientRect();
    const popW = Math.min(340, window.innerWidth - 16);
    workspaceManagePopover.style.width = popW + "px";
    let left = rect.left;
    if (left + popW > window.innerWidth - 8) left = window.innerWidth - popW - 8;
    if (left < 8) left = 8;
    workspaceManagePopover.style.left = left + "px";
    workspaceManagePopover.style.top = rect.bottom + 6 + "px";
  }

  function toggleManagePopover() {
    if (!workspaceManagePopover) return;
    const open = workspaceManagePopover.classList.contains("hidden");
    if (open) {
      renderManageRoots();
      positionManagePopover();
      workspaceManagePopover.classList.remove("hidden");
      workspaceManagePopover.setAttribute("aria-hidden", "false");
    } else {
      hideManagePopover();
    }
  }

  function addWorkspaceRootPath(raw) {
    const path = (raw || "").trim();
    if (!path) return;
    post({ type: "addWorkspaceRoot", path }).then((data) => {
      if (data && data.workspace) {
        applyWorkspacePayload({
          ...data.workspace,
          workspaceAction: "add",
          addedPath: path,
          alreadyExists: data.alreadyExists,
        });
      } else if (data && data.message) {
        setWorkspaceStatus(data.message, "ok");
      }
    });
  }

  function removeWorkspaceRootPath(raw) {
    const path = (raw || "").trim();
    if (!path || samePath(path, currentCwd)) return;
    post({ type: "removeWorkspaceRoot", path }).then((data) => {
      if (data && data.workspace) {
        applyWorkspacePayload({ ...data.workspace, workspaceAction: data.workspace?.workspaceAction || "update" });
        setWorkspaceStatus(data.message || "已移除根目录", "ok");
      }
    });
  }

  function hideFolderModal() {
    if (!folderModal) return;
    folderModal.classList.add("hidden");
    folderModal.setAttribute("aria-hidden", "true");
  }

  function openWorkspacePath(raw) {
    const path = (raw || "").trim();
    if (!path) return;
    post({ type: "setWorkspace", path }).then((data) => {
      if (data && data.workspace) applyWorkspacePayload({ ...data.workspace, workspaceAction: "switch" });
      else hideFolderModal();
    });
  }

  function openAddWorkspaceModal() {
    if (standalone) showFolderModal();
    else post({ type: "addWorkspaceRootDialog" });
  }

  if (workspaceSelect) {
    workspaceSelect.addEventListener("change", () => {
      const path = workspaceSelect.value;
      if (path && !samePath(path, currentCwd)) {
        post({ type: "setWorkspace", path }).then((data) => {
          if (data && data.workspace) {
            applyWorkspacePayload({ ...data.workspace, workspaceAction: "switch" });
          }
        });
      }
    });
  }
  if (addWorkspaceRootBtn) addWorkspaceRootBtn.addEventListener("click", openAddWorkspaceModal);
  if (workspaceCollapseAllBtn) {
    workspaceCollapseAllBtn.addEventListener("click", () => {
      expandedDirs.clear();
      expandedScopeRoots.clear();
      rebuildTree();
    });
  }
  if (manageWorkspaceRootsBtn) {
    manageWorkspaceRootsBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleManagePopover();
    });
  }
  document.addEventListener("click", (e) => {
    if (!workspaceManagePopover || workspaceManagePopover.classList.contains("hidden")) return;
    const btn = manageWorkspaceRootsBtn;
    if (btn && (btn === e.target || btn.contains(e.target))) return;
    if (!workspaceManagePopover.contains(e.target)) hideManagePopover();
  });
  window.addEventListener("resize", () => {
    if (workspaceManagePopover && !workspaceManagePopover.classList.contains("hidden")) {
      positionManagePopover();
    }
  });
  if (folderSelectCurrentBtn) {
    folderSelectCurrentBtn.addEventListener("click", () => openWorkspacePath(browsePath));
  }
  if (folderAddRootBtn) {
    folderAddRootBtn.addEventListener("click", () => addWorkspaceRootPath(browsePath));
  }
  if (folderModalCancelBtn) folderModalCancelBtn.addEventListener("click", hideFolderModal);
  const gotoRootsBtn = $("folder-goto-roots-btn");
  const gotoHomeBtn = $("folder-goto-home-btn");
  const gotoCwdBtn = $("folder-goto-cwd-btn");
  if (gotoRootsBtn) gotoRootsBtn.addEventListener("click", () => loadBrowse(""));
  if (gotoHomeBtn) {
    gotoHomeBtn.addEventListener("click", () => {
      loadBrowse("");
      setTimeout(() => {
        const home = folderBrowseList && folderBrowseList.querySelector("li[title*='Users']");
        if (home && home.title) loadBrowse(home.title);
      }, 300);
    });
  }
  if (gotoCwdBtn) {
    gotoCwdBtn.addEventListener("click", () => {
      const p = serverCwd || currentCwd;
      if (p) loadBrowse(p);
    });
  }
  if (folderModal) {
    folderModal.addEventListener("click", (e) => {
      if (e.target === folderModal) hideFolderModal();
    });
  }

  if (taskScopeCurrentBtn) {
    taskScopeCurrentBtn.addEventListener("click", () => {
      if (!currentCwd) return;
      persistTaskScope([currentCwd]);
    });
  }
  if (taskScopeAllBtn) {
    taskScopeAllBtn.addEventListener("click", () => {
      const paths = getProjectOptions().map((f) => f.path);
      persistTaskScope(paths);
    });
  }

  window.addEventListener("message", (event) => {
    const msg = event.data;
    if (!msg || !msg.type) return;
    switch (msg.type) {
      case "workspaceInfo":
        applyWorkspacePayload(msg);
        break;
      case "workspacePickError":
        if (window.__merisShowError) window.__merisShowError(msg.error || "无法打开文件夹");
        if (folderModalHint) folderModalHint.textContent = msg.error || "操作失败，请重试。";
        showFolderModal();
        break;
      case "dirListing":
        dirCache[cacheKey(msg.root || currentCwd, msg.dir || "")] = msg.entries || [];
        rebuildTree();
        break;
      case "contextItem":
        if (msg.item && window.__merisAddContextItem) window.__merisAddContextItem(msg.item);
        break;
    }
  });

  if (standalone) {
    fetchJson("/api/workspace").then((info) => renderWorkspace(info));
  } else {
    post({ type: "getWorkspace" });
  }
})();
