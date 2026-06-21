/* Rich file preview — syntax highlight + markdown (Preview tab & iframe srcdoc) */
(function () {
  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  const EXT_LANG = {
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
    sh: "bash",
    bash: "bash",
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

  function extLang(path) {
    const base = String(path || "").split(/[/\\]/).pop() || "";
    const dot = base.lastIndexOf(".");
    if (dot < 0) return "plaintext";
    return EXT_LANG[base.slice(dot + 1).toLowerCase()] || "plaintext";
  }

  function isMarkdownPath(path) {
    return /\.(md|markdown|mdx)$/i.test(String(path || ""));
  }

  function isHtmlPath(path) {
    return /\.(html?|htm)$/i.test(String(path || ""));
  }

  function span(cls, text) {
    return '<span class="tok-' + cls + '">' + text + "</span>";
  }

  function highlightGeneric(code) {
    let s = escapeHtml(code);
    s = s.replace(/(\/\/.*$|#.*$)/gm, (m) => span("cmt", m));
    s = s.replace(/("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)/g, (m) => span("str", m));
    s = s.replace(/\b(0x[\da-fA-F]+|\d+\.?\d*)\b/g, (m) => span("num", m));
    s = s.replace(
      /\b(function|const|let|var|return|if|else|for|while|class|import|export|from|async|await|def|raise|try|except|with|as|pass|yield|True|False|None|null|undefined|struct|enum|impl|fn|pub|use|mod|match|loop|interface|type|namespace|public|private|protected|void|int|float|bool|string)\b/g,
      (m) => span("kw", m)
    );
    return s;
  }

  function highlightJson(code) {
    let s = escapeHtml(code);
    s = s.replace(/"([^"\\]|\\.)*"(?=\s*:)/g, (m) => span("key", m));
    s = s.replace(/"([^"\\]|\\.)*"/g, (m) => span("str", m));
    s = s.replace(/\b(true|false|null)\b/g, (m) => span("kw", m));
    s = s.replace(/\b-?\d+\.?\d*\b/g, (m) => span("num", m));
    return s;
  }

  function highlightCode(code, lang) {
    if (lang === "json") return highlightJson(code);
    if (lang === "markdown") return escapeHtml(code);
    return highlightGeneric(code);
  }

  function inlineFmt(s) {
    let h = escapeHtml(s);
    h = h.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="md-a">$1</a>');
    h = h.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    h = h.replace(/`([^`]+)`/g, '<code class="md-inline">$1</code>');
    return h;
  }

  function renderMarkdown(text) {
    const parts = [];
    const lines = String(text || "").split("\n");
    let i = 0;
    let inCode = false;
    let codeLang = "";
    let codeBuf = [];
    let tableRows = [];

    function flushTable() {
      if (tableRows.length < 2) {
        if (tableRows.length) parts.push('<p class="md-p">' + inlineFmt(tableRows.join(" ")) + "</p>");
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
      const fence = line.match(/^```(\w+)?\s*$/);
      if (fence) {
        if (inCode) {
          const lang = codeLang || "plaintext";
          parts.push(
            '<div class="md-code-block"><div class="md-code-lang">' +
              escapeHtml(lang) +
              '</div><pre class="md-code"><code>' +
              highlightCode(codeBuf.join("\n"), lang) +
              "</code></pre></div>"
          );
          codeBuf = [];
          codeLang = "";
          inCode = false;
        } else {
          inCode = true;
          codeLang = fence[1] || "";
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

      const bq = line.match(/^>\s?(.*)$/);
      if (bq) {
        parts.push('<blockquote class="md-bq">' + inlineFmt(bq[1]) + "</blockquote>");
        i++;
        continue;
      }
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
      if (/^---+$/.test(line.trim())) {
        parts.push('<hr class="md-hr">');
        i++;
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
      const lang = codeLang || "plaintext";
      parts.push(
        '<div class="md-code-block"><pre class="md-code"><code>' +
          highlightCode(codeBuf.join("\n"), lang) +
          "</code></pre></div>"
      );
    }
    if (tableRows.length) flushTable();
    return parts.join("");
  }

  const PREVIEW_CSS =
    ":root{--bg:#0b0d11;--surface:#12141a;--surface-2:#1a1d26;--border:#262a33;--text:#e8eaee;" +
    "--text-secondary:#d1d5db;--muted:#8a8f9a;--accent:#6c8cff;--code-bg:#080a0e;--inline-code:#c4b5fd;" +
    "--mono:'JetBrains Mono','Cascadia Code',Consolas,monospace;--font:system-ui,sans-serif}" +
    "body{margin:0;padding:16px 20px 28px;background:var(--bg);color:var(--text);" +
    "font-family:var(--font);font-size:14px;line-height:1.6}" +
    ".md-prose{max-width:820px;margin:0 auto}" +
    ".md-h1,.md-h2,.md-h3{margin:16px 0 8px;font-weight:600;line-height:1.3}" +
    ".md-h1{font-size:1.5rem;border-bottom:1px solid var(--border);padding-bottom:8px}" +
    ".md-h2{font-size:1.2rem}.md-h3{font-size:1.05rem;color:var(--text-secondary)}" +
    ".md-p{margin:0 0 10px}.md-ul,.md-ol{margin:8px 0 12px;padding-left:1.4rem}" +
    ".md-bq{margin:10px 0;padding:8px 12px;border-left:3px solid var(--accent);" +
    "background:var(--surface);color:var(--text-secondary)}" +
    ".md-hr{border:none;border-top:1px solid var(--border);margin:16px 0}" +
    ".md-a{color:var(--accent);text-decoration:none}.md-a:hover{text-decoration:underline}" +
    ".md-inline{font-family:var(--mono);font-size:.9em;background:var(--surface-2);" +
    "border:1px solid var(--border);padding:1px 5px;border-radius:4px;color:var(--inline-code)}" +
    ".md-table{width:100%;border-collapse:collapse;margin:12px 0;font-size:13px;border:1px solid var(--border)}" +
    ".md-table th,.md-table td{padding:8px 10px;border-bottom:1px solid var(--border);text-align:left}" +
    ".md-table th{background:var(--surface-2);color:var(--muted);font-size:12px}" +
    ".md-code-block{margin:12px 0;border:1px solid var(--border);border-radius:8px;overflow:hidden}" +
    ".md-code-lang{padding:4px 10px;font-size:11px;color:var(--muted);background:var(--surface-2);" +
    "border-bottom:1px solid var(--border);font-family:var(--mono)}" +
    ".md-code{margin:0;padding:12px 14px;background:var(--code-bg);font-family:var(--mono);" +
    "font-size:12px;line-height:1.55;overflow-x:auto;white-space:pre}" +
    ".code-shell{border:1px solid var(--border);border-radius:8px;overflow:hidden}" +
    ".code-meta{padding:6px 12px;font-size:11px;color:var(--muted);background:var(--surface-2);" +
    "border-bottom:1px solid var(--border);font-family:var(--mono)}" +
    ".code-scroll{margin:0;padding:12px 0;background:var(--code-bg);overflow-x:auto}" +
    ".code-table{border-collapse:collapse;width:100%;font-family:var(--mono);font-size:12px;line-height:1.55}" +
    ".code-table td{vertical-align:top;padding:0}" +
    ".code-ln{width:42px;padding:0 10px 0 14px;text-align:right;color:var(--muted);" +
    "user-select:none;border-right:1px solid var(--border)}" +
    ".code-lc{padding:0 14px 0 12px;white-space:pre}" +
    ".tok-kw{color:#c792ea}.tok-str{color:#c3e88d}.tok-cmt{color:#637777;font-style:italic}" +
    ".tok-num{color:#f78c6c}.tok-key{color:#82aaff}";

  function buildCodePreview(path, content, lang) {
    const lines = String(content || "").split("\n");
    const rows = lines
      .map((line, idx) => {
        const hl = highlightCode(line, lang);
        return (
          "<tr><td class=\"code-ln\">" +
          (idx + 1) +
          '</td><td class="code-lc">' +
          (hl || " ") +
          "</td></tr>"
        );
      })
      .join("");
    return (
      '<div class="code-shell"><div class="code-meta">' +
      escapeHtml(lang) +
      " · " +
      lines.length +
      " lines · " +
      escapeHtml(path) +
      '</div><div class="code-scroll"><table class="code-table"><tbody>' +
      rows +
      "</tbody></table></div></div>"
    );
  }

  function buildPreviewDocument(path, content) {
    const text = String(content ?? "");
    if (isHtmlPath(path)) return text;
    let body;
    if (isMarkdownPath(path)) {
      body = '<article class="md-prose">' + renderMarkdown(text) + "</article>";
    } else {
      const lang = extLang(path);
      body = buildCodePreview(path, text, lang);
    }
    return (
      "<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"UTF-8\">" +
      "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">" +
      "<style>" +
      PREVIEW_CSS +
      "</style></head><body>" +
      body +
      "</body></html>"
    );
  }

  window.__merisBuildFilePreview = buildPreviewDocument;
  window.__merisRenderMarkdown = renderMarkdown;
  window.__merisExtLang = extLang;
})();
