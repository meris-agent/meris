//! Permission checks — parity with meris.harness.permissions.

use regex::Regex;
use serde_json::Value;
use std::collections::HashMap;

fn tool_category(tool_name: &str) -> &'static str {
    if tool_name.starts_with("mcp_") {
        return "MCP";
    }
    match tool_name {
        "read_file" | "load_skill" | "subagent_run" | "fetch_url" | "lint_file" => "Read",
        "write_file" => "Write",
        "edit_file" => "Edit",
        "glob" => "Glob",
        "grep" => "Grep",
        "git_status" | "git_diff" | "git_commit" => "Git",
        "bash" => "Bash",
        _ => "Unknown",
    }
}

fn match_bash_rule(rule: &str, command: &str) -> bool {
    if !rule.starts_with("Bash(") || !rule.ends_with(')') {
        return false;
    }
    let inner = &rule[5..rule.len() - 1];
    let pat = inner.replace('*', ".*");
    Regex::new(&pat).map(|re| re.is_match(command)).unwrap_or(false)
}

fn allowed_by_rule(rule: &str, tool_name: &str, args: &Value) -> bool {
    let rule = rule.trim();
    if rule.starts_with("Bash(") {
        if tool_name != "bash" {
            return false;
        }
        let cmd = args.get("command").and_then(|c| c.as_str()).unwrap_or("");
        return match_bash_rule(rule, cmd);
    }
    let cat = tool_category(tool_name);
    if rule == cat {
        return true;
    }
    rule == "MCP" && tool_name.starts_with("mcp_")
}

/// Return error message if blocked, else None.
pub fn check_tool_allowed(tool_name: &str, args: &Value, settings: &HashMap<String, Value>) -> Option<String> {
    let perms = settings.get("permissions").and_then(|p| p.as_object());
    let deny: Vec<&str> = perms
        .and_then(|p| p.get("deny"))
        .and_then(|d| d.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|v| v.as_str())
                .collect()
        })
        .unwrap_or_default();
    let allow: Vec<&str> = perms
        .and_then(|p| p.get("allow"))
        .and_then(|a| a.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|v| v.as_str())
                .collect()
        })
        .unwrap_or_default();

    if tool_name == "bash" {
        let cmd = args.get("command").and_then(|c| c.as_str()).unwrap_or("");
        for rule in &deny {
            if match_bash_rule(rule, cmd) {
                return Some(format!("Permission denied: {rule}"));
            }
        }
    }

    if !allow.is_empty() && !allow.iter().any(|r| allowed_by_rule(r, tool_name, args)) {
        let cat = tool_category(tool_name);
        return Some(format!(
            "Permission denied: {tool_name} ({cat}) not in allow list"
        ));
    }

    None
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn deny_bash_rm() {
        let mut settings = HashMap::new();
        settings.insert(
            "permissions".into(),
            json!({"deny": ["Bash(rm -rf*)"], "allow": ["Bash(pytest*)"]}),
        );
        let err = check_tool_allowed(
            "bash",
            &json!({"command": "rm -rf /tmp/x"}),
            &settings,
        );
        assert!(err.is_some());
    }

    #[test]
    fn allow_list_blocks_unknown() {
        let mut settings = HashMap::new();
        settings.insert("permissions".into(), json!({"allow": ["Read"]}));
        let err = check_tool_allowed("bash", &json!({"command": "echo hi"}), &settings);
        assert!(err.is_some());
        assert!(check_tool_allowed("read_file", &json!({}), &settings).is_none());
    }
}
