/* Git changes panel — scope repos dirty summary + ship (G1/G2/G4) */
(function () {
  const vscode = window.__merisVscode || { postMessage: () => {} };
  const standalone = typeof acquireVsCodeApi === "undefined";
  const $ = (id) => document.getElementById(id);

  const gitPanel = $("git-changes-panel");
  const gitRefreshBtn = $("git-refresh-btn");
  const gitShipAllBtn = $("git-ship-all-btn");
  if (!gitPanel) return;

  /** @type {object[]} */
  let lastSummaries = [];
  /** @type {object[]} */
  let lastScopeCommits = [];
  const expandedRepos = new Set();
  /** @type {Map<string, (data: object|null) => void>} */
  const pendingCmd = new Map();
  let cmdSeq = 0;

  function scopeRoots() {
    if (typeof window.__merisGetTaskScopeSelected === "function") {
      return window.__merisGetTaskScopeSelected();
    }
    return [];
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
          if (!ct.includes("application/json")) return null;
          try {
            return await r.json();
          } catch {
            return null;
          }
        })
        .catch(() => null);
    }
    return new Promise((resolve) => {
      const id = "git-" + ++cmdSeq;
      pendingCmd.set(id, resolve);
      vscode.postMessage({ ...msg, _gitReqId: id });
      setTimeout(() => {
        if (pendingCmd.has(id)) {
          pendingCmd.delete(id);
          resolve(null);
        }
      }, 30000);
    });
  }

  function fetchSummary() {
    const roots = scopeRoots();
    if (standalone) {
      const qs = roots.map((r) => "roots=" + encodeURIComponent(r)).join("&");
      const url = "/api/git/summary" + (qs ? "?" + qs : "");
      fetch(url)
        .then((r) => r.json())
        .then((data) => applyPayload(data))
        .catch(() => {});
      return;
    }
    post({ type: "getGitSummary", roots });
  }

  function applyPayload(data) {
    if (!data) return;
    lastSummaries = Array.isArray(data.summaries) ? data.summaries : [];
    lastScopeCommits = Array.isArray(data.scopeCommits) ? data.scopeCommits : [];
    render();
  }

  function statusBadge(summary) {
    if (!summary.isRepo) return "非 git";
    const parts = [];
    if (summary.dirty) {
      const n = (summary.stagedCount || 0) + (summary.unstagedCount || 0);
      parts.push("+" + n);
    } else {
      parts.push("干净");
    }
    if (summary.ahead) parts.push("↑" + summary.ahead);
    if (summary.behind) parts.push("↓" + summary.behind);
    return parts.join(" ");
  }

  function fileStatusLabel(code) {
    const map = { M: "改", A: "增", D: "删", "?": "新", R: "移" };
    return map[code] || code || "?";
  }

  function render() {
    if (!lastSummaries.length) {
      gitPanel.innerHTML = '<div class="git-changes-empty">勾选项目后显示各仓库改动</div>';
      return;
    }
    const dirtyCount = lastSummaries.filter((s) => s.isRepo && s.dirty).length;
    if (gitShipAllBtn) {
      gitShipAllBtn.disabled = dirtyCount === 0;
      gitShipAllBtn.title = dirtyCount ? "暂存并提交范围内全部脏仓库（不 push）" : "无改动";
    }

    const blocks = lastSummaries.map((s) => {
      const key = s.path || "";
      const open = expandedRepos.has(key);
      const toggle = open ? "▾" : "▸";
      const displayName =
        typeof window.__merisProjectLabelForPath === "function"
          ? window.__merisProjectLabelForPath(key)
          : s.name || key;
      const branch = s.branch ? " · " + s.branch : "";
      const badge = statusBadge(s);
      const files = (s.files || [])
        .slice(0, 12)
        .map(
          (f) =>
            `<li class="git-file-row"><span class="git-file-st">${fileStatusLabel(f.status)}</span>` +
            `<span class="git-file-path" title="${escapeHtml(f.path)}">${escapeHtml(shortPath(f.path))}</span></li>`
        )
        .join("");
      const more =
        (s.files || []).length > 12
          ? `<li class="git-file-more">…还有 ${(s.files || []).length - 12} 个文件</li>`
          : "";
      const err = s.error ? `<div class="git-repo-error">${escapeHtml(s.error)}</div>` : "";
      const actions = s.isRepo
        ? `<div class="git-repo-actions">
            <button type="button" class="git-action-btn" data-action="stage" data-root="${escapeAttr(key)}">Stage</button>
            <button type="button" class="git-action-btn" data-action="commit" data-root="${escapeAttr(key)}">Commit</button>
          </div>`
        : "";
      return (
        `<div class="git-repo-block${s.dirty ? " is-dirty" : ""}" data-root="${escapeAttr(key)}">` +
        `<button type="button" class="git-repo-toggle" data-root="${escapeAttr(key)}">` +
        `${toggle} <span class="git-repo-name">${escapeHtml(displayName)}</span>` +
        `<span class="git-repo-meta">${escapeHtml(branch)} (${escapeHtml(badge)})</span></button>` +
        `<div class="git-repo-body${open ? "" : " hidden"}">` +
        err +
        (files ? `<ul class="git-file-list">${files}${more}</ul>` : '<div class="git-changes-empty">无改动</div>') +
        actions +
        `</div></div>`
      );
    });

    let logHtml = "";
    if (lastScopeCommits.length) {
      const rows = lastScopeCommits
        .slice(0, 5)
        .map(
          (c) =>
            `<li class="git-log-row" title="${escapeAttr(c.root || "")}">` +
            `<span class="git-log-msg">${escapeHtml((c.message || "").slice(0, 48))}</span>` +
            `<span class="git-log-at">${escapeHtml((c.at || "").slice(0, 16))}</span></li>`
        )
        .join("");
      logHtml = `<div class="git-scope-log"><div class="git-scope-log-title">最近提交</div><ul>${rows}</ul></div>`;
    }

    gitPanel.innerHTML = blocks.join("") + logHtml;
  }

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function escapeAttr(s) {
    return escapeHtml(s).replace(/'/g, "&#39;");
  }

  function shortPath(p) {
    const parts = String(p || "").split("/");
    if (parts.length <= 2) return p;
    return "…/" + parts.slice(-2).join("/");
  }

  function suggestAndCommit(root) {
    post({ type: "gitSuggestMessage", root }).then((data) => {
      const suggested = (data && data.message) || "chore: update";
      const msg = window.prompt("Commit message（不会 push）:", suggested);
      if (msg === null) return;
      post({ type: "gitCommit", root, message: msg }).then((res) => {
        if (res && !res.ok && window.__merisComposerHint) {
          window.__merisComposerHint(res.error || "commit failed", "error");
        }
        fetchSummary();
      });
    });
  }

  gitPanel.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-action]");
    if (btn) {
      const root = btn.getAttribute("data-root");
      const action = btn.getAttribute("data-action");
      if (!root) return;
      if (action === "stage") {
        post({ type: "gitStage", root }).then(() => fetchSummary());
      } else if (action === "commit") {
        suggestAndCommit(root);
      }
      return;
    }
    const toggle = e.target.closest(".git-repo-toggle");
    if (toggle) {
      const root = toggle.getAttribute("data-root");
      if (!root) return;
      if (expandedRepos.has(root)) expandedRepos.delete(root);
      else expandedRepos.add(root);
      render();
    }
  });

  if (gitRefreshBtn) gitRefreshBtn.addEventListener("click", () => fetchSummary());
  if (gitShipAllBtn) {
    gitShipAllBtn.addEventListener("click", () => {
      if (!window.confirm("对范围内全部脏仓库执行 Stage + Commit？（不会 push）")) return;
      post({ type: "gitShipScope" }).then((res) => {
        if (res && res.results && window.__merisComposerHint) {
          const ok = res.results.filter((r) => r.ok).length;
          const fail = res.results.filter((r) => !r.ok).length;
          window.__merisComposerHint(`已提交 ${ok} 个仓库` + (fail ? `，${fail} 个失败` : ""), ok ? "ok" : "error");
        }
        fetchSummary();
      });
    });
  }

  window.addEventListener("message", (event) => {
    const msg = event.data;
    if (!msg || !msg.type) return;
    if (msg._gitReqId && pendingCmd.has(msg._gitReqId)) {
      const resolve = pendingCmd.get(msg._gitReqId);
      pendingCmd.delete(msg._gitReqId);
      resolve(msg);
    }
    if (msg.type === "gitSummary") applyPayload(msg);
    if (msg.type === "workspaceInfo") fetchSummary();
    if (msg.type === "status" && (msg.status === "done" || msg.status === "error")) fetchSummary();
  });

  window.__merisGitRefresh = fetchSummary;
  setTimeout(fetchSummary, 400);
})();
