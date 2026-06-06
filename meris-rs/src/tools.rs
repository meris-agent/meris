//! Builtin tools — parity with meris.tools.builtin (P5-3).

use crate::sandbox::{check_bash_sandbox, get_bash_timeout, get_sandbox_mode, run_bash_in_workspace};
use crate::settings::load_settings;
use globwalk::GlobWalkerBuilder;
use regex::Regex;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

const MAX_GLOB_MATCHES: usize = 50;
const MAX_GREP_HITS: usize = 40;
const MAX_GREP_FILE_BYTES: u64 = 500_000;
const MAX_GREP_LINE_CHARS: usize = 200;
const DEFAULT_READ_LIMIT: usize = 200;

pub fn resolve_in_workspace(workspace: &Path, rel: &str) -> Result<PathBuf, String> {
    let ws = workspace
        .canonicalize()
        .map_err(|e| format!("workspace: {e}"))?;
    let rel = rel.trim().replace('\\', "/");
    if rel.is_empty() {
        return Err("empty path".into());
    }
    let p = ws
        .join(&rel)
        .canonicalize()
        .map_err(|e| format!("{rel}: {e}"))?;
    if !p.starts_with(&ws) {
        return Err(format!("path escapes workspace: {rel}"));
    }
    Ok(p)
}

pub fn tool_read_file(workspace: &Path, args: &Value) -> String {
    let path = match args.get("path").and_then(|v| v.as_str()) {
        Some(p) => p,
        None => return "Error: missing path".into(),
    };
    let resolved = match resolve_in_workspace(workspace, path) {
        Ok(p) => p,
        Err(e) => return format!("Error: {e}"),
    };
    if !resolved.is_file() {
        return format!("Error: not a file: {path}");
    }
    let text = match fs::read_to_string(&resolved) {
        Ok(t) => t,
        Err(e) => return format!("Error: {e}"),
    };
    let offset = args
        .get("offset")
        .and_then(|v| v.as_u64().or_else(|| v.as_i64().map(|i| i as u64)))
        .unwrap_or(1)
        .max(1) as usize;
    let limit = args
        .get("limit")
        .and_then(|v| v.as_u64().or_else(|| v.as_i64().map(|i| i as u64)))
        .unwrap_or(DEFAULT_READ_LIMIT as u64) as usize;
    let lines: Vec<&str> = text.lines().collect();
    let start = offset.saturating_sub(1);
    if start >= lines.len() {
        return "(empty file)".into();
    }
    let end = (start + limit).min(lines.len());
    let mut out = String::new();
    for (i, ln) in lines[start..end].iter().enumerate() {
        out.push_str(&format!("{:4}| {ln}\n", start + i + 1));
    }
    let trimmed = out.trim_end().to_string();
    if trimmed.is_empty() {
        "(empty file)".into()
    } else {
        trimmed
    }
}

pub fn tool_glob(workspace: &Path, args: &Value) -> String {
    let pattern = match args.get("pattern").and_then(|v| v.as_str()) {
        Some(p) => p.trim(),
        None => return "Error: missing pattern".into(),
    };
    if pattern.is_empty() {
        return "Error: empty pattern".into();
    }
    let ws = match workspace.canonicalize() {
        Ok(p) => p,
        Err(e) => return format!("Error: {e}"),
    };
    let pattern_norm = pattern.replace('\\', "/");
    let walker = match GlobWalkerBuilder::from_patterns(&ws, &[pattern_norm.as_str()])
        .max_depth(100)
        .build()
    {
        Ok(w) => w,
        Err(e) => return format!("Error: {e}"),
    };
    let mut rels: Vec<String> = Vec::new();
    for entry in walker.flatten().take(MAX_GLOB_MATCHES) {
        let p = entry.path();
        if let Ok(r) = p.strip_prefix(&ws) {
            rels.push(r.to_string_lossy().replace('\\', "/"));
        }
    }
    rels.sort();
    rels.dedup();
    if rels.is_empty() {
        "(no matches)".into()
    } else {
        rels.join("\n")
    }
}

fn grep_file(
    workspace: &Path,
    fp: &Path,
    rx: &Regex,
    hits: &mut Vec<String>,
) -> bool {
    if !fp.is_file() {
        return false;
    }
    let meta = match fs::metadata(fp) {
        Ok(m) => m,
        Err(_) => return false,
    };
    if meta.len() > MAX_GREP_FILE_BYTES {
        return false;
    }
    let text = match fs::read_to_string(fp) {
        Ok(t) => t,
        Err(_) => return false,
    };
    let rel = fp
        .strip_prefix(workspace)
        .unwrap_or(fp)
        .to_string_lossy()
        .replace('\\', "/");
    for (i, line) in text.lines().enumerate() {
        if rx.is_match(line) {
            let snippet: String = line.chars().take(MAX_GREP_LINE_CHARS).collect();
            hits.push(format!("{}:{}:{}", rel, i + 1, snippet));
            if hits.len() >= MAX_GREP_HITS {
                return true;
            }
        }
    }
    false
}

pub fn tool_grep(workspace: &Path, args: &Value) -> String {
    let pattern = match args.get("pattern").and_then(|v| v.as_str()) {
        Some(p) => p,
        None => return "Error: missing pattern".into(),
    };
    let rx = match Regex::new(pattern) {
        Ok(r) => r,
        Err(e) => return format!("Error: invalid regex: {e}"),
    };
    let path = args.get("path").and_then(|v| v.as_str()).unwrap_or(".");
    let root = match resolve_in_workspace(workspace, path) {
        Ok(p) => p,
        Err(e) => return format!("Error: {e}"),
    };
    let ws = match workspace.canonicalize() {
        Ok(p) => p,
        Err(e) => return format!("Error: {e}"),
    };
    let mut hits: Vec<String> = Vec::new();
    if root.is_dir() {
        if let Ok(walker) = GlobWalkerBuilder::from_patterns(&root, &["**/*"]).max_depth(50).build()
        {
            for entry in walker.flatten() {
                if grep_file(&ws, entry.path(), &rx, &mut hits) {
                    break;
                }
            }
        }
    } else if grep_file(&ws, &root, &rx, &mut hits) {
        // single file
    }
    if hits.is_empty() {
        "(no matches)".into()
    } else {
        hits.join("\n")
    }
}

pub fn tool_write_file(workspace: &Path, args: &Value) -> String {
    let path = match args.get("path").and_then(|v| v.as_str()) {
        Some(p) => p,
        None => return "Error: missing path".into(),
    };
    let content = match args.get("content").and_then(|v| v.as_str()) {
        Some(c) => c,
        None => return "Error: missing content".into(),
    };
    let resolved = match resolve_in_workspace(workspace, path) {
        Ok(p) => p,
        Err(e) => return format!("Error: {e}"),
    };
    if let Some(parent) = resolved.parent() {
        if let Err(e) = fs::create_dir_all(parent) {
            return format!("Error: {e}");
        }
    }
    match fs::write(&resolved, content) {
        Ok(()) => format!("Wrote {path} ({} bytes)", content.len()),
        Err(e) => format!("Error: {e}"),
    }
}

pub fn tool_edit_file(workspace: &Path, args: &Value) -> String {
    let path = match args.get("path").and_then(|v| v.as_str()) {
        Some(p) => p,
        None => return "Error: missing path".into(),
    };
    let old = match args.get("old_string").and_then(|v| v.as_str()) {
        Some(s) => s,
        None => return "Error: missing old_string".into(),
    };
    let new = match args.get("new_string").and_then(|v| v.as_str()) {
        Some(s) => s,
        None => return "Error: missing new_string".into(),
    };
    let resolved = match resolve_in_workspace(workspace, path) {
        Ok(p) => p,
        Err(e) => return format!("Error: {e}"),
    };
    if !resolved.is_file() {
        return format!("Error: not a file: {path}");
    }
    let text = match fs::read_to_string(&resolved) {
        Ok(t) => t,
        Err(e) => return format!("Error: {e}"),
    };
    if !text.contains(old) {
        return "Error: old_string not found in file".into();
    }
    let updated = text.replacen(old, new, 1);
    match fs::write(&resolved, updated) {
        Ok(()) => format!("Edited {path}"),
        Err(e) => format!("Error: {e}"),
    }
}

pub fn tool_bash(
    workspace: &Path,
    args: &Value,
    settings: &HashMap<String, Value>,
) -> String {
    let command = match args.get("command").and_then(|v| v.as_str()) {
        Some(c) => c,
        None => return "Error: missing command".into(),
    };
    let mode = get_sandbox_mode(settings);
    if let Some(v) = check_bash_sandbox(command, &mode) {
        if v.blocked {
            return v.message.clone();
        }
    }
    let timeout = get_bash_timeout(settings);
    match run_bash_in_workspace(workspace, command, timeout, settings) {
        Ok((code, out)) => {
            let text = out.trim();
            if text.is_empty() {
                format!("exit={code}")
            } else {
                format!("exit={code}\n{text}")
            }
        }
        Err(e) => format!("exit=1\n{e}"),
    }
}

fn fn_schema(name: &str, description: &str, parameters: Value) -> Value {
    json!({
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        }
    })
}

pub fn tool_schemas(read_only: bool) -> Vec<Value> {
    let mut schemas = vec![
        fn_schema(
            "read_file",
            "Read a file with 1-based line numbers.",
            json!({
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "offset": {"type": "integer"},
                    "limit": {"type": "integer"},
                },
                "required": ["path"],
            }),
        ),
        fn_schema(
            "glob",
            "Find files by glob pattern relative to repo root.",
            json!({
                "type": "object",
                "properties": {"pattern": {"type": "string"}},
                "required": ["pattern"],
            }),
        ),
        fn_schema(
            "grep",
            "Regex search in files. Optional path (file or dir).",
            json!({
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string"},
                },
                "required": ["pattern"],
            }),
        ),
    ];
    if !read_only {
        schemas.push(fn_schema(
            "write_file",
            "Create or overwrite a file.",
            json!({
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            }),
        ));
        schemas.push(fn_schema(
            "edit_file",
            "Replace exactly one occurrence of old_string with new_string.",
            json!({
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_string": {"type": "string"},
                    "new_string": {"type": "string"},
                },
                "required": ["path", "old_string", "new_string"],
            }),
        ));
        schemas.push(fn_schema(
            "bash",
            "Run shell command in repo root. Prefer rg/grep/test over cat.",
            json!({
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            }),
        ));
    }
    schemas
}

pub fn tool_schemas_json(read_only: bool) -> String {
    serde_json::to_string_pretty(&tool_schemas(read_only)).unwrap_or_else(|_| "[]".into())
}

pub fn run_builtin_tool(
    workspace: &Path,
    tool: &str,
    args: &Value,
    settings: &HashMap<String, Value>,
) -> String {
    match tool {
        "read_file" => tool_read_file(workspace, args),
        "glob" => tool_glob(workspace, args),
        "grep" => tool_grep(workspace, args),
        "write_file" => tool_write_file(workspace, args),
        "edit_file" => tool_edit_file(workspace, args),
        "bash" => tool_bash(workspace, args, settings),
        _ => format!("Error: unknown tool {tool}"),
    }
}

pub fn tool_needs_approval(tool: &str) -> bool {
    !READONLY_TOOLS.contains(&tool)
}

pub fn run_readonly_tool(workspace: &Path, tool: &str, args: &Value) -> String {
    let settings = load_settings(workspace);
    run_builtin_tool(workspace, tool, args, &settings)
}

pub const READONLY_TOOLS: &[&str] = &["read_file", "glob", "grep"];
pub const BUILTIN_TOOL_NAMES: &[&str] = &[
    "read_file",
    "glob",
    "grep",
    "write_file",
    "edit_file",
    "bash",
];
pub const EDIT_TOOLS: &[&str] = &["write_file", "edit_file"];

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use tempfile::TempDir;

    #[test]
    fn read_file_numbered() {
        let dir = TempDir::new().unwrap();
        let f = dir.path().join("a.txt");
        fs::write(&f, "one\ntwo\nthree\n").unwrap();
        let out = tool_read_file(dir.path(), &json!({"path": "a.txt", "limit": 2}));
        assert!(out.contains("   1| one"));
        assert!(out.contains("   2| two"));
    }

    #[test]
    fn glob_finds_py() {
        let dir = TempDir::new().unwrap();
        fs::write(dir.path().join("hello.py"), "x").unwrap();
        let out = tool_glob(dir.path(), &json!({"pattern": "*.py"}));
        assert!(out.contains("hello.py"));
    }

    #[test]
    fn grep_finds_pattern() {
        let dir = TempDir::new().unwrap();
        fs::write(dir.path().join("hello.py"), "print('hello')\n").unwrap();
        let out = tool_grep(dir.path(), &json!({"pattern": "hello", "path": "."}));
        assert!(out.contains("hello.py"));
    }

    #[test]
    fn blocks_path_escape() {
        let dir = TempDir::new().unwrap();
        let err = resolve_in_workspace(dir.path(), "../etc/passwd").unwrap_err();
        assert!(err.contains("escapes"));
    }

    #[test]
    fn write_and_edit_file() {
        let dir = TempDir::new().unwrap();
        let out = tool_write_file(
            dir.path(),
            &json!({"path": "sub/a.txt", "content": "hello world"}),
        );
        assert!(out.contains("Wrote sub/a.txt"));
        let out = tool_edit_file(
            dir.path(),
            &json!({"path": "sub/a.txt", "old_string": "world", "new_string": "meris"}),
        );
        assert!(out.contains("Edited sub/a.txt"));
        let text = fs::read_to_string(dir.path().join("sub/a.txt")).unwrap();
        assert_eq!(text, "hello meris");
    }

    #[test]
    fn schemas_match_readonly_count() {
        assert_eq!(tool_schemas(true).len(), 3);
        assert_eq!(tool_schemas(false).len(), 6);
    }

    #[test]
    fn schema_has_function_wrapper() {
        let s = &tool_schemas(true)[0];
        assert_eq!(s["type"], "function");
        assert_eq!(s["function"]["name"], "read_file");
    }
}
