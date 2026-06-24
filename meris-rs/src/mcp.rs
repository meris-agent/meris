//! MCP bridge — JSONL protocol to `meris mcp serve` (P5-4 M3).

use serde_json::{json, Value};
use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::path::Path;
use std::process::{Child, ChildStdin, Command, Stdio};

pub fn has_mcp_servers(settings: &HashMap<String, Value>) -> bool {
    settings
        .get("mcpServers")
        .and_then(|v| v.as_object())
        .is_some_and(|o| !o.is_empty())
}

pub fn is_mcp_tool(name: &str) -> bool {
    name.starts_with("mcp_")
}

fn which_meris() -> Option<String> {
    if cfg!(windows) {
        Command::new("where")
            .arg("meris")
            .output()
            .ok()
            .and_then(|o| {
                String::from_utf8(o.stdout)
                    .ok()
                    .and_then(|s| s.lines().next().map(str::trim).map(String::from))
            })
    } else {
        Command::new("which")
            .arg("meris")
            .output()
            .ok()
            .and_then(|o| {
                String::from_utf8(o.stdout)
                    .ok()
                    .map(|s| s.trim().to_string())
                    .filter(|s| !s.is_empty())
            })
    }
}

pub struct McpBridge {
    child: Child,
    stdin: ChildStdin,
    reader: BufReader<std::process::ChildStdout>,
    pub notes: Vec<String>,
    read_only_flags: HashMap<String, bool>,
}

impl McpBridge {
    pub fn start(workspace: &Path) -> Option<Self> {
        let meris = which_meris()?;
        let ws = workspace.canonicalize().ok()?;
        let mut child = Command::new(&meris)
            .args(["mcp", "serve", "--cwd", ws.to_str()?])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .ok()?;
        let stdin = child.stdin.take()?;
        let stdout = child.stdout.take()?;
        let mut reader = BufReader::new(stdout);
        let mut ready_line = String::new();
        reader.read_line(&mut ready_line).ok()?;
        let ready: Value = serde_json::from_str(ready_line.trim()).ok()?;
        let notes: Vec<String> = ready
            .get("notes")
            .and_then(|n| n.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(str::to_string))
                    .collect()
            })
            .unwrap_or_default();
        Some(McpBridge {
            child,
            stdin,
            reader,
            notes,
            read_only_flags: HashMap::new(),
        })
    }

    fn request(&mut self, body: &Value) -> Option<Value> {
        let line = serde_json::to_string(body).ok()?;
        writeln!(self.stdin, "{line}").ok()?;
        self.stdin.flush().ok()?;
        let mut resp_line = String::new();
        self.reader.read_line(&mut resp_line).ok()?;
        serde_json::from_str(resp_line.trim()).ok()
    }

    pub fn load_schemas(&mut self, read_only: bool) -> Option<Vec<Value>> {
        let resp = self.request(&json!({"cmd": "schemas", "read_only": read_only}))?;
        if resp.get("ok").and_then(|v| v.as_bool()) != Some(true) {
            return None;
        }
        if let Some(obj) = resp.get("read_only").and_then(|v| v.as_object()) {
            self.read_only_flags = obj
                .iter()
                .filter_map(|(k, v)| v.as_bool().map(|b| (k.clone(), b)))
                .collect();
        }
        resp.get("schemas")
            .and_then(|s| s.as_array())
            .cloned()
    }

    pub fn call_tool(&mut self, tool: &str, args: &Value) -> Option<String> {
        let resp = self.request(&json!({"cmd": "call", "tool": tool, "args": args}))?;
        if resp.get("ok").and_then(|v| v.as_bool()) != Some(true) {
            return Some(
                resp.get("error")
                    .and_then(|e| e.as_str())
                    .unwrap_or("MCP call failed")
                    .to_string(),
            );
        }
        Some(
            resp.get("result")
                .and_then(|r| r.as_str())
                .unwrap_or("(empty)")
                .to_string(),
        )
    }

    pub fn tool_needs_approval(&self, tool: &str) -> bool {
        !self.read_only_flags.get(tool).copied().unwrap_or(true)
    }

    pub fn close(mut self) {
        let _ = self.request(&json!({"cmd": "close"}));
        let _ = self.child.wait();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn detects_mcp_tool_names() {
        assert!(is_mcp_tool("mcp_fs_read"));
        assert!(!is_mcp_tool("read_file"));
    }
}
