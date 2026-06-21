const vscode = require("vscode");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn, execFileSync } = require("child_process");

/** @type {vscode.ExtensionContext | null} */
let extensionContext = null;

/** @type {vscode.WebviewPanel | null} */
let agentPanel = null;

/** @type {Set<vscode.Webview>} */
const agentWebviews = new Set();

/** @type {import("child_process").ChildProcess | null} */
let activeProcess = null;
let activeCliProcess = null;

/** meris argv allowlist for UI one-shot run (sync with meris/ui/cli_runner.py) */
const RUNNABLE_CLI = {
  doctor: ["doctor", "--no-probe"],
  dogfood: ["dogfood"],
  "harness-check": ["harness", "check"],
  "ratchet-status": ["ratchet", "status"],
  "ratchet-scan": ["ratchet", "scan"],
  "native-status": ["native", "status"],
  "mcp-list": ["mcp", "list"],
  "release-check": ["release", "check"],
  "session-list": ["session", "list"],
  "models-route": ["models", "route", "preview routing smoke"],
  benchmark: ["benchmark", "run", "--local-only"],
};

/** @type {{ path: string | null; position: number; pollTimer: ReturnType<typeof setInterval> | null; fsWatcher: fs.FSWatcher | null }} */
const tailState = { path: null, position: 0, pollTimer: null, fsWatcher: null };

/** @type {string | null} */
let activeWorkspacePath = null;

const EXTRA_ROOTS_KEY = "meris.extraWorkspaceRoots";
const TASK_SCOPE_KEY = "meris.taskScope";

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
  try {
    if (fs.existsSync(path.join(p, "SKILL.md")) && !isMerisRepo(p)) return true;
  } catch {
    /* ignore */
  }
  return false;
}

function getExtraRoots() {
  if (!extensionContext) return [];
  const raw = extensionContext.globalState.get(EXTRA_ROOTS_KEY);
  return Array.isArray(raw) ? raw.map(String) : [];
}

function getTaskScopePaths() {
  if (!extensionContext) return [];
  const raw = extensionContext.globalState.get(TASK_SCOPE_KEY);
  return Array.isArray(raw) ? raw.map(String) : [];
}

/** @param {string[]} paths */
async function saveTaskScopePaths(paths) {
  if (!extensionContext) return;
  await extensionContext.globalState.update(TASK_SCOPE_KEY, paths);
}

/** @param {string} cwd */
function getAvailableProjectPaths(cwd) {
  const active = path.resolve(cwd);
  const seeds = [];
  const seen = new Set();
  for (const candidate of [...getExtraRoots(), active]) {
    if (!candidate || isLikelySkillRoot(candidate)) continue;
    try {
      const resolved = path.resolve(candidate);
      const key = process.platform === "win32" ? resolved.toLowerCase() : resolved;
      if (!fs.existsSync(resolved) || !fs.statSync(resolved).isDirectory()) continue;
      if (seen.has(key)) continue;
      seen.add(key);
      seeds.push(resolved);
    } catch {
      /* ignore */
    }
  }
  return seeds;
}

/** @param {string[]} selected @param {string[]} available @param {string} cwd */
function normalizeTaskScope(selected, available, cwd) {
  const active = path.resolve(cwd);
  const norm = (p) => {
    const r = path.resolve(p);
    return process.platform === "win32" ? r.toLowerCase() : r;
  };
  const avail = new Set(available.map(norm));
  if (!selected.length) return [active];
  const kept = selected.map((p) => path.resolve(p)).filter((p) => avail.has(norm(p)));
  return kept.length ? kept : [active];
}

/** @param {string} cwd */
function buildTaskScopePayload(cwd) {
  const active = path.resolve(cwd);
  const available = getAvailableProjectPaths(cwd);
  const selected = normalizeTaskScope(getTaskScopePaths(), available, active);
  const norm = (p) => (process.platform === "win32" ? path.resolve(p).toLowerCase() : path.resolve(p));
  const selectedSet = new Set(selected.map(norm));
  const items = available.map((p) => ({
    name: path.basename(p),
    path: p,
    selected: selectedSet.has(norm(p)),
    isCwd: norm(p) === norm(active),
  }));
  return {
    taskScope: items,
    taskScopeSelected: [...selectedSet].sort(),
  };
}

/** @param {string} p */
async function addExtraRoot(p) {
  if (!extensionContext) return false;
  const normalized = path.resolve(p);
  if (isLikelySkillRoot(normalized)) {
    vscode.window.showWarningMessage(
      "Meris: Skill 目录不能作为项目根 — 请在设置 → 技能 管理"
    );
    return false;
  }
  const roots = getExtraRoots().map((r) => path.resolve(r));
  if (roots.includes(normalized)) return false;
  await extensionContext.globalState.update(EXTRA_ROOTS_KEY, [...new Set([...getExtraRoots(), normalized])]);
  return true;
}

/** @param {string} p */
async function removeExtraRoot(p) {
  if (!extensionContext) return;
  const key = path.resolve(p);
  const roots = getExtraRoots().filter((r) => path.resolve(r) !== key);
  await extensionContext.globalState.update(EXTRA_ROOTS_KEY, roots);
  const cwd = getWorkspaceCwd();
  if (cwd) {
    const pruned = normalizeTaskScope(
      getTaskScopePaths().filter((r) => path.resolve(r) !== key),
      getAvailableProjectPaths(cwd),
      cwd
    );
    await saveTaskScopePaths(pruned);
  }
}

function pickPlanExecuteRoot(activeCwd) {
  const folders = discoverWorkspaceFolders();
  const merisRoots = folders.filter((f) => f.isMeris);
  if (!merisRoots.length) return activeCwd;
  const active = path.resolve(activeCwd);
  for (const m of merisRoots) {
    const mp = path.resolve(m.path);
    for (const f of folders) {
      const fp = path.resolve(f.path);
      if (fp !== mp && mp.startsWith(fp + path.sep)) {
        return mp;
      }
    }
  }
  const hit = merisRoots.find((m) => path.resolve(m.path) === active);
  if (hit) return active;
  return path.resolve(merisRoots[0].path);
}

function loadPlanPayload(cwd) {
  const planFile = path.join(cwd, ".meris", "plan", "tasks.md");
  if (!fs.existsSync(planFile)) return null;
  try {
    const text = fs.readFileSync(planFile, "utf8");
    const items = [];
    for (const line of text.split("\n")) {
      const m = line.trim().match(/^-\s+\[( |x|X)\]\s+(.+)$/);
      if (m) items.push({ done: m[1].toLowerCase() === "x", text: m[2].trim() });
    }
    return { path: ".meris/plan/tasks.md", items };
  } catch {
    return null;
  }
}

/** Harness doc index for settings overlay (Phase J5). */
const HARNESS_DOC_CATALOG = [
  { id: "readme", file: "README.md", title: "Harness 索引", blurb: "docs/harness 入口与快速参考" },
  { id: "architecture", file: "architecture.md", title: "仓库架构", blurb: "包布局、CLI、import 约定" },
  { id: "routing", file: "routing.md", title: "模型路由", blurb: "意图 → mode → model 决策表" },
  { id: "events", file: "events.md", title: "事件流 JSONL", blurb: "Agent Window / --event-stream 协议" },
  { id: "testing", file: "testing.md", title: "测试与 DoD", blurb: "pytest · harness check · benchmark" },
  { id: "plan-format", file: "plan-format.md", title: "Plan 格式", blurb: "`- [ ]` checkbox 任务清单" },
  { id: "sandbox", file: "sandbox.md", title: "Bash 沙箱", blurb: "warn / strict · bubblewrap" },
];

function harnessDocsDir() {
  return path.join(__dirname, "..", "..", "docs", "harness");
}

function listDocsOnDisk() {
  const base = harnessDocsDir();
  return HARNESS_DOC_CATALOG.map((entry) => ({
    id: entry.id,
    title: entry.title,
    blurb: entry.blurb,
    path: `docs/harness/${entry.file}`,
    available: fs.existsSync(path.join(base, entry.file)) ? "true" : "false",
  }));
}

/** @param {string} docId */
function readDocOnDisk(docId) {
  const entry = HARNESS_DOC_CATALOG.find((d) => d.id === docId);
  if (!entry) return null;
  const fp = path.join(harnessDocsDir(), entry.file);
  if (!fs.existsSync(fp)) return null;
  return {
    id: entry.id,
    title: entry.title,
    path: `docs/harness/${entry.file}`,
    content: fs.readFileSync(fp, "utf8").slice(0, 24000),
  };
}

function listCliCommandsOnDisk() {
  try {
    const fp = path.join(__dirname, "media", "cli-commands.json");
    const data = JSON.parse(fs.readFileSync(fp, "utf8"));
    const groups = data.groups || [];
    for (const group of groups) {
      for (const cmd of group.commands || []) {
        if (cmd && cmd.id && RUNNABLE_CLI[cmd.id]) cmd.runnable = true;
      }
    }
    return { groups };
  } catch {
    return { groups: [] };
  }
}

function discoverWorkspaceFolders() {
  const seen = new Set();
  const merisRoots = [];
  const other = [];

  /** @param {string} base @param {string} [label] */
  function addRoot(base, label) {
    if (!base || seen.has(base) || !fs.existsSync(base)) return;
    if (isLikelySkillRoot(base)) return;
    seen.add(base);
    const entry = { name: label || path.basename(base), path: base, isMeris: isMerisRepo(base) };
    (entry.isMeris ? merisRoots : other).push(entry);
    const sub = path.join(base, "meris");
    if (fs.existsSync(sub) && !seen.has(sub) && isMerisRepo(sub)) {
      seen.add(sub);
      merisRoots.push({ name: "meris", path: sub, isMeris: true });
    }
  }

  for (const f of vscode.workspace.workspaceFolders || []) {
    addRoot(f.uri.fsPath, f.name);
  }
  for (const base of getExtraRoots()) {
    addRoot(base);
  }
  if (activeWorkspacePath) {
    addRoot(activeWorkspacePath);
  }
  return [...merisRoots, ...other];
}

function isMerisRepo(p) {
  try {
    if (fs.existsSync(path.join(p, ".meris"))) return true;
    if (fs.existsSync(path.join(p, "pyproject.toml")) && fs.existsSync(path.join(p, "meris"))) return true;
  } catch {
    /* ignore */
  }
  return false;
}

function getDefaultWorkspacePath() {
  const folders = discoverWorkspaceFolders();
  const meris = folders.find((f) => f.isMeris);
  return meris?.path || folders[0]?.path;
}

function getWorkspaceFolders() {
  return discoverWorkspaceFolders().map(({ name, path: p }) => ({ name, path: p }));
}

function getWorkspaceCwd() {
  if (activeWorkspacePath && fs.existsSync(activeWorkspacePath)) {
    return activeWorkspacePath;
  }
  return getDefaultWorkspacePath() ?? activeWorkspacePath ?? undefined;
}

/** @param {string} p */
function setActiveWorkspace(p) {
  activeWorkspacePath = p;
  if (extensionContext) {
    void extensionContext.globalState.update("meris.activeWorkspace", p);
    void addExtraRoot(p);
  }
  postWorkspaceInfo("switch");
  refreshAgentSidebarData(p);
}

function postWorkspaceInfo(action = "update", extra = {}) {
  const cwd = getWorkspaceCwd();
  const scope = cwd ? buildTaskScopePayload(cwd) : { taskScope: [], taskScopeSelected: [] };
  postToAgentWebviews({
    type: "workspaceInfo",
    cwd: cwd || "",
    cwdLabel: cwd ? path.basename(cwd) : "",
    folders: getWorkspaceFolders(),
    persistedRoots: getExtraRoots().map((p) => ({ name: path.basename(p), path: p })),
    workspaceAction: action,
    ...scope,
    ...extra,
  });
}

/** @param {string} cwd @param {string} relDir */
function listDirEntries(cwd, relDir) {
  const full = path.join(cwd, relDir || "");
  const skip = new Set([".git", "node_modules", "__pycache__", ".venv", "dist", "build"]);
  let names;
  try {
    names = fs.readdirSync(full, { withFileTypes: true });
  } catch {
    return [];
  }
  return names
    .filter((e) => !(!relDir && skip.has(e.name)))
    .map((e) => ({
      name: e.name,
      path: path.join(relDir || "", e.name).replace(/\\/g, "/"),
      isDir: e.isDirectory(),
    }))
    .sort((a, b) => {
      if (a.isDir !== b.isDir) return a.isDir ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
}

/** Bundled skill templates (meris repo dev layout). */
const BUNDLED_SKILLS_DIR = path.join(__dirname, "..", "..", "templates", "skills");
const GLOBAL_SKILLS_DIR = path.join(os.homedir(), ".meris", "skills");

/** @param {string} text */
function parseSkillFrontmatter(text) {
  if (!text.startsWith("---")) return { meta: {}, body: text };
  const end = text.indexOf("\n---\n", 4);
  if (end < 0) return { meta: {}, body: text };
  const block = text.slice(4, end);
  const meta = {};
  for (const line of block.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const idx = trimmed.indexOf(":");
    if (idx < 0) continue;
    const key = trimmed.slice(0, idx).trim().toLowerCase();
    let val = trimmed.slice(idx + 1).trim();
    val = val.replace(/^['"]|['"]$/g, "");
    meta[key] = val;
  }
  return { meta, body: text.slice(end + 5).replace(/^\n/, "") };
}

/** @param {string} body @param {string} fallback */
function skillTitleFromBody(body, fallback) {
  for (const line of body.split("\n")) {
    const t = line.trim();
    if (t.startsWith("#")) return t.replace(/^#+\s*/, "") || fallback;
  }
  return fallback;
}

/** @param {string} body */
function skillFirstParagraph(body) {
  const lines = [];
  for (const line of body.split("\n")) {
    const t = line.trim();
    if (!t) {
      if (lines.length) break;
      continue;
    }
    if (t.startsWith("#") || t.startsWith("```")) {
      if (lines.length) break;
      continue;
    }
    lines.push(t);
  }
  let text = lines.join(" ").trim();
  if (text.length > 160) text = text.slice(0, 159).trimEnd() + "…";
  return text || "按需通过 load_skill 加载";
}

/** @param {string} name @param {Record<string, string>} meta */
function skillGuessIcon(name, meta) {
  if (meta.icon) return meta.icon;
  const low = name.toLowerCase();
  if (low.includes("plan")) return "📋";
  if (low.includes("harness")) return "⚙️";
  if (low.includes("security")) return "🔒";
  if (low.includes("debug")) return "🐛";
  if (low.includes("review")) return "🔍";
  return "📋";
}

/** @param {string} text @param {string} name */
function skillMetadata(text, name) {
  const { meta, body } = parseSkillFrontmatter(text);
  return {
    title: meta.name || meta.title || skillTitleFromBody(body, name),
    description: meta.description || skillFirstParagraph(body),
    icon: skillGuessIcon(name, meta),
  };
}

/** @param {string} cwd */
function loadSkillPrefsOnDisk(cwd) {
  const p = path.join(cwd, ".meris", "ui", "skill-prefs.json");
  if (!fs.existsSync(p)) return { disabled: [], importSourcePath: "" };
  try {
    const data = JSON.parse(fs.readFileSync(p, "utf8"));
    return {
      disabled: Array.isArray(data.disabled) ? data.disabled.map(String) : [],
      importSourcePath: String(data.importSourcePath || "").trim(),
    };
  } catch {
    return { disabled: [], importSourcePath: "" };
  }
}

/** @param {string} cwd @param {object} prefs */
function saveSkillPrefsOnDisk(cwd, prefs) {
  const dir = path.join(cwd, ".meris", "ui");
  fs.mkdirSync(dir, { recursive: true });
  const out = {
    disabled: [...new Set((prefs.disabled || []).map(String))].sort(),
    importSourcePath: String(prefs.importSourcePath || "").trim(),
  };
  fs.writeFileSync(path.join(dir, "skill-prefs.json"), JSON.stringify(out, null, 2) + "\n", "utf8");
}

/** @param {string} cwd @param {string} importPath */
function setSkillImportSourceOnDisk(cwd, importPath) {
  const prefs = loadSkillPrefsOnDisk(cwd);
  prefs.importSourcePath = importPath ? path.resolve(importPath) : "";
  saveSkillPrefsOnDisk(cwd, prefs);
}

/** @param {string} cwd */
function defaultSkillImportDirs(cwd) {
  return [path.join(cwd, ".agents", "skills"), path.join(cwd, ".cursor", "skills")];
}

/** @param {string} cwd @param {string | undefined} explicit */
function resolveSkillImportSourceOnDisk(cwd, explicit) {
  if (explicit && String(explicit).trim()) {
    const p = path.resolve(String(explicit).trim());
    return fs.existsSync(p) && fs.statSync(p).isDirectory() ? p : null;
  }
  const prefs = loadSkillPrefsOnDisk(cwd);
  if (prefs.importSourcePath && fs.existsSync(prefs.importSourcePath)) {
    return prefs.importSourcePath;
  }
  for (const d of defaultSkillImportDirs(cwd)) {
    if (fs.existsSync(d) && fs.statSync(d).isDirectory()) return d;
  }
  return null;
}

/** @param {string} cwd @param {string} srcDir */
function importSkillsFromDirOnDisk(cwd, srcDir) {
  if (!fs.existsSync(srcDir) || !fs.statSync(srcDir).isDirectory()) return 0;
  const dst = path.join(cwd, ".meris", "skills");
  fs.mkdirSync(dst, { recursive: true });
  let count = 0;
  for (const entry of fs.readdirSync(srcDir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    if (entry.isDirectory()) {
      const skillMd = path.join(srcDir, entry.name, "SKILL.md");
      if (!fs.existsSync(skillMd)) continue;
      const safe = entry.name.replace(/[^a-zA-Z0-9_-]/g, "");
      if (!safe) continue;
      let text = fs.readFileSync(skillMd, "utf8");
      if (!text.startsWith("---")) text = `---\nsource: import\n---\n\n${text}`;
      else if (!text.split("---", 3)[1].includes("source:")) {
        text = text.replace("---\n", "---\nsource: import\n", 1);
      }
      fs.writeFileSync(path.join(dst, `${safe}.md`), text, "utf8");
      count += 1;
    } else if (entry.isFile() && entry.name.endsWith(".md")) {
      const safe = entry.name.replace(/\.md$/, "").replace(/[^a-zA-Z0-9_-]/g, "");
      if (!safe) continue;
      fs.copyFileSync(path.join(srcDir, entry.name), path.join(dst, `${safe}.md`));
      count += 1;
    }
  }
  return count;
}

/** @param {string} cwd @param {string} name */
function isSkillEnabledOnDisk(cwd, name) {
  const prefs = loadSkillPrefsOnDisk(cwd);
  return !(prefs.disabled || []).includes(name);
}

/** @param {string} cwd */
function listBundledSkillNames() {
  if (!fs.existsSync(BUNDLED_SKILLS_DIR)) return [];
  return fs
    .readdirSync(BUNDLED_SKILLS_DIR)
    .filter((f) => f.endsWith(".md"))
    .map((f) => f.replace(/\.md$/, ""))
    .sort();
}

/** @param {string} cwd */
function listSkillsOnDisk(cwd) {
  const workspaceDir = path.join(cwd, ".meris", "skills");
  const projectNames = new Set();
  const items = [];
  if (fs.existsSync(workspaceDir)) {
    for (const f of fs.readdirSync(workspaceDir).filter((x) => x.endsWith(".md")).sort()) {
      const name = f.replace(/\.md$/, "");
      projectNames.add(name);
      const text = fs.readFileSync(path.join(workspaceDir, f), "utf8");
      const meta = skillMetadata(text, name);
      items.push({
        name,
        title: meta.title,
        description: meta.description,
        icon: meta.icon,
        path: `.meris/skills/${f}`,
        source: "installed",
        enabled: isSkillEnabledOnDisk(cwd, name),
        readonly: false,
        installed: true,
      });
    }
  }
  if (fs.existsSync(GLOBAL_SKILLS_DIR)) {
    for (const f of fs.readdirSync(GLOBAL_SKILLS_DIR).filter((x) => x.endsWith(".md")).sort()) {
      const name = f.replace(/\.md$/, "");
      if (projectNames.has(name)) continue;
      const text = fs.readFileSync(path.join(GLOBAL_SKILLS_DIR, f), "utf8");
      const meta = skillMetadata(text, name);
      items.push({
        name,
        title: meta.title,
        description: meta.description,
        icon: meta.icon,
        path: `~/.meris/skills/${f}`,
        source: "global",
        enabled: isSkillEnabledOnDisk(cwd, name),
        readonly: false,
        installed: true,
      });
    }
  }
  for (const name of listBundledSkillNames()) {
    if (projectNames.has(name)) continue;
    const fp = path.join(BUNDLED_SKILLS_DIR, `${name}.md`);
    const text = fs.readFileSync(fp, "utf8");
    const meta = skillMetadata(text, name);
    items.push({
      name,
      title: meta.title,
      description: meta.description,
      icon: meta.icon,
      path: `templates/skills/${name}.md`,
      source: "builtin",
      enabled: true,
      readonly: true,
      installed: false,
    });
  }
  return items;
}

/** @param {string} cwd @param {string} name */
function readSkillOnDisk(cwd, name) {
  const safe = name.replace(/[^a-zA-Z0-9_-]/g, "");
  if (!safe) return null;
  const projectPath = path.join(cwd, ".meris", "skills", `${safe}.md`);
  if (fs.existsSync(projectPath)) {
    return {
      path: `.meris/skills/${safe}.md`,
      content: fs.readFileSync(projectPath, "utf8").slice(0, 12000),
      skill: safe,
    };
  }
  const globalPath = path.join(GLOBAL_SKILLS_DIR, `${safe}.md`);
  if (fs.existsSync(globalPath)) {
    return {
      path: `~/.meris/skills/${safe}.md`,
      content: fs.readFileSync(globalPath, "utf8").slice(0, 12000),
      skill: safe,
    };
  }
  const bundledPath = path.join(BUNDLED_SKILLS_DIR, `${safe}.md`);
  if (fs.existsSync(bundledPath)) {
    return {
      path: `templates/skills/${safe}.md`,
      content: fs.readFileSync(bundledPath, "utf8").slice(0, 12000),
      skill: safe,
    };
  }
  return null;
}

/** @param {string} cwd */
function listRulesOnDisk(cwd) {
  const dir = path.join(cwd, ".meris", "rules");
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir)
    .filter((f) => f.endsWith(".md"))
    .map((f) => ({ name: f.replace(/\.md$/, ""), path: `.meris/rules/${f}` }));
}

/** @param {string} cwd @param {string} name */
function readRuleOnDisk(cwd, name) {
  const p = path.join(cwd, ".meris", "rules", `${name}.md`);
  if (!fs.existsSync(p)) return null;
  return {
    name,
    path: `.meris/rules/${name}.md`,
    content: fs.readFileSync(p, "utf8").slice(0, 12000),
  };
}

/** @param {string} cwd @param {string} name @param {string} content */
function saveRuleOnDisk(cwd, name, content) {
  const safe = name.replace(/[^a-zA-Z0-9_-]/g, "");
  if (!safe) throw new Error("invalid rule name");
  const dir = path.join(cwd, ".meris", "rules");
  fs.mkdirSync(dir, { recursive: true });
  const body = (content || "").trim() || `# ${safe}\n`;
  fs.writeFileSync(path.join(dir, `${safe}.md`), body + (body.endsWith("\n") ? "" : "\n"), "utf8");
  return safe;
}

/** @param {string} cwd */
function listModelsFromSettings(cwd) {
  const p = path.join(cwd, ".meris", "settings.json");
  if (!fs.existsSync(p)) return { defaultModel: "auto", byMode: {}, rules: [] };
  try {
    const data = JSON.parse(fs.readFileSync(p, "utf8"));
    const models = data.models || {};
    const byMode = models.byMode || {};
    const out = {};
    Object.keys(byMode).forEach((k) => {
      out[k] = (byMode[k] && byMode[k].model) || "";
    });
    return {
      defaultModel: (models.default && models.default.model) || "auto",
      byMode: out,
      rules: Array.isArray(models.rules)
        ? models.rules.map((r) => ({
            name: r.name || "",
            model: r.model || "",
            profile: r.profile || "",
          }))
        : [],
    };
  } catch {
    return { defaultModel: "auto", byMode: {}, rules: [] };
  }
}

/** @param {string} cwd */
/** @param {string} cwd */
function migrateMcpSettingsToUiOnDisk(cwd) {
  const raw = readSettingsMcpRaw(cwd);
  if (!raw || !Object.keys(raw).length) return false;
  writeUiMcpServers(cwd, mcpDictToItems(raw));
  return true;
}

/** @param {string} cwd @param {string} filePath */
function importMcpFromPathOnDisk(cwd, filePath) {
  const p = path.resolve(filePath);
  if (!fs.existsSync(p)) return false;
  try {
    const data = JSON.parse(fs.readFileSync(p, "utf8"));
    const servers = data.mcpServers || data;
    if (!servers || typeof servers !== "object") return false;
    writeUiMcpServers(cwd, mcpDictToItems(servers));
    return true;
  } catch {
    return false;
  }
}

/** @param {string} cwd @param {string} name @param {string} content */
function saveGlobalSkillOnDisk(name, content) {
  const safe = name.replace(/[^a-zA-Z0-9_-]/g, "");
  if (!safe) throw new Error("invalid skill name");
  fs.mkdirSync(GLOBAL_SKILLS_DIR, { recursive: true });
  const body = (content || "").trim() || `# ${safe}\n`;
  fs.writeFileSync(
    path.join(GLOBAL_SKILLS_DIR, `${safe}.md`),
    body + (body.endsWith("\n") ? "" : "\n"),
    "utf8"
  );
  return safe;
}

/** @param {string} name */
function installBundledToGlobalOnDisk(name) {
  const safe = name.replace(/[^a-zA-Z0-9_-]/g, "");
  if (!safe) throw new Error("invalid skill name");
  const src = path.join(BUNDLED_SKILLS_DIR, `${safe}.md`);
  if (!fs.existsSync(src)) return null;
  fs.mkdirSync(GLOBAL_SKILLS_DIR, { recursive: true });
  const dst = path.join(GLOBAL_SKILLS_DIR, `${safe}.md`);
  if (!fs.existsSync(dst)) fs.copyFileSync(src, dst);
  return safe;
}

/** @param {string} cwd @param {string} dirPath */
function importRulesFromDirOnDisk(cwd, dirPath) {
  const src = path.resolve(dirPath);
  if (!fs.existsSync(src)) return 0;
  const dst = path.join(cwd, ".meris", "rules");
  fs.mkdirSync(dst, { recursive: true });
  let count = 0;
  for (const f of fs.readdirSync(src)) {
    if (!f.endsWith(".md") && !f.endsWith(".mdc")) continue;
    const name = f.replace(/\.(md|mdc)$/, "").replace(/[^a-zA-Z0-9_-]/g, "");
    if (!name) continue;
    let text = fs.readFileSync(path.join(src, f), "utf8");
    if (f.endsWith(".mdc") && !text.startsWith("---")) {
      text = `---\nsource: import\n---\n\n${text}`;
    }
    fs.writeFileSync(path.join(dst, `${name}.md`), text, "utf8");
    count += 1;
  }
  return count;
}

function importCursorRulesOnDisk(cwd) {
  return importRulesFromDirOnDisk(cwd, path.join(cwd, ".cursor", "rules"));
}

/** @param {object} servers */
function mcpDictToItems(servers) {
  return Object.keys(servers || {})
    .sort()
    .map((name) => {
      const cfg = servers[name] || {};
      const transport = cfg.url ? "sse" : "stdio";
      return {
        name,
        enabled: cfg.enabled !== false && !cfg.disabled,
        transport: cfg.transport || transport,
        command: cfg.command || "",
        args: Array.isArray(cfg.args) ? cfg.args : [],
        url: cfg.url || "",
        env: cfg.env && typeof cfg.env === "object" ? cfg.env : {},
      };
    });
}

/** @param {string} cwd */
function readSettingsMcpRaw(cwd) {
  try {
    const py =
      "import json,sys;from pathlib import Path;from meris.harness.settings import load_settings;print(json.dumps(load_settings(Path(sys.argv[1])).get('mcpServers')or{}))";
    const out = execFileSync("python", ["-c", py, cwd], { encoding: "utf8", timeout: 15000, cwd });
    const raw = JSON.parse(out.trim());
    return raw && typeof raw === "object" ? raw : {};
  } catch {
    return {};
  }
}

/** @param {string} cwd */
function readUiMcpRaw(cwd) {
  const p = path.join(cwd, ".meris", "ui", "mcp-servers.json");
  if (!fs.existsSync(p)) return null;
  try {
    const data = JSON.parse(fs.readFileSync(p, "utf8"));
    const servers = data.mcpServers || data;
    return servers && typeof servers === "object" ? servers : {};
  } catch {
    return {};
  }
}

/** @param {string} cwd */
function listMcpServersOnDisk(cwd) {
  const ui = readUiMcpRaw(cwd);
  if (ui !== null) return mcpDictToItems(ui);
  return mcpDictToItems(readSettingsMcpRaw(cwd));
}

/** @param {string} cwd */
function readUiMcpServers(cwd) {
  return listMcpServersOnDisk(cwd);
}

/** @param {string} cwd @param {object[]} items */
function writeUiMcpServers(cwd, items) {
  const servers = {};
  for (const item of items || []) {
    if (!item.name) continue;
    servers[item.name] = {
      transport: item.transport || "stdio",
      command: item.command || "",
      args: Array.isArray(item.args) ? item.args : [],
      url: item.url || "",
      env: item.env || {},
      enabled: item.enabled !== false,
    };
  }
  const dir = path.join(cwd, ".meris", "ui");
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(
    path.join(dir, "mcp-servers.json"),
    JSON.stringify({ mcpServers: servers }, null, 2),
    "utf8"
  );
}

/** @param {string} cwd @param {string} name @param {string} content */
function saveSkillOnDisk(cwd, name, content) {
  const safe = name.replace(/[^a-zA-Z0-9_-]/g, "");
  if (!safe) throw new Error("invalid skill name");
  const dir = path.join(cwd, ".meris", "skills");
  fs.mkdirSync(dir, { recursive: true });
  const body = (content || "").trim() || `# ${safe}\n`;
  fs.writeFileSync(path.join(dir, `${safe}.md`), body + (body.endsWith("\n") ? "" : "\n"), "utf8");
  return safe;
}

/** @param {string} cwd @param {string} name @param {boolean} enabled */
function setSkillEnabledOnDisk(cwd, name, enabled) {
  const safe = name.replace(/[^a-zA-Z0-9_-]/g, "");
  if (!safe) throw new Error("invalid skill name");
  const prefs = loadSkillPrefsOnDisk(cwd);
  const disabled = new Set(prefs.disabled || []);
  if (enabled) disabled.delete(safe);
  else disabled.add(safe);
  prefs.disabled = [...disabled].sort();
  saveSkillPrefsOnDisk(cwd, prefs);
}

/** @param {string} cwd @param {string | undefined} explicit */
function runSkillImportOnDisk(cwd, explicit) {
  const src = resolveSkillImportSourceOnDisk(cwd, explicit);
  if (!src) return { count: 0, src: null };
  return { count: importSkillsFromDirOnDisk(cwd, src), src };
}

/** @param {string} cwd @param {string} name */
function installBundledSkillOnDisk(cwd, name) {
  const safe = name.replace(/[^a-zA-Z0-9_-]/g, "");
  if (!safe) throw new Error("invalid skill name");
  const src = path.join(BUNDLED_SKILLS_DIR, `${safe}.md`);
  if (!fs.existsSync(src)) return null;
  const dstDir = path.join(cwd, ".meris", "skills");
  fs.mkdirSync(dstDir, { recursive: true });
  const dst = path.join(dstDir, `${safe}.md`);
  if (!fs.existsSync(dst)) fs.copyFileSync(src, dst);
  return safe;
}

/** @param {string} cwd */
/** @param {string} cwd */
function mcpConfigSourceOnDisk(cwd) {
  const p = path.join(cwd, ".meris", "ui", "mcp-servers.json");
  return fs.existsSync(p) ? "ui" : "settings";
}

function fetchMcpInfo(cwd) {
  return new Promise((resolve) => {
    const servers = readUiMcpServers(cwd);
    const proc = spawn("meris", ["mcp", "list"], { cwd, shell: true, env: { ...process.env } });
    let out = "";
    proc.stdout?.on("data", (c) => {
      out += c.toString();
    });
    proc.on("close", () => {
      const tools = out
        .split("\n")
        .map((l) => l.trim())
        .filter((l) => l && !l.startsWith("(") && !l.startsWith("Install"));
      const connByName = {};
      for (const line of out.split("\n")) {
        const ok = line.match(/^MCP connected:\s*(\S+)/);
        if (ok) {
          connByName[ok[1]] = { connection: "ok", connectionDetail: line.trim() };
          continue;
        }
        const fail = line.match(/^MCP failed\s+(\S+):\s*(.+)$/);
        if (fail) {
          connByName[fail[1]] = { connection: "fail", connectionDetail: fail[2].trim() };
        }
      }
      const enriched = servers.map((srv) => ({
        ...srv,
        ...(connByName[srv.name] || {
          connection: srv.enabled === false ? "disabled" : "unknown",
          connectionDetail: "",
        }),
      }));
      resolve({
        servers: enriched,
        configured: servers.length > 0,
        tools: tools.slice(0, 24),
        source: mcpConfigSourceOnDisk(cwd),
      });
    });
  });
}

function postToAgentWebviews(msg) {
  for (const webview of agentWebviews) {
    webview.postMessage(msg);
  }
}

/** @param {string} mode ask | plan | run */
async function runMerisTask(mode, extraArgs = []) {
  const folder = vscode.workspace.workspaceFolders?.[0];
  if (!folder) {
    vscode.window.showErrorMessage("Meris: open a workspace folder first.");
    return;
  }
  const task = await vscode.window.showInputBox({
    prompt: `Meris ${mode} — describe your task`,
    placeHolder: "e.g. fix failing test in tests/test_auth.py",
  });
  if (!task) {
    return;
  }
  const escaped = task.replace(/"/g, '\\"');
  const args = [mode, `"${escaped}"`, ...extraArgs].join(" ");
  const term = vscode.window.createTerminal({
    name: `Meris ${mode}`,
    cwd: folder.uri.fsPath,
  });
  term.show();
  term.sendText(`meris ${args}`);
}

function runMerisSimple(command, label) {
  const cwd = getWorkspaceCwd() ?? ".";
  const term = vscode.window.createTerminal({ name: label, cwd });
  term.show();
  term.sendText(`meris ${command}`);
}

function runMerisWithEvents() {
  const cwd = getWorkspaceCwd();
  if (!cwd) {
    vscode.window.showErrorMessage("Meris: open a workspace folder first.");
    return;
  }
  const eventsPath = path.join(cwd, ".meris", "events", "vscode-run.jsonl");
  runMerisTask("run", ["--event-stream", `"${eventsPath.replace(/\\/g, "/")}"`]);
}

async function runMerisReview() {
  const folder = vscode.workspace.workspaceFolders?.[0];
  if (!folder) {
    vscode.window.showErrorMessage("Meris: open a workspace folder first.");
    return;
  }
  const staged = await vscode.window.showQuickPick(
    [
      { label: "Staged diff", value: "--staged" },
      { label: "Working tree diff", value: "" },
    ],
    { placeHolder: "Review which diff?" }
  );
  if (!staged) {
    return;
  }
  const term = vscode.window.createTerminal({
    name: "Meris Review",
    cwd: folder.uri.fsPath,
  });
  term.show();
  term.sendText(`meris review ${staged.value}`.trim());
}

async function runMerisExec() {
  const folder = vscode.workspace.workspaceFolders?.[0];
  if (!folder) {
    vscode.window.showErrorMessage("Meris: open a workspace folder first.");
    return;
  }
  const task = await vscode.window.showInputBox({
    prompt: "Meris exec — one-shot task (JSON output)",
    placeHolder: "e.g. list files in src/",
  });
  if (!task) {
    return;
  }
  const escaped = task.replace(/"/g, '\\"');
  const term = vscode.window.createTerminal({
    name: "Meris Exec",
    cwd: folder.uri.fsPath,
  });
  term.show();
  term.sendText(`meris exec "${escaped}" --json`);
}

function getNonce() {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let out = "";
  for (let i = 0; i < 32; i++) {
    out += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return out;
}

/** @param {vscode.Webview} webview @param {vscode.Uri} extensionUri */
function getAgentWebviewContent(webview, extensionUri) {
  const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, "media", "agent.js"));
  const phaseIUri = webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, "media", "phase-i.js"));
  const harnessUiUri = webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, "media", "harness-ui.js"));
  const filePreviewUri = webview.asWebviewUri(
    vscode.Uri.joinPath(extensionUri, "media", "file-preview.js")
  );
  const gitUiUri = webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, "media", "git-ui.js"));
  const settingsUiUri = webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, "media", "settings-ui.js"));
  const composerMediaUri = webview.asWebviewUri(
    vscode.Uri.joinPath(extensionUri, "media", "composer-media.js")
  );
  const uiHelpUri = webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, "media", "ui-help.js"));
  const styleUri = webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, "media", "agent.css"));
  const nonce = getNonce();
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource}; script-src 'nonce-${nonce}';">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link href="${styleUri}" rel="stylesheet">
  <title>Meris Agent</title>
</head>
<body>
<div id="header">
    <span class="brand">Meris Agent</span>
    <div class="workspace-bar">
      <label for="workspace-select" class="workspace-bar-label">主项目</label>
      <select id="workspace-select" class="workspace-select" title="主项目 (cwd)：命令、测试、Harness 默认根"></select>
    </div>
    <div class="header-actions">
      <button id="settings-btn" type="button" title="设置" aria-label="设置">
        <span class="settings-btn-icon">⚙</span>
        <span class="settings-btn-label">设置</span>
      </button>
      <span id="status" class="status idle">Ready</span>
    </div>
  </div>
  <div id="model-bar" class="hidden">
    <span id="model-label"></span>
    <span id="route-label"></span>
  </div>
  <div id="error-banner" class="hidden"></div>

  <div id="workspace-manage-popover" class="workspace-manage-popover hidden" aria-hidden="true">
    <div class="workspace-manage-title">项目列表 <span id="workspace-root-count" class="workspace-root-count"></span></div>
    <ul id="workspace-roots-list" class="workspace-roots-list"></ul>
    <p class="workspace-manage-hint">已注册项目。★ 为主项目 (cwd)。× 移除。Skill 在设置 → 技能。</p>
  </div>

  <div id="folder-modal" class="folder-modal hidden" aria-hidden="true">
    <div class="folder-modal-card">
      <h3 class="folder-modal-title">添加项目</h3>
      <p id="folder-modal-hint" class="folder-modal-hint">选择<strong>项目文件夹</strong>（含代码或 Harness），不是 Skill 目录。「添加」加入项目列表；「切换」设为当前 cwd。</p>
      <div class="folder-quick-links">
        <button type="button" id="folder-goto-roots-btn" class="folder-quick-btn">此电脑</button>
        <button type="button" id="folder-goto-home-btn" class="folder-quick-btn">用户文件夹</button>
        <button type="button" id="folder-goto-cwd-btn" class="folder-quick-btn">启动目录</button>
      </div>
      <div class="folder-browse-bar">
        <span id="folder-browse-path" class="folder-browse-path">—</span>
        <button type="button" id="folder-select-current-btn" class="folder-select-current-btn">切换到此目录</button>
        <button type="button" id="folder-add-root-btn" class="folder-add-root-btn secondary-btn">添加根目录</button>
      </div>
      <ul id="folder-browse-list" class="folder-browse-list"></ul>
      <div class="folder-modal-actions">
        <button type="button" id="folder-modal-cancel-btn">取消</button>
      </div>
    </div>
  </div>

  <div id="settings-overlay" class="hidden" aria-hidden="true">
    <div class="settings-shell">
      <aside class="settings-nav">
        <div class="settings-nav-top">
          <span class="settings-nav-title">设置</span>
          <button type="button" id="settings-close" class="settings-close-btn" title="关闭">×</button>
        </div>
        <input type="search" id="settings-search" placeholder="搜索设置…" autocomplete="off">
        <nav class="settings-nav-list" id="settings-nav-list">
          <button type="button" class="settings-nav-item active" data-settings="general">通用</button>
          <button type="button" class="settings-nav-item" data-settings="agent">智能体</button>
          <button type="button" class="settings-nav-item" data-settings="models">模型</button>
          <button type="button" class="settings-nav-item" data-settings="mcp">MCP</button>
          <button type="button" class="settings-nav-item" data-settings="skills">技能</button>
          <button type="button" class="settings-nav-item" data-settings="rules">规则</button>
          <button type="button" class="settings-nav-item" data-settings="docs">文档</button>
          <button type="button" class="settings-nav-item" data-settings="commands">CLI 命令</button>
          <button type="button" class="settings-nav-item" data-settings="import">导入配置</button>
        </nav>
      </aside>
      <main class="settings-main">
        <p id="settings-project-banner" class="settings-harness-banner settings-hint hidden">
          当前项目根（Harness）：<code id="settings-project-root">—</code>
        </p>
        <section id="settings-general" class="settings-page active" data-settings="general">
          <h2 class="settings-page-title">通用</h2>
          <div class="settings-field">
            <label class="settings-field-label">主题</label>
            <div id="theme-presets" class="theme-presets">
              <button type="button" class="theme-chip active" data-theme="vibe">默认</button>
              <button type="button" class="theme-chip" data-theme="dark">石墨</button>
              <button type="button" class="theme-chip" data-theme="midnight">午夜</button>
              <button type="button" class="theme-chip" data-theme="light">浅色</button>
            </div>
          </div>
          <div class="settings-field">
            <label class="settings-field-label">背景</label>
            <div class="settings-inline">
              <input type="color" id="bg-color-picker" value="#0b0d11" title="自定义背景色">
              <span id="bg-color-text">#0b0d11</span>
              <button type="button" id="settings-reset">恢复默认</button>
            </div>
          </div>
        </section>
        <section id="settings-agent" class="settings-page hidden" data-settings="agent">
          <h2 class="settings-page-title">智能体</h2>
          <div class="settings-field">
            <label class="settings-field-label" for="default-mode-select">默认模式</label>
            <select id="default-mode-select">
              <option value="run">run</option>
              <option value="ask">ask</option>
              <option value="plan">plan</option>
            </select>
          </div>
          <div class="settings-field">
            <label class="settings-field-label"><input type="checkbox" id="default-approve-check"> 默认开启 approve</label>
          </div>
          <p class="settings-hint">影响新会话的默认选项；当前 composer 仍可临时修改。</p>
        </section>
        <section id="settings-models" class="settings-page hidden" data-settings="models">
          <h2 class="settings-page-title">模型</h2>
          <div id="models-summary" class="settings-summary"></div>
          <p class="settings-hint">路由配置来自 <code>.meris/settings.json</code> 的 <code>models</code> 段。Composer 的 Auto 由路由自动选择。</p>
        </section>
        <section id="settings-mcp" class="settings-page hidden" data-settings="mcp">
          <h2 class="settings-page-title">MCP</h2>
          <p id="mcp-source-hint" class="settings-hint">外挂工具服务。保存后写入 <code>.meris/ui/mcp-servers.json</code> 并覆盖 <code>settings.yaml</code> 中的 <code>mcpServers</code>。绿点=已连接，红点=失败，灰点=已禁用。</p>
          <ul id="mcp-list" class="settings-list"></ul>
          <textarea id="mcp-json-input" class="settings-code" rows="12" spellcheck="false" placeholder='{"mcpServers": {}}'></textarea>
          <div class="settings-actions">
            <button type="button" id="mcp-migrate-btn" class="secondary-btn hidden">从 settings.yaml 迁移到 UI</button>
            <button type="button" id="mcp-save-btn">保存 MCP</button>
          </div>
          <div id="mcp-json-error" class="settings-error hidden"></div>
        </section>
        <section id="settings-skills" class="settings-page hidden" data-settings="skills">
          <h2 class="settings-page-title">技能</h2>
          <div class="skill-import-card settings-card">
            <div class="skill-import-text">
              <strong>从本地目录导入技能</strong>
              <p class="settings-hint">导入到<strong>当前项目</strong> <code>.meris/skills/</code>（与下方「导入配置」页的 MCP/规则无关）。全局技能放 <code>~/.meris/skills/</code>。</p>
            </div>
            <div class="skill-import-path-row">
              <code id="skill-import-path" class="skill-import-path">未选择目录</code>
            </div>
            <div class="settings-inline skill-import-actions">
              <button type="button" id="pick-skill-import-dir-btn">选择目录</button>
              <button type="button" id="import-skills-btn">导入</button>
              <button type="button" id="import-cursor-skills-btn" class="link-btn">从 .cursor/skills</button>
              <span id="skills-import-status" class="settings-hint"></span>
            </div>
            <div id="skill-import-browse" class="skill-import-browse hidden">
              <div class="folder-browse-bar">
                <span id="skill-browse-path" class="folder-browse-path">—</span>
                <button type="button" id="skill-browse-refresh-btn" class="icon-btn" title="刷新">↻</button>
              </div>
              <ul id="skill-browse-list" class="folder-browse-list skill-browse-list"></ul>
              <div class="settings-inline">
                <button type="button" id="skill-browse-use-btn">使用此目录</button>
                <button type="button" id="skill-browse-close-btn" class="link-btn">收起</button>
              </div>
            </div>
          </div>
          <div class="skills-section-head">
            <div>
              <h3 class="skills-subtitle">技能</h3>
              <p class="settings-hint">当前项目 <code>.meris/skills/</code> + 全局 <code>~/.meris/skills/</code>；Agent 通过 <code>load_skill</code> 按需加载。</p>
            </div>
            <div class="skills-toolbar">
              <button type="button" id="skills-refresh-btn" class="icon-btn" title="刷新">↻</button>
              <button type="button" id="skill-global-create-btn" class="secondary-btn">+ 全局</button>
              <button type="button" id="skill-create-btn" class="primary-btn">+ 项目</button>
            </div>
          </div>
          <div id="settings-skill-cards" class="skill-cards"></div>
          <div id="skill-editor-panel" class="skill-editor-panel hidden">
            <div class="skill-editor-head">
              <h4 id="skill-editor-title">编辑技能</h4>
              <button type="button" id="skill-editor-close" class="icon-btn" title="关闭">×</button>
            </div>
            <div class="settings-inline skill-quick-add">
              <input type="text" id="skill-name-input" placeholder="新建 skill 名称（kebab-case）">
            </div>
            <textarea id="skill-content-input" class="settings-code" rows="12" spellcheck="false" placeholder="# Skill Markdown&#10;---&#10;name: my-skill&#10;description: 简要说明何时使用&#10;---"></textarea>
            <div class="settings-actions">
              <button type="button" id="skill-save-btn">保存 Skill</button>
            </div>
          </div>
          <div class="skills-commands-block">
            <div class="skills-section-head">
              <div>
                <h3 class="skills-subtitle">命令</h3>
                <p class="settings-hint">常用 CLI 速查；▶ 在终端运行，完整列表见「CLI 命令」页。</p>
              </div>
              <button type="button" id="skills-open-commands-btn" class="link-btn">查看全部 →</button>
            </div>
            <div id="skills-commands-preview" class="skills-commands-preview"></div>
          </div>
        </section>
        <section id="settings-rules" class="settings-page hidden" data-settings="rules">
          <h2 class="settings-page-title">规则</h2>
          <p class="settings-hint">编辑 <code>.meris/rules/*.md</code>，注入策略由 frontmatter <code>inject</code> 控制。</p>
          <ul id="settings-rule-list" class="settings-list selectable"></ul>
          <textarea id="rule-content-input" class="settings-code" rows="12" spellcheck="false" placeholder="# Rule Markdown"></textarea>
          <div class="settings-actions">
            <button type="button" id="rule-save-btn">保存规则</button>
          </div>
        </section>
        <section id="settings-docs" class="settings-page hidden" data-settings="docs">
          <h2 class="settings-page-title">Harness 文档</h2>
          <p class="settings-hint">Meris Harness 索引（<code>docs/harness/</code>）。点击条目预览。</p>
          <ul id="docs-index-list" class="settings-list selectable"></ul>
          <textarea id="docs-preview" class="settings-code" rows="16" readonly spellcheck="false" placeholder="选择左侧文档…"></textarea>
        </section>
        <section id="settings-commands" class="settings-page hidden" data-settings="commands">
          <h2 class="settings-page-title">CLI 命令</h2>
          <p class="settings-hint">终端 <code>meris</code> 子命令速查；带 <span class="cmd-ui-badge">UI</span> 的可在此窗口完成。<strong>▶</strong> 一键运行，输出在底部 Terminal。点击命令行复制。</p>
          <input id="commands-search" type="search" class="settings-search-inline" placeholder="搜索命令…" autocomplete="off">
          <div id="commands-groups" class="commands-groups"></div>
        </section>
        <section id="settings-import" class="settings-page hidden" data-settings="import">
          <h2 class="settings-page-title">导入配置</h2>
          <p class="settings-hint">仅迁移 <strong>MCP</strong> 与 <strong>规则</strong> 到当前项目 Harness。技能请用「技能」页的目录导入。</p>
          <div class="settings-import-cards">
            <button type="button" class="settings-import-card" id="import-cursor-mcp-btn">
              <strong>导入 MCP（.cursor）</strong>
              <span><code>.cursor/mcp.json</code> → <code>.meris/ui/mcp-servers.json</code></span>
            </button>
            <button type="button" class="settings-import-card" id="import-cursor-rules-btn">
              <strong>导入规则（.cursor）</strong>
              <span><code>.cursor/rules/</code> → <code>.meris/rules/</code></span>
            </button>
          </div>
          <div class="settings-import-custom settings-card">
            <h3 class="skills-subtitle">自定义路径</h3>
            <div class="settings-import-path-row">
              <label for="import-mcp-path">MCP 文件</label>
              <input type="text" id="import-mcp-path" class="settings-path-input" placeholder="任意 mcp.json 路径">
              <button type="button" id="pick-import-mcp-btn">选择文件</button>
              <button type="button" id="import-mcp-path-btn">导入 MCP</button>
            </div>
            <div class="settings-import-path-row">
              <label for="import-rules-path">规则目录</label>
              <input type="text" id="import-rules-path" class="settings-path-input" placeholder="任意 rules 目录">
              <button type="button" id="pick-import-rules-btn">选择目录</button>
              <button type="button" id="import-rules-path-btn">导入规则</button>
            </div>
          </div>
          <div id="import-status" class="settings-hint"></div>
        </section>
      </main>
    </div>
  </div>

  <div id="layout">
    <aside id="left-panel">
      <section class="sidebar-block sidebar-block-projects">
        <div class="panel-header workspace-panel-header project-panel-header">
          <span class="workspace-panel-title">项目</span>
          <div class="workspace-panel-actions">
            <button type="button" id="add-workspace-root-btn" class="workspace-panel-btn" title="添加项目">+</button>
            <button type="button" id="manage-workspace-roots-btn" class="workspace-panel-btn" title="管理项目列表">⋯</button>
            <button type="button" id="task-scope-current-btn" class="task-scope-btn" title="仅勾选主项目">仅当前</button>
            <button type="button" id="task-scope-all-btn" class="task-scope-btn" title="勾选全部项目">全选</button>
          </div>
        </div>
        <div id="project-list" class="project-list"></div>
      </section>
      <section class="sidebar-block sidebar-block-files">
        <div class="panel-header workspace-panel-header file-panel-header">
          <span class="workspace-panel-title" id="file-panel-title">文件</span>
          <div class="workspace-panel-actions">
            <button type="button" id="workspace-collapse-all-btn" class="workspace-panel-btn" title="折叠全部">⊟</button>
          </div>
        </div>
        <div id="file-tree" class="file-tree workspace-tree"></div>
      </section>
      <section class="sidebar-block sidebar-block-changes">
        <div class="panel-header workspace-panel-header git-panel-header">
          <span class="workspace-panel-title">改动</span>
          <div class="workspace-panel-actions">
            <button type="button" id="git-ship-all-btn" class="git-ship-all-btn" title="暂存并提交范围内全部脏仓库（不 push）">提交全部</button>
            <button type="button" id="git-refresh-btn" class="workspace-panel-btn" title="刷新 git 状态">↻</button>
          </div>
        </div>
        <div id="git-changes-panel" class="git-changes-panel"></div>
      </section>
    </aside>
    <div id="main">
      <div id="view-tabs" class="view-tabs-bar">
        <div class="view-tabs-inner">
          <button type="button" class="view-tab active" data-view="chat">Chat</button>
          <button type="button" class="view-tab" data-view="plan">Plan</button>
          <button type="button" class="view-tab" data-view="parallel">Parallel</button>
          <button type="button" class="view-tab" data-view="preview">Preview</button>
        </div>
        <button type="button" id="view-tabs-help" class="ui-help-btn" title="视图标签说明" aria-label="视图标签说明">?</button>
      </div>
      <div id="chat-view" class="view-panel active">
        <div id="timeline"></div>
      </div>
      <div id="plan-view" class="view-panel hidden">
        <div id="plan-panel">
          <div class="plan-empty">运行 <code>plan</code> 模式后，任务清单会显示在这里。</div>
          <p id="plan-source" class="plan-source hidden"></p>
          <ul id="plan-list"></ul>
          <div class="plan-actions">
            <button type="button" id="plan-run-btn" class="hidden">Run plan →</button>
            <button type="button" id="plan-clear-btn" class="hidden" title="删除 .meris/plan/tasks.md">清除计划</button>
          </div>
        </div>
      </div>
      <div id="parallel-view" class="view-panel hidden">
        <textarea id="parallel-input" placeholder="每行一个任务…" rows="4"></textarea>
        <div class="parallel-options">
          <label class="parallel-isolate-label"><input type="checkbox" id="parallel-isolate-check"> 隔离 worktree（--isolate，仅 run 模式）</label>
          <select id="parallel-mode-select" title="parallel 模式">
            <option value="ask">ask</option>
            <option value="run">run</option>
          </select>
        </div>
        <button type="button" id="parallel-run-btn">Run parallel</button>
        <div id="parallel-summary" class="parallel-summary hidden"></div>
        <div id="parallel-lanes" class="parallel-lanes hidden"></div>
      </div>
      <div id="preview-view" class="view-panel hidden">
        <div class="preview-toolbar">
          <div id="preview-tabs" class="preview-tabs" role="tablist" aria-label="已打开文件"></div>
          <div class="preview-toolbar-actions">
            <button type="button" id="preview-refresh" class="preview-toolbar-btn" title="刷新当前文件">↻</button>
            <button type="button" id="preview-close-all" class="preview-toolbar-btn" title="关闭全部标签">×</button>
          </div>
        </div>
        <iframe id="preview-frame" title="Live preview" sandbox="allow-scripts allow-same-origin"></iframe>
      </div>
      <details id="terminal-panel" class="terminal-panel">
        <summary>Terminal</summary>
        <pre id="terminal-output"></pre>
      </details>
      <div id="composer">
        <div id="approval-bar" class="hidden">
          <div class="approval-title">Approve tool call?</div>
          <div id="approval-tool" class="approval-tool"></div>
          <pre id="approval-args" class="approval-args"></pre>
          <div class="approval-actions">
            <button id="approve-yes" type="button">Approve</button>
            <button id="approve-no" type="button">Deny</button>
          </div>
        </div>
        <div id="task-scope-chips" class="task-scope-chips"></div>
        <div id="context-chips"></div>
        <div id="composer-hint" class="composer-hint hidden" aria-live="polite"></div>
        <div id="git-ship-bar" class="git-ship-bar hidden" aria-live="polite">
          <button type="button" id="git-ship-stats-btn" class="git-ship-stats-btn" title="点击查看左侧「改动」">
            <span class="git-ship-stats-label">Changes</span>
            <span id="git-stat-add" class="git-stat-add">+0</span>
            <span id="git-stat-del" class="git-stat-del">−0</span>
          </button>
          <div class="git-ship-commit-wrap">
            <button type="button" id="git-quick-commit-btn" class="git-quick-commit-btn">Commit</button>
            <button type="button" id="git-quick-menu-btn" class="git-quick-menu-btn" title="更多 Git 操作" aria-haspopup="true">▾</button>
            <div id="git-quick-menu" class="git-quick-menu hidden" role="menu">
              <button type="button" class="git-quick-menu-item" data-git-action="stage-scope" role="menuitem">Stage 全部（scope）</button>
              <button type="button" class="git-quick-menu-item" data-git-action="commit-scope" role="menuitem">Commit 全部（scope）…</button>
              <button type="button" class="git-quick-menu-item git-quick-menu-push" data-git-action="push-main" role="menuitem">Push 主项目…</button>
            </div>
          </div>
          <div class="git-ship-meta">
            <span id="git-quick-branch" class="git-quick-branch" title="主项目分支">⎇ —</span>
            <span id="git-quick-cwd" class="git-quick-cwd" title="主项目">Local</span>
          </div>
        </div>
        <div class="composer-card">
          <div class="composer-topbar">
            <div class="composer-agent-pill" id="composer-agent-pill">
              <span class="composer-agent-icon" aria-hidden="true">◇</span>
              <span id="composer-mode-label">@Agent</span>
            </div>
            <div class="composer-topbar-actions">
              <button type="button" id="composer-help-btn" class="composer-topbar-btn" title="CLI 命令速查">?</button>
              <button type="button" id="composer-tools-btn" class="composer-topbar-btn" title="工具与 MCP">⛭</button>
              <button type="button" id="composer-settings-btn" class="composer-topbar-btn" title="设置">⚙</button>
            </div>
          </div>
          <div class="composer-editor-wrap">
            <textarea id="task-input" placeholder="您正在与 Agent 聊天…" rows="3"></textarea>
            <div class="composer-toolbar">
              <div class="composer-toolbar-left">
                <button id="at-btn" type="button" class="composer-icon-btn" title="Skill @">@</button>
                <button id="hash-btn" type="button" class="composer-icon-btn" title="文件 #">#</button>
                <button id="image-btn" type="button" class="composer-icon-btn" title="截图/粘贴图片" aria-label="图片">🖼</button>
                <input id="image-input" type="file" accept="image/*" class="hidden" tabindex="-1" aria-hidden="true">
                <div id="at-dropdown" class="ctx-picker hidden">
                  <div class="ctx-picker-title">Skills</div>
                  <ul id="at-skill-list"></ul>
                </div>
                <div id="hash-dropdown" class="ctx-picker hidden">
                  <input id="hash-search" type="search" placeholder="搜索文件…" autocomplete="off">
                  <button type="button" id="hash-selection" class="at-action">+ 当前选区</button>
                  <ul id="hash-file-list"></ul>
                </div>
              </div>
              <div class="composer-toolbar-right">
                <button type="button" id="mode-help-btn" class="ui-help-btn ui-help-btn-inline" title="运行模式说明" aria-label="运行模式说明">?</button>
                <select id="mode-select" class="composer-mode-select" title="运行模式">
                  <option value="run" selected>Agent</option>
                  <option value="ask">Ask</option>
                  <option value="plan">Plan</option>
                </select>
                <select id="model-select" class="composer-model-select" title="模型">
                  <option value="auto" selected>Auto</option>
                </select>
                <label class="composer-approve-toggle" title="每步确认 (approve)">
                  <input type="checkbox" id="approve-check" class="hidden">
                  <span class="composer-approve-icon" aria-hidden="true">✦</span>
                </label>
                <button id="mic-btn" type="button" class="composer-icon-btn" title="语音输入" aria-label="语音">🎤</button>
                <button id="submit-btn" type="button" class="composer-send-btn" title="发送 (Ctrl+Enter)" aria-label="发送">
                  <span class="composer-send-icon" aria-hidden="true">↑</span>
                </button>
                <button id="stop-btn" type="button" class="composer-stop-btn hidden" disabled title="停止" aria-label="停止">■</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <aside id="right-panel">
      <div class="right-tabs">
        <button type="button" class="right-tab active" data-right="history">历史</button>
        <button type="button" class="right-tab" data-right="ratchet">Ratchet</button>
      </div>
      <div id="history-panel">
        <div class="panel-header">
          <span>历史记录</span>
          <button id="refresh-sessions" type="button" title="Refresh">↻</button>
        </div>
        <input id="session-search" type="search" placeholder="搜索任务…" autocomplete="off">
        <div id="session-list"></div>
      </div>
      <div id="ratchet-panel" class="hidden">
        <div class="panel-header">
          <span>Ratchet</span>
          <div class="panel-actions">
            <button id="ratchet-scan" type="button" title="Scan">⊕</button>
            <button id="refresh-ratchet" type="button" title="Refresh">↻</button>
          </div>
        </div>
        <ul id="ratchet-list"></ul>
      </div>
    </aside>
  </div>

  <div id="ui-help-popover" class="ui-help-popover hidden" aria-hidden="true">
    <div class="ui-help-card" role="dialog" aria-modal="true" aria-labelledby="ui-help-title">
      <div class="ui-help-header">
        <span id="ui-help-title" class="ui-help-title">说明</span>
        <button type="button" id="ui-help-close" class="ui-help-close" aria-label="关闭">×</button>
      </div>
      <div id="ui-help-body" class="ui-help-body"></div>
    </div>
  </div>

  <script nonce="${nonce}" src="${scriptUri}"></script>
  <script nonce="${nonce}" src="${phaseIUri}"></script>
  <script nonce="${nonce}" src="${harnessUiUri}"></script>
  <script nonce="${nonce}" src="${filePreviewUri}"></script>
  <script nonce="${nonce}" src="${gitUiUri}"></script>
  <script nonce="${nonce}" src="${settingsUiUri}"></script>
  <script nonce="${nonce}" src="${composerMediaUri}"></script>
  <script nonce="${nonce}" src="${uiHelpUri}"></script>
</html>`;
}

function stopTail() {
  if (tailState.pollTimer) {
    clearInterval(tailState.pollTimer);
    tailState.pollTimer = null;
  }
  if (tailState.fsWatcher) {
    tailState.fsWatcher.close();
    tailState.fsWatcher = null;
  }
}

/** @param {string} eventsPath @returns {object[]} */
function readNewJsonlEvents(eventsPath) {
  if (!fs.existsSync(eventsPath)) {
    return [];
  }
  const stat = fs.statSync(eventsPath);
  if (stat.size < tailState.position) {
    tailState.position = 0;
  }
  if (stat.size === tailState.position) {
    return [];
  }
  const fd = fs.openSync(eventsPath, "r");
  const buffer = Buffer.alloc(stat.size - tailState.position);
  fs.readSync(fd, buffer, 0, buffer.length, tailState.position);
  fs.closeSync(fd);
  tailState.position = stat.size;

  const events = [];
  for (const line of buffer.toString("utf8").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) {
      continue;
    }
    try {
      events.push(JSON.parse(trimmed));
    } catch {
      // skip malformed line
    }
  }
  return events;
}

/** @param {string} eventsPath @param {(ev: object) => void} onEvent */
function startJsonlTail(eventsPath, onEvent) {
  stopTail();
  tailState.path = eventsPath;
  tailState.position = 0;

  const dir = path.dirname(eventsPath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  if (fs.existsSync(eventsPath)) {
    tailState.position = fs.statSync(eventsPath).size;
  }

  const pump = () => {
    for (const ev of readNewJsonlEvents(eventsPath)) {
      onEvent(ev);
    }
  };

  tailState.pollTimer = setInterval(pump, 250);
  try {
    tailState.fsWatcher = fs.watch(eventsPath, pump);
  } catch {
    // file may not exist until meris writes
  }
}

function killActiveProcess() {
  if (activeProcess && !activeProcess.killed) {
    activeProcess.kill("SIGTERM");
    activeProcess = null;
  }
}

/** @param {string} cwd @returns {object[]} */
function loadSessions(cwd) {
  const dir = path.join(cwd, ".meris", "sessions");
  if (!fs.existsSync(dir)) {
    return [];
  }
  const sessions = [];
  for (const name of fs.readdirSync(dir)) {
    if (!name.endsWith(".json")) {
      continue;
    }
    const fp = path.join(dir, name);
    try {
      const data = JSON.parse(fs.readFileSync(fp, "utf8"));
      const stat = fs.statSync(fp);
      sessions.push({
        id: data.id || name.replace(/\.json$/, ""),
        task: data.task || "",
        mode: data.mode || "run",
        status: data.status || "unknown",
        turn: data.turn || 0,
        updatedAt: data.updated_at || "",
        mtime: stat.mtimeMs,
      });
    } catch {
      // skip corrupt session file
    }
  }
  return sessions.sort((a, b) => b.mtime - a.mtime).slice(0, 20);
}

/** @param {string} cwd */
function loadRatchetData(cwd) {
  const proposalsDir = path.join(cwd, ".meris", "ratchet", "proposals");
  const proposals = [];
  if (fs.existsSync(proposalsDir)) {
    for (const name of fs.readdirSync(proposalsDir)) {
      if (!name.endsWith(".json")) {
        continue;
      }
      const fp = path.join(proposalsDir, name);
      try {
        const data = JSON.parse(fs.readFileSync(fp, "utf8"));
        if (data.status !== "pending") {
          continue;
        }
        const stat = fs.statSync(fp);
        proposals.push({
          id: data.id,
          lesson: data.lesson || "",
          summary: data.summary || "",
          target: data.target?.path || "",
          mtime: stat.mtimeMs,
        });
      } catch {
        // skip
      }
    }
  }
  proposals.sort((a, b) => b.mtime - a.mtime);

  let insightsPending = 0;
  const insightsPath = path.join(cwd, ".meris", "ratchet", "insights", "pending.jsonl");
  if (fs.existsSync(insightsPath)) {
    insightsPending = fs
      .readFileSync(insightsPath, "utf8")
      .split("\n")
      .filter((line) => line.trim()).length;
  }

  return { proposals: proposals.slice(0, 8), insightsPending };
}

/** @param {string} cwd */
function refreshAgentSidebarData(cwd) {
  postToAgentWebviews({ type: "sessions", sessions: loadSessions(cwd) });
  postToAgentWebviews({ type: "ratchet", ...loadRatchetData(cwd) });
  const plan = loadPlanPayload(cwd);
  if (plan) postToAgentWebviews({ type: "plan", ...plan });
}

/** @param {string} cwd */
function runRatchetScan(cwd) {
  return new Promise((resolve) => {
    const proc = spawn("meris", ["ratchet", "scan"], {
      cwd,
      shell: true,
      env: { ...process.env },
    });
    let stderr = "";
    proc.stderr?.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    proc.on("close", (code) => {
      resolve({ ok: code === 0, stderr: stderr.slice(-300) });
    });
  });
}

/** @param {string} cwd @param {string} subcmd apply | reject @param {string} proposalId */
function runRatchetCli(cwd, subcmd, proposalId) {
  return new Promise((resolve) => {
    const proc = spawn("meris", ["ratchet", subcmd, proposalId], {
      cwd,
      shell: true,
      env: { ...process.env },
    });
    let stderr = "";
    proc.stderr?.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    proc.on("close", (code) => {
      resolve({ ok: code === 0, stderr: stderr.slice(-300) });
    });
  });
}

/** @param {string} cwd @param {(ev: object) => void} postEvent @returns {string[]} */
function buildMerisSpawnArgs(cwd, postEvent, opts) {
  const eventsPath = path.join(cwd, ".meris", "events", "agent-window.jsonl");
  const eventsArg = eventsPath.replace(/\\/g, "/");
  const approvalArg = path.join(cwd, ".meris", "events", "approval").replace(/\\/g, "/");

  const eventDir = path.dirname(eventsPath);
  if (!fs.existsSync(eventDir)) {
    fs.mkdirSync(eventDir, { recursive: true });
  }
  fs.writeFileSync(eventsPath, "", "utf8");

  startJsonlTail(eventsPath, postEvent);

  const approvalFlags = [];
  if (opts.approve) {
    approvalFlags.push("--approve", "--approval-channel", approvalArg);
  }

  if (opts.resume && opts.sessionId) {
    return ["session", "resume", opts.sessionId, "--event-stream", eventsArg, ...approvalFlags];
  }

  const runArgs = [opts.mode, opts.task, "--event-stream", eventsArg];
  if (opts.fromPlan) runArgs.push("--from-plan");
  if (opts.ratchetAfter) runArgs.push("--ratchet");
  return [...runArgs, ...approvalFlags];
}

/** @param {string} cwd @param {string} requestId @param {boolean} approved */
function writeApprovalResponse(cwd, requestId, approved) {
  const dir = path.join(cwd, ".meris", "events", "approval");
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  const resPath = path.join(dir, "approval-response.json");
  fs.writeFileSync(resPath, JSON.stringify({ request_id: requestId, approved }), "utf8");
}

/** Run meris Python helpers and parse JSON stdout. */
function merisPythonJson(code, argvPayload) {
  const script =
    "import json,sys\nfrom pathlib import Path\n" +
    code +
    "\n";
  try {
    const out = execFileSync("python", ["-c", script, argvPayload || "[]"], {
      encoding: "utf8",
      maxBuffer: 1024 * 1024,
      env: { ...process.env },
    });
    return JSON.parse(String(out).trim() || "{}");
  } catch (err) {
    const out = err.stdout ? String(err.stdout).trim() : "";
    if (out) {
      try {
        return JSON.parse(out);
      } catch {
        /* fall through */
      }
    }
    return { ok: false, error: String(err.message || err) };
  }
}

/** @param {string[]} roots */
function buildGitSummaryPayload(roots) {
  return merisPythonJson(
    "roots=[Path(p) for p in json.loads(sys.argv[1])]\n" +
      "from meris.harness.git_summary import git_summary_for_roots\n" +
      "from meris.harness.ui_config import load_scope_commits\n" +
      'print(json.dumps({"summaries": git_summary_for_roots(roots), "scopeCommits": load_scope_commits()}))',
    JSON.stringify(roots || [])
  );
}

/** @param {string} root */
function gitStageRoot(root) {
  return merisPythonJson(
    "root=Path(json.loads(sys.argv[1]))\n" +
      "from meris.harness.git_summary import git_stage_all\n" +
      "print(json.dumps(git_stage_all(root)))",
    JSON.stringify(root)
  );
}

/** @param {string} root @param {string} message @param {string} cwd */
function gitCommitRoot(root, message, cwd) {
  return merisPythonJson(
    "payload=json.loads(sys.argv[1])\n" +
      "root=Path(payload['root'])\n" +
      "from meris.harness.git_summary import git_commit\n" +
      "from meris.harness.ui_config import record_scope_commit\n" +
      "result=git_commit(root, payload['message'])\n" +
      "if result.get('ok'):\n" +
      "  record_scope_commit(root=root, message=str(result.get('commitMessage') or ''), cwd=Path(payload['cwd']))\n" +
      "print(json.dumps(result))",
    JSON.stringify({ root, message, cwd })
  );
}

/** @param {string} root */
function gitSuggestRoot(root) {
  return merisPythonJson(
    "root=Path(json.loads(sys.argv[1]))\n" +
      "from meris.harness.git_summary import suggest_commit_message\n" +
      'print(json.dumps({"ok": True, "message": suggest_commit_message(root)}))',
    JSON.stringify(root)
  );
}

/** @param {string} cwd */
function gitShipScope(cwd) {
  return merisPythonJson(
    "cwd=Path(json.loads(sys.argv[1]))\n" +
      "from meris.harness.git_summary import git_commit, git_stage_all, git_summary, suggest_commit_message\n" +
      "from meris.harness.ui_config import available_project_paths, load_task_scope_paths, normalize_task_scope, record_scope_commit\n" +
      "roots=normalize_task_scope(load_task_scope_paths(), available=available_project_paths(cwd), cwd=cwd)\n" +
      "results=[]\n" +
      "for root in roots:\n" +
      "  summary=git_summary(root)\n" +
      "  if not summary.get('isRepo') or not summary.get('dirty'): continue\n" +
      "  staged=git_stage_all(root)\n" +
      "  if not staged.get('ok'):\n" +
      "    results.append({'path': str(root), 'ok': False, 'error': staged.get('error')}); continue\n" +
      "  msg=suggest_commit_message(root)\n" +
      "  committed=git_commit(root, msg)\n" +
      "  if committed.get('ok'):\n" +
      "    record_scope_commit(root=root, message=str(committed.get('commitMessage') or msg), cwd=cwd)\n" +
      "  results.append({'path': str(root), 'ok': bool(committed.get('ok')), 'message': committed.get('commitMessage') or msg, 'error': committed.get('error')})\n" +
      'print(json.dumps({"ok": True, "results": results}))',
    JSON.stringify(cwd)
  );
}

/** @param {string} root */
function gitPushRoot(root) {
  return merisPythonJson(
    "root=Path(json.loads(sys.argv[1]))\n" +
      "from meris.harness.git_summary import git_push\n" +
      "print(json.dumps(git_push(root)))",
    JSON.stringify(root)
  );
}

/** @param {string[]} roots @param {string} [reqId] */
function postGitSummary(roots, reqId) {
  const payload = buildGitSummaryPayload(roots);
  postToAgentWebviews({ type: "gitSummary", _gitReqId: reqId, ...payload });
  return payload;
}

function getGitDiff(cwd, relPath) {
  if (!relPath) {
    return "";
  }
  try {
    return execFileSync("git", ["diff", "--unified=3", "--", relPath], {
      cwd,
      encoding: "utf8",
      maxBuffer: 80000,
    }).trim();
  } catch (err) {
    const out = err.stdout ? String(err.stdout).trim() : "";
    return out;
  }
}

/** @param {string} cwd @param {object} ev */
function enrichEvent(cwd, ev) {
  if (!ev || ev.kind !== "file_change" || ev.diff_preview) {
    return ev;
  }
  const gitDiff = getGitDiff(cwd, ev.path);
  if (!gitDiff) {
    return ev;
  }
  return { ...ev, diff_preview: gitDiff };
}

/** @param {string} cwd @param {object} opts */
function spawnMerisRun(cwd, opts) {
  const eventsPath = path.join(cwd, ".meris", "events", "agent-window.jsonl");
  const postEvent = (ev) => {
    postToAgentWebviews({ type: "event", event: enrichEvent(cwd, ev) });
  };

  const args = buildMerisSpawnArgs(cwd, postEvent, opts);

  killActiveProcess();
  activeProcess = spawn("meris", args, {
    cwd,
    shell: true,
    env: { ...process.env },
  });

  let stderr = "";
  let stdout = "";
  const emitTerm = (stream, chunk) => {
    postToAgentWebviews({ type: "terminal", stream, chunk: chunk.toString() });
  };
  activeProcess.stdout?.on("data", (chunk) => {
    stdout += chunk.toString();
    emitTerm("stdout", chunk);
  });
  activeProcess.stderr?.on("data", (chunk) => {
    stderr += chunk.toString();
    emitTerm("stderr", chunk);
  });

  activeProcess.on("close", async (code) => {
    for (const ev of readNewJsonlEvents(eventsPath)) {
      postEvent(ev);
    }
    activeProcess = null;
    const status = code === 0 ? "done" : "error";
    const sessions = loadSessions(cwd);
    const latest = sessions[0];
    const sessStatus = latest?.status || "";
    const failed = code !== 0 || ["dod_failed", "error", "denied"].includes(sessStatus);
    if (failed) {
      await runRatchetScan(cwd);
      postToAgentWebviews({ type: "ratchetAlert", reason: sessStatus || "error" });
    }
    if (opts.fromPlan && code === 0 && opts.markDone?.length) {
      savePlanFile(
        cwd,
        ".meris/plan/tasks.md",
        (loadPlanPayload(cwd)?.items || []).map((item) => ({
          ...item,
          done: item.done || opts.markDone.includes(item.text),
        }))
      );
    }
    postToAgentWebviews({
      type: "status",
      status,
      code,
      stderr: stderr.slice(-500),
    });
    refreshAgentSidebarData(cwd);
  });
}

function getEditorSelection(cwd) {
  const ed = vscode.window.activeTextEditor;
  if (!ed || !cwd) return null;
  const sel = ed.selection;
  if (sel.isEmpty) return null;
  const rel = path.relative(cwd, ed.document.uri.fsPath).replace(/\\/g, "/");
  return {
    path: rel,
    content: ed.document.getText(sel),
    startLine: sel.start.line + 1,
    endLine: sel.end.line + 1,
  };
}

/** @param {string} cwd @param {string} query */
async function listContextFiles(cwd, query) {
  const pattern = query ? `**/*${query}*` : "**/*";
  const uris = await vscode.workspace.findFiles(
    new vscode.RelativePattern(cwd, pattern),
    new vscode.RelativePattern(cwd, "**/{node_modules,.git,.meris}/**"),
    80
  );
  return uris.map((u) => path.relative(cwd, u.fsPath).replace(/\\/g, "/"));
}

/** @param {string} cwd @param {string} dataUrl @param {string} filename */
async function saveContextImage(cwd, dataUrl, filename) {
  const m = String(dataUrl).match(/^data:image\/([\w+-]+);base64,(.+)$/s);
  if (!m) throw new Error("invalid image");
  const extMap = { png: ".png", jpeg: ".jpg", jpg: ".jpg", gif: ".gif", webp: ".webp" };
  const ext = extMap[m[1].toLowerCase()] || ".png";
  const raw = Buffer.from(m[2], "base64");
  if (raw.length > 8 * 1024 * 1024) throw new Error("image too large");
  const safe = (filename || "paste").replace(/[^\w.\-]+/g, "_").slice(0, 40) || "paste";
  const name = /\.(png|jpe?g|gif|webp)$/i.test(safe) ? safe : safe + ext;
  const ts = new Date().toISOString().replace(/[-:]/g, "").slice(0, 15);
  const relDir = path.join(".meris", "context", "images");
  const outDir = path.join(cwd, relDir);
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
  const rel = path.join(relDir, `${ts}-${name}`).replace(/\\/g, "/");
  fs.writeFileSync(path.join(cwd, rel), raw);
  const previewUrl = raw.length <= 200_000 ? `data:image/${m[1]};base64,${m[2]}` : undefined;
  return {
    kind: "image",
    path: rel,
    content: `[Image attached at ${rel}]`,
    previewUrl,
  };
}

/** @param {string} rel */
function languageIdFromPath(rel) {
  const ext = path.extname(String(rel || "")).slice(1).toLowerCase();
  const map = {
    py: "python",
    pyi: "python",
    js: "javascript",
    mjs: "javascript",
    cjs: "javascript",
    jsx: "javascript",
    ts: "typescript",
    tsx: "typescript",
    json: "json",
    yaml: "yaml",
    yml: "yaml",
    md: "markdown",
    markdown: "markdown",
    mdx: "markdown",
    html: "html",
    htm: "html",
    css: "css",
    scss: "css",
    rs: "rust",
    go: "go",
    sh: "shellscript",
    bash: "shellscript",
    ps1: "powershell",
    sql: "sql",
    toml: "toml",
    xml: "xml",
    java: "java",
    kt: "kotlin",
    rb: "ruby",
    php: "php",
    swift: "swift",
    c: "c",
    cpp: "cpp",
    h: "c",
    hpp: "cpp",
    cs: "csharp",
    vue: "javascript",
    svelte: "javascript",
  };
  return map[ext];
}

/** @param {string} base @param {string} rel */
async function openWorkspaceFile(base, rel) {
  const full = path.isAbsolute(rel) ? rel : path.join(base, rel);
  const uri = vscode.Uri.file(full);
  const languageId = languageIdFromPath(rel);
  const doc = languageId
    ? await vscode.workspace.openTextDocument({ uri, language: languageId })
    : await vscode.workspace.openTextDocument(uri);
  await vscode.window.showTextDocument(doc, { preview: false, viewColumn: vscode.ViewColumn.One });
  return doc;
}

function postFilePreview(rel, content, root) {
  postToAgentWebviews({
    type: "filePreview",
    path: rel.replace(/\\/g, "/"),
    content: content || "",
    root: root ? String(root) : "",
  });
}

/** @param {string} cwd @param {string} rel */
async function readContextFile(cwd, rel) {
  const doc = await openWorkspaceFile(cwd, rel);
  return { path: rel.replace(/\\/g, "/"), content: doc.getText().slice(0, 12000) };
}

/** @param {string} cwd @param {string} relPath @param {string} patchText */
function applyHunkPatch(cwd, relPath, patchText) {
  const tmpDir = path.join(cwd, ".meris", "tmp");
  if (!fs.existsSync(tmpDir)) fs.mkdirSync(tmpDir, { recursive: true });
  const tmp = path.join(tmpDir, "hunk.patch");
  const body = patchText.includes("---") ? patchText : `--- a/${relPath}\n+++ b/${relPath}\n${patchText}`;
  fs.writeFileSync(tmp, body, "utf8");
  execFileSync("git", ["apply", "--unsafe-paths", tmp], { cwd, stdio: "pipe" });
}

/** @param {string} cwd @param {string} planPath @param {object[]} items */
function savePlanFile(cwd, planPath, items) {
  const tmpDir = path.join(cwd, ".meris", "tmp");
  if (!fs.existsSync(tmpDir)) fs.mkdirSync(tmpDir, { recursive: true });
  const tmp = path.join(tmpDir, "plan-sync.json");
  fs.writeFileSync(tmp, JSON.stringify({ items }), "utf8");
  try {
    execFileSync("meris", ["plan-sync", planPath, "--items-file", tmp], { cwd, stdio: "pipe" });
    postToAgentWebviews({ type: "planSaved", path: planPath, items });
  } catch (e) {
    vscode.window.showErrorMessage("Meris: plan save failed — " + String(e.message || e));
  }
}

/** @param {string} cwd @param {string[]} tasks @param {string} mode @param {boolean} isolate */
function spawnMerisParallel(cwd, tasks, mode, isolate) {
  killActiveProcess();
  const eventsPath = path.join(cwd, ".meris", "events", "agent-window.jsonl");
  const eventsArg = eventsPath.replace(/\\/g, "/");
  const postEvent = (ev) => {
    postToAgentWebviews({ type: "event", event: enrichEvent(cwd, ev) });
  };

  const eventDir = path.dirname(eventsPath);
  if (!fs.existsSync(eventDir)) fs.mkdirSync(eventDir, { recursive: true });
  fs.writeFileSync(eventsPath, "", "utf8");
  startJsonlTail(eventsPath, postEvent);

  postToAgentWebviews({ type: "parallelStart", tasks, mode });
  postToAgentWebviews({ type: "status", status: "running" });

  const args = [
    "parallel",
    ...tasks.map((t) => `"${t.replace(/"/g, '\\"')}"`),
    "--mode",
    mode,
    "--event-stream",
    eventsArg,
  ];
  if (isolate) args.push("--isolate");
  activeProcess = spawn("meris", args, { cwd, shell: true, env: { ...process.env } });
  let stderr = "";
  const emitTerm = (stream, chunk) =>
    postToAgentWebviews({ type: "terminal", stream, chunk: chunk.toString() });
  activeProcess.stdout?.on("data", (c) => emitTerm("stdout", c));
  activeProcess.stderr?.on("data", (c) => {
    stderr += c.toString();
    emitTerm("stderr", c);
  });
  activeProcess.on("close", (code) => {
    activeProcess = null;
    for (const ev of readNewJsonlEvents(eventsPath)) {
      postEvent(ev);
    }
    postToAgentWebviews({ type: "status", status: code === 0 ? "done" : "error", stderr: stderr.slice(-500) });
    postToAgentWebviews({ type: "parallelDone", code, tasks });
    refreshAgentSidebarData(cwd);
  });
}

/** @param {string} cwd @param {string} commandId */
function spawnCliCommand(cwd, commandId) {
  const argv = RUNNABLE_CLI[commandId];
  if (!argv) {
    postToAgentWebviews({
      type: "cliRunDone",
      commandId,
      code: 1,
      ok: false,
      error: "command not runnable from UI",
    });
    return;
  }
  if (activeCliProcess && !activeCliProcess.killed) {
    activeCliProcess.kill("SIGTERM");
    activeCliProcess = null;
  }
  const display = "meris " + argv.join(" ");
  postToAgentWebviews({ type: "cliRunStart", commandId, cmd: display });
  const emitTerm = (stream, chunk) =>
    postToAgentWebviews({ type: "terminal", stream, chunk: chunk.toString() });
  activeCliProcess = spawn("meris", argv, { cwd, env: { ...process.env } });
  activeCliProcess.stdout?.on("data", (c) => emitTerm("stdout", c));
  activeCliProcess.stderr?.on("data", (c) => emitTerm("stderr", c));
  activeCliProcess.on("close", (code) => {
    activeCliProcess = null;
    postToAgentWebviews({
      type: "cliRunDone",
      commandId,
      cmd: display,
      code: code ?? 1,
      ok: code === 0,
    });
  });
}

/** @param {object} msg */
async function handleAgentMessage(msg) {
  if (msg.type === "getWorkspace") {
    postWorkspaceInfo();
    return;
  }
  if (msg.type === "getGitSummary") {
    const roots = Array.isArray(msg.roots) ? msg.roots.map(String) : [];
    postGitSummary(roots, msg._gitReqId);
    return;
  }
  if (msg.type === "gitStage" && msg.root) {
    const result = gitStageRoot(String(msg.root));
    postGitSummary([]);
    postToAgentWebviews({ type: "gitStageResult", _gitReqId: msg._gitReqId, ...result });
    return;
  }
  if (msg.type === "gitCommit" && msg.root) {
    const cwd = getWorkspaceCwd() || String(msg.root);
    const result = gitCommitRoot(String(msg.root), String(msg.message || ""), cwd);
    postGitSummary([]);
    postToAgentWebviews({ type: "gitCommitResult", _gitReqId: msg._gitReqId, ...result });
    return;
  }
  if (msg.type === "gitSuggestMessage" && msg.root) {
    const result = gitSuggestRoot(String(msg.root));
    postToAgentWebviews({ type: "gitSuggestResult", _gitReqId: msg._gitReqId, ...result });
    return;
  }
  if (msg.type === "gitShipScope") {
    const cwd = getWorkspaceCwd();
    if (!cwd) return;
    const result = gitShipScope(cwd);
    postGitSummary([]);
    postToAgentWebviews({ type: "gitShipResult", _gitReqId: msg._gitReqId, ...result });
    return;
  }
  if (msg.type === "gitPush" && msg.root) {
    const result = gitPushRoot(String(msg.root));
    postGitSummary([]);
    postToAgentWebviews({ type: "gitPushResult", _gitReqId: msg._gitReqId, ...result });
    return;
  }
  if (msg.type === "setWorkspace" && msg.path) {
    setActiveWorkspace(String(msg.path));
    return;
  }
  if (msg.type === "setTaskScope") {
    const active = getWorkspaceCwd();
    if (!active) return;
    const paths = Array.isArray(msg.paths) ? msg.paths.map(String) : [];
    const available = getAvailableProjectPaths(active);
    const normalized = normalizeTaskScope(paths, available, active);
    await saveTaskScopePaths(normalized);
    postWorkspaceInfo("update");
    return;
  }
  if (msg.type === "clearPlan") {
    const cwd = getWorkspaceCwd();
    if (!cwd) return;
    const rel = String(msg.path || ".meris/plan/tasks.md");
    const planFile = path.isAbsolute(rel) ? rel : path.join(cwd, rel);
    const harnessPlan = path.join(cwd, ".meris", "plan", "tasks.md");
    for (const fp of [planFile, harnessPlan]) {
      try {
        if (fs.existsSync(fp)) fs.unlinkSync(fp);
      } catch {
        /* ignore */
      }
    }
    postToAgentWebviews({ type: "planCleared" });
    postToAgentWebviews({ type: "plan", path: "", items: [] });
    return;
  }
  if (msg.type === "addWorkspaceRoot" && msg.path) {
    const created = await addExtraRoot(String(msg.path));
    postWorkspaceInfo("add", {
      addedPath: String(msg.path),
      alreadyExists: !created,
    });
    return;
  }
  if (msg.type === "removeWorkspaceRoot" && msg.path) {
    const rem = String(msg.path);
    await removeExtraRoot(rem);
    const active = getWorkspaceCwd();
    if (active && path.resolve(active) === path.resolve(rem)) {
      const next = discoverWorkspaceFolders()[0];
      if (next) setActiveWorkspace(next.path);
      else postWorkspaceInfo("update");
    } else {
      postWorkspaceInfo("update");
    }
    return;
  }

  const cwd = getWorkspaceCwd();
  if (!cwd) {
    if (msg.type === "submit" || msg.type === "resumeSession") {
      vscode.window.showErrorMessage("Meris: open a workspace folder first.");
    }
    return;
  }

  switch (msg.type) {
    case "submit":
      postToAgentWebviews({
        type: "runStart",
        task: msg.displayTask || msg.task,
        mode: msg.mode,
      });
      postToAgentWebviews({ type: "status", status: "running" });
      spawnMerisRun(cwd, {
        task: msg.task,
        mode: msg.mode,
        approve: Boolean(msg.approve),
        resume: false,
      });
      break;
    case "planRun": {
      const execCwd = pickPlanExecuteRoot(cwd);
      if (path.resolve(execCwd) !== path.resolve(cwd)) {
        setActiveWorkspace(execCwd);
      }
      const task = msg.task || "implement the plan";
      postToAgentWebviews({ type: "runStart", task, mode: "run" });
      postToAgentWebviews({ type: "status", status: "running" });
      spawnMerisRun(execCwd, {
        task,
        mode: "run",
        approve: Boolean(msg.approve),
        resume: false,
        fromPlan: true,
        ratchetAfter: true,
        markDone: Array.isArray(msg.markDone) ? msg.markDone : [],
      });
      break;
    }
    case "resumeSession": {
      const sessions = loadSessions(cwd);
      const rec = sessions.find((s) => s.id === msg.sessionId);
      if (!rec) {
        vscode.window.showErrorMessage(`Meris: session not found: ${msg.sessionId}`);
        return;
      }
      postToAgentWebviews({
        type: "runStart",
        task: rec.task,
        mode: rec.mode,
        resume: true,
        sessionId: msg.sessionId,
      });
      postToAgentWebviews({ type: "status", status: "running" });
      spawnMerisRun(cwd, {
        task: rec.task,
        mode: rec.mode,
        approve: Boolean(msg.approve),
        resume: true,
        sessionId: msg.sessionId,
      });
      break;
    }
    case "refreshSessions":
    case "refreshRatchet":
      refreshAgentSidebarData(cwd);
      break;
    case "approvalResponse":
      if (msg.requestId) {
        writeApprovalResponse(cwd, msg.requestId, Boolean(msg.approved));
      }
      break;
    case "openFile": {
      if (!msg.path) return;
      const base = String(msg.root || cwd);
      const rel = String(msg.path);
      try {
        const full = path.isAbsolute(rel) ? rel : path.join(base, rel);
        const content = fs.readFileSync(full, "utf8");
        postFilePreview(rel, content, base);
        await openWorkspaceFile(base, rel);
      } catch (e) {
        vscode.window.showErrorMessage(
          "Meris: cannot open " + msg.path + " — " + String(e.message || e)
        );
      }
      break;
    }
    case "ratchetApply":
    case "ratchetReject": {
      if (!msg.proposalId) return;
      const subcmd = msg.type === "ratchetApply" ? "apply" : "reject";
      const result = await runRatchetCli(cwd, subcmd, msg.proposalId);
      postToAgentWebviews({
        type: "ratchetResult",
        action: subcmd,
        proposalId: msg.proposalId,
        ok: result.ok,
        detail: result.stderr,
      });
      refreshAgentSidebarData(cwd);
      break;
    }
    case "ratchetScan": {
      const result = await runRatchetScan(cwd);
      postToAgentWebviews({
        type: "ratchetResult",
        action: "scan",
        ok: result.ok,
        detail: result.stderr || (result.ok ? "scan complete" : "scan failed"),
      });
      refreshAgentSidebarData(cwd);
      break;
    }
    case "stop":
      killActiveProcess();
      postToAgentWebviews({ type: "status", status: "cancelled" });
      refreshAgentSidebarData(cwd);
      break;
    case "listContextFiles": {
      const files = await listContextFiles(cwd, String(msg.query || ""));
      postToAgentWebviews({ type: "contextFiles", files });
      break;
    }
    case "listDir": {
      const root = String(msg.root || cwd);
      postToAgentWebviews({
        type: "dirListing",
        dir: String(msg.dir || ""),
        root,
        entries: listDirEntries(root, String(msg.dir || "")),
      });
      break;
    }
    case "listSkills":
      postToAgentWebviews({
        type: "skillsList",
        skills: listSkillsOnDisk(cwd),
        prefs: loadSkillPrefsOnDisk(cwd),
      });
      break;
    case "toggleSkillEnabled": {
      try {
        setSkillEnabledOnDisk(cwd, String(msg.name || ""), Boolean(msg.enabled));
        postToAgentWebviews({
          type: "skillsList",
          skills: listSkillsOnDisk(cwd),
          prefs: loadSkillPrefsOnDisk(cwd),
        });
      } catch (e) {
        vscode.window.showErrorMessage("Meris: " + String(e.message || e));
      }
      break;
    }
    case "pickSkillImportDir": {
      const uris = await vscode.window.showOpenDialog({
        canSelectFolders: true,
        canSelectFiles: false,
        openLabel: "选择技能目录",
      });
      if (!uris?.[0]) break;
      const picked = uris[0].fsPath;
      setSkillImportSourceOnDisk(cwd, picked);
      postToAgentWebviews({
        type: "skillImportSource",
        path: picked,
        prefs: loadSkillPrefsOnDisk(cwd),
        skills: listSkillsOnDisk(cwd),
      });
      break;
    }
    case "importSkills": {
      const { count, src } = runSkillImportOnDisk(cwd, msg.path ? String(msg.path) : undefined);
      postToAgentWebviews({
        type: "skillsList",
        skills: listSkillsOnDisk(cwd),
        prefs: loadSkillPrefsOnDisk(cwd),
      });
      postToAgentWebviews({
        type: "importResult",
        ok: count > 0,
        kind: "skills",
        detail: !src
          ? "请先选择本地技能目录"
          : count > 0
            ? `已从 ${src} 导入 ${count} 个技能`
            : `目录为空或无可识别技能：${src}`,
        sourcePath: src || "",
      });
      if (count > 0) vscode.window.showInformationMessage(`Meris: 已导入 ${count} 个技能`);
      break;
    }
    case "importCursorSkills": {
      const cursorDir = path.join(cwd, ".cursor", "skills");
      const count = fs.existsSync(cursorDir) ? importSkillsFromDirOnDisk(cwd, cursorDir) : 0;
      postToAgentWebviews({
        type: "skillsList",
        skills: listSkillsOnDisk(cwd),
        prefs: loadSkillPrefsOnDisk(cwd),
      });
      postToAgentWebviews({
        type: "importResult",
        ok: count > 0,
        kind: "skills",
        detail:
          count > 0
            ? `已从 ${cursorDir} 导入 ${count} 个技能`
            : "未找到 .cursor/skills/ 或可导入文件",
        sourcePath: cursorDir,
      });
      if (count > 0) vscode.window.showInformationMessage(`Meris: 已导入 ${count} 个技能`);
      break;
    }
    case "installBundledSkill": {
      try {
        const name = installBundledSkillOnDisk(cwd, String(msg.name || ""));
        if (!name) {
          vscode.window.showWarningMessage("Meris: bundled skill not found");
          break;
        }
        postToAgentWebviews({
          type: "skillsList",
          skills: listSkillsOnDisk(cwd),
          prefs: loadSkillPrefsOnDisk(cwd),
        });
        if (msg.forEditor) {
          const item = readSkillOnDisk(cwd, name);
          if (item) {
            postToAgentWebviews({
              type: "skillContent",
              name,
              content: item.content,
              skills: listSkillsOnDisk(cwd),
              prefs: loadSkillPrefsOnDisk(cwd),
            });
          }
        }
        vscode.window.showInformationMessage(`Meris: 已安装技能 ${name}`);
      } catch (e) {
        vscode.window.showErrorMessage("Meris: " + String(e.message || e));
      }
      break;
    }
    case "installBundledToGlobal": {
      try {
        const name = installBundledToGlobalOnDisk(String(msg.name || ""));
        if (!name) {
          vscode.window.showWarningMessage("Meris: bundled skill not found");
          break;
        }
        postToAgentWebviews({
          type: "skillsList",
          skills: listSkillsOnDisk(cwd),
          prefs: loadSkillPrefsOnDisk(cwd),
        });
        if (msg.forEditor) {
          const item = readSkillOnDisk(cwd, name);
          if (item) {
            postToAgentWebviews({
              type: "skillContent",
              name,
              content: item.content,
              skills: listSkillsOnDisk(cwd),
              prefs: loadSkillPrefsOnDisk(cwd),
            });
          }
        }
        vscode.window.showInformationMessage(`Meris: 已安装全局技能 ${name}`);
      } catch (e) {
        vscode.window.showErrorMessage("Meris: " + String(e.message || e));
      }
      break;
    }
    case "saveSkillPrefs": {
      if ("importSourcePath" in msg) {
        const picked = String(msg.importSourcePath || "");
        setSkillImportSourceOnDisk(cwd, picked);
        postToAgentWebviews({
          type: "skillImportSource",
          path: picked,
          prefs: loadSkillPrefsOnDisk(cwd),
          skills: listSkillsOnDisk(cwd),
        });
      }
      postToAgentWebviews({
        type: "skillsList",
        skills: listSkillsOnDisk(cwd),
        prefs: loadSkillPrefsOnDisk(cwd),
      });
      break;
    }
    case "readSkill": {
      if (!msg.name) break;
      const item = readSkillOnDisk(cwd, String(msg.name));
      if (!item) {
        vscode.window.showWarningMessage("Meris: skill not found — " + msg.name);
        break;
      }
      if (msg.forEditor) {
        postToAgentWebviews({
          type: "skillContent",
          name: String(msg.name),
          content: item.content,
          skills: listSkillsOnDisk(cwd),
          prefs: loadSkillPrefsOnDisk(cwd),
        });
      } else {
        postToAgentWebviews({ type: "contextItem", item });
      }
      break;
    }
    case "listRules":
      postToAgentWebviews({ type: "rulesList", rules: listRulesOnDisk(cwd) });
      break;
    case "readRule": {
      const item = readRuleOnDisk(cwd, String(msg.name || ""));
      if (item) postToAgentWebviews({ type: "ruleContent", name: item.name, content: item.content });
      break;
    }
    case "saveRule": {
      try {
        const name = saveRuleOnDisk(cwd, String(msg.name || ""), String(msg.content || ""));
        postToAgentWebviews({ type: "rulesList", rules: listRulesOnDisk(cwd) });
        vscode.window.showInformationMessage(`Meris: rule saved — ${name}`);
      } catch (e) {
        vscode.window.showErrorMessage("Meris: " + String(e.message || e));
      }
      break;
    }
    case "getModels":
      postToAgentWebviews({ type: "modelsInfo", ...listModelsFromSettings(cwd) });
      break;
    case "importCursorRules": {
      const count = importCursorRulesOnDisk(cwd);
      if (count <= 0) {
        postToAgentWebviews({
          type: "importResult",
          ok: false,
          kind: "rules",
          detail: "未找到 .cursor/rules/ 或可导入文件",
        });
      } else {
        postToAgentWebviews({ type: "rulesList", rules: listRulesOnDisk(cwd) });
        postToAgentWebviews({
          type: "importResult",
          ok: true,
          kind: "rules",
          detail: `已导入 ${count} 条规则`,
        });
        vscode.window.showInformationMessage(`Meris: 已导入 ${count} 条 Cursor 规则`);
      }
      break;
    }
    case "runCliCommand": {
      const cwd = getWorkspaceCwd();
      if (!cwd) {
        vscode.window.showErrorMessage("Meris: open a workspace folder first.");
        break;
      }
      spawnCliCommand(cwd, String(msg.id || ""));
      break;
    }
    case "listCommands": {
      postToAgentWebviews({ type: "commandsList", ...listCliCommandsOnDisk() });
      break;
    }
    case "listDocs": {
      postToAgentWebviews({ type: "docsList", docs: listDocsOnDisk() });
      break;
    }
    case "readDoc": {
      const doc = readDocOnDisk(String(msg.id || ""));
      if (doc) postToAgentWebviews({ type: "docContent", ...doc });
      break;
    }
    case "listMcp": {
      const info = await fetchMcpInfo(cwd);
      postToAgentWebviews({ type: "mcpInfo", ...info });
      break;
    }
    case "importCursorMcp": {
      const cursorPath = path.join(cwd, ".cursor", "mcp.json");
      if (!fs.existsSync(cursorPath)) {
        postToAgentWebviews({ type: "mcpImportError", error: "未找到 .cursor/mcp.json" });
        break;
      }
      try {
        const raw = JSON.parse(fs.readFileSync(cursorPath, "utf8"));
        const servers = raw.mcpServers || raw;
        writeUiMcpServers(
          cwd,
          Object.entries(servers).map(([name, cfg]) => ({
            name,
            ...(typeof cfg === "object" && cfg ? cfg : {}),
            transport: cfg && cfg.url ? "sse" : "stdio",
            enabled: cfg && cfg.enabled !== false,
          }))
        );
        const info = await fetchMcpInfo(cwd);
        postToAgentWebviews({ type: "mcpInfo", ...info });
        postToAgentWebviews({
          type: "importResult",
          ok: true,
          kind: "mcp",
          detail: "已从 .cursor/mcp.json 导入 MCP",
        });
        vscode.window.showInformationMessage("Meris: 已从 .cursor/mcp.json 导入 MCP");
      } catch (e) {
        postToAgentWebviews({ type: "mcpImportError", error: String(e.message || e) });
      }
      break;
    }
    case "saveMcpServers": {
      writeUiMcpServers(cwd, Array.isArray(msg.servers) ? msg.servers : []);
      const info = await fetchMcpInfo(cwd);
      postToAgentWebviews({ type: "mcpInfo", ...info });
      break;
    }
    case "migrateMcpToUi": {
      const ok = migrateMcpSettingsToUiOnDisk(cwd);
      const info = await fetchMcpInfo(cwd);
      postToAgentWebviews({ type: "mcpInfo", ...info });
      postToAgentWebviews({
        type: "importResult",
        ok,
        kind: "mcp",
        detail: ok ? "已从 settings.yaml 迁移到 UI 配置" : "无可迁移的 MCP 或已存在 UI 配置",
      });
      if (ok) vscode.window.showInformationMessage("Meris: MCP 已迁移到 .meris/ui/mcp-servers.json");
      break;
    }
    case "importMcpFromPath": {
      const filePath = String(msg.path || "").trim();
      if (!filePath) break;
      const ok = importMcpFromPathOnDisk(cwd, filePath);
      const info = await fetchMcpInfo(cwd);
      postToAgentWebviews({ type: "mcpInfo", ...info });
      postToAgentWebviews({
        type: "importResult",
        ok,
        kind: "mcp",
        detail: ok ? `已从 ${filePath} 导入 MCP` : `无法从 ${filePath} 导入 MCP`,
      });
      if (ok) vscode.window.showInformationMessage("Meris: MCP 导入完成");
      break;
    }
    case "importRulesFromPath": {
      const dirPath = String(msg.path || "").trim();
      if (!dirPath) break;
      const count = importRulesFromDirOnDisk(cwd, dirPath);
      if (count <= 0) {
        postToAgentWebviews({
          type: "importResult",
          ok: false,
          kind: "rules",
          detail: `目录为空或无可导入文件：${dirPath}`,
        });
      } else {
        postToAgentWebviews({ type: "rulesList", rules: listRulesOnDisk(cwd) });
        postToAgentWebviews({
          type: "importResult",
          ok: true,
          kind: "rules",
          detail: `已从 ${dirPath} 导入 ${count} 条规则`,
        });
        vscode.window.showInformationMessage(`Meris: 已导入 ${count} 条规则`);
      }
      break;
    }
    case "pickImportMcpFile": {
      const uris = await vscode.window.showOpenDialog({
        canSelectFiles: true,
        canSelectFolders: false,
        filters: { JSON: ["json"] },
        openLabel: "选择 mcp.json",
      });
      if (uris?.[0]) {
        postToAgentWebviews({
          type: "importPathPicked",
          kind: "mcp",
          path: uris[0].fsPath,
        });
      }
      break;
    }
    case "pickImportRulesDir": {
      const uris = await vscode.window.showOpenDialog({
        canSelectFolders: true,
        canSelectFiles: false,
        openLabel: "选择规则目录",
      });
      if (uris?.[0]) {
        postToAgentWebviews({
          type: "importPathPicked",
          kind: "rules",
          path: uris[0].fsPath,
        });
      }
      break;
    }
    case "saveSkill": {
      try {
        const name = saveSkillOnDisk(cwd, String(msg.name || ""), String(msg.content || ""));
        postToAgentWebviews({
          type: "skillsList",
          skills: listSkillsOnDisk(cwd),
          prefs: loadSkillPrefsOnDisk(cwd),
        });
        if (msg.forEditor) {
          postToAgentWebviews({
            type: "skillContent",
            name,
            content: fs.readFileSync(path.join(cwd, ".meris", "skills", `${name}.md`), "utf8"),
            skills: listSkillsOnDisk(cwd),
            prefs: loadSkillPrefsOnDisk(cwd),
          });
        }
        vscode.window.showInformationMessage(`Meris: skill saved — ${name}`);
      } catch (e) {
        vscode.window.showErrorMessage("Meris: " + String(e.message || e));
      }
      break;
    }
    case "saveGlobalSkill": {
      try {
        const name = saveGlobalSkillOnDisk(String(msg.name || ""), String(msg.content || ""));
        postToAgentWebviews({
          type: "skillsList",
          skills: listSkillsOnDisk(cwd),
          prefs: loadSkillPrefsOnDisk(cwd),
        });
        if (msg.forEditor) {
          const item = readSkillOnDisk(cwd, name);
          if (item) {
            postToAgentWebviews({
              type: "skillContent",
              name,
              content: item.content,
              skills: listSkillsOnDisk(cwd),
              prefs: loadSkillPrefsOnDisk(cwd),
            });
          }
        }
        vscode.window.showInformationMessage(`Meris: global skill saved — ${name}`);
      } catch (e) {
        vscode.window.showErrorMessage("Meris: " + String(e.message || e));
      }
      break;
    }
    case "openFolder": {
      const uris = await vscode.window.showOpenDialog({
        canSelectFolders: true,
        canSelectFiles: false,
        openLabel: "Open Folder",
      });
      if (uris?.[0]) setActiveWorkspace(uris[0].fsPath);
      break;
    }
    case "addWorkspaceRootDialog": {
      const uris = await vscode.window.showOpenDialog({
        canSelectFolders: true,
        canSelectFiles: false,
        openLabel: "Add Root Folder",
      });
      if (uris?.[0]) {
        const created = await addExtraRoot(uris[0].fsPath);
        postWorkspaceInfo("add", {
          addedPath: uris[0].fsPath,
          alreadyExists: !created,
        });
        vscode.window.showInformationMessage(
          created
            ? `Meris: 已添加根目录 — ${uris[0].fsPath}`
            : `Meris: 已在工作区中 — ${uris[0].fsPath}`
        );
      }
      break;
    }
    case "openMerisRoot": {
      const meris = discoverWorkspaceFolders().find((f) => f.isMeris);
      if (meris) setActiveWorkspace(meris.path);
      else vscode.window.showWarningMessage("未找到 meris 仓库 — 请 Open Folder 选择 meris 目录");
      break;
    }
    case "readContextFile": {
      if (!msg.path) break;
      try {
        const root = String(msg.root || cwd);
        const item = await readContextFile(root, msg.path);
        postToAgentWebviews({ type: "contextItem", item });
      } catch {
        vscode.window.showErrorMessage("Meris: cannot read " + msg.path);
      }
      break;
    }
    case "saveContextImage": {
      if (!msg.dataUrl) break;
      try {
        const item = await saveContextImage(cwd, String(msg.dataUrl), String(msg.filename || ""));
        postToAgentWebviews({ type: "contextItem", item });
      } catch (e) {
        postToAgentWebviews({
          type: "contextImageError",
          error: String(e.message || e),
        });
      }
      break;
    }
    case "addContextSelection": {
      const item = getEditorSelection(cwd);
      if (item) postToAgentWebviews({ type: "contextItem", item });
      else vscode.window.showWarningMessage("Meris: no editor selection");
      break;
    }
    case "applyHunk": {
      if (!msg.path || !msg.patch) break;
      try {
        applyHunkPatch(cwd, msg.path, msg.patch);
        vscode.window.showInformationMessage("Meris: hunk applied");
      } catch (e) {
        vscode.window.showErrorMessage("Meris: apply failed — " + String(e.message || e));
      }
      break;
    }
    case "loadPreview": {
      if (!msg.path) break;
      const base = String(msg.root || cwd);
      const full = path.isAbsolute(msg.path) ? msg.path : path.join(base, msg.path);
      try {
        const text = fs.readFileSync(full, "utf8");
        if (/\.(html?|htm)$/i.test(msg.path)) {
          postToAgentWebviews({ type: "preview", path: msg.path, html: text });
        } else {
          postFilePreview(msg.path, text, base);
        }
      } catch {
        vscode.window.showErrorMessage("Meris: preview failed for " + msg.path);
      }
      break;
    }
    case "savePlan":
      if (msg.path && msg.items) savePlanFile(cwd, msg.path, msg.items);
      break;
    case "parallelRun": {
      const tasks = Array.isArray(msg.tasks) ? msg.tasks : [];
      if (!tasks.length) break;
      spawnMerisParallel(cwd, tasks, msg.mode || "ask", Boolean(msg.isolate));
      break;
    }
    default:
      break;
  }
}

/** @param {vscode.Webview} webview */
function registerAgentWebview(webview) {
  agentWebviews.add(webview);
  webview.onDidReceiveMessage(handleAgentMessage);
}

/** @param {vscode.ExtensionContext} context */
function setupAgentWebview(webview, context) {
  const extensionUri = context.extensionUri;
  webview.options = {
    enableScripts: true,
    localResourceRoots: [vscode.Uri.joinPath(extensionUri, "media")],
  };
  webview.html = getAgentWebviewContent(webview, extensionUri);
  registerAgentWebview(webview);
  postWorkspaceInfo();
  const cwd = getWorkspaceCwd();
  if (cwd) {
    refreshAgentSidebarData(cwd);
  }
}

class MerisAgentViewProvider {
  /** @param {vscode.ExtensionContext} context */
  constructor(context) {
    this.context = context;
  }

  /** @param {vscode.WebviewView} webviewView */
  resolveWebviewView(webviewView) {
    setupAgentWebview(webviewView.webview, this.context);
    webviewView.onDidDispose(() => {
      agentWebviews.delete(webviewView.webview);
    });
  }
}

/** @param {vscode.ExtensionContext} context */
function openAgentWindow(context) {
  if (agentPanel) {
    agentPanel.reveal(vscode.ViewColumn.Beside);
    return;
  }

  agentPanel = vscode.window.createWebviewPanel(
    "merisAgentWindow",
    "Meris Agent",
    vscode.ViewColumn.Beside,
    {
      enableScripts: true,
      retainContextWhenHidden: true,
      localResourceRoots: [vscode.Uri.joinPath(context.extensionUri, "media")],
    }
  );

  setupAgentWebview(agentPanel.webview, context);

  agentPanel.onDidDispose(() => {
    agentWebviews.delete(agentPanel.webview);
    stopTail();
    killActiveProcess();
    agentPanel = null;
  });
}

/** @param {vscode.ExtensionContext} context */
function activate(context) {
  extensionContext = context;
  activeWorkspacePath = context.globalState.get("meris.activeWorkspace") || null;
  if (!activeWorkspacePath || !fs.existsSync(activeWorkspacePath)) {
    activeWorkspacePath = getDefaultWorkspacePath() || null;
  }

  const viewProvider = new MerisAgentViewProvider(context);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider("meris.agentView", viewProvider, {
      webviewOptions: { retainContextWhenHidden: true },
    }),
    vscode.commands.registerCommand("meris.ask", () => runMerisTask("ask")),
    vscode.commands.registerCommand("meris.plan", () => runMerisTask("plan")),
    vscode.commands.registerCommand("meris.run", () => runMerisTask("run")),
    vscode.commands.registerCommand("meris.runApprove", () =>
      runMerisTask("run", ["--approve"])
    ),
    vscode.commands.registerCommand("meris.runWithEvents", runMerisWithEvents),
    vscode.commands.registerCommand("meris.review", runMerisReview),
    vscode.commands.registerCommand("meris.exec", runMerisExec),
    vscode.commands.registerCommand("meris.doctor", () =>
      runMerisSimple("doctor", "Meris Doctor")
    ),
    vscode.commands.registerCommand("meris.tui", () =>
      runMerisSimple("tui", "Meris TUI")
    ),
    vscode.commands.registerCommand("meris.agentWindow", () => openAgentWindow(context)),
    vscode.commands.registerCommand("meris.agentView.focus", () => {
      vscode.commands.executeCommand("workbench.view.extension.meris-sidebar");
    })
  );
}

function deactivate() {
  stopTail();
  killActiveProcess();
  agentWebviews.clear();
}

module.exports = { activate, deactivate };
