//! Plan mode output — parity with meris.harness.plan (P5-4 M4).

use chrono::Utc;
use serde_json::Value;
use std::fs;
use std::path::{Path, PathBuf};

pub fn default_plan_path(workspace: &Path) -> PathBuf {
    workspace.join(".meris").join("plan").join("tasks.md")
}

pub fn resolve_plan_path(workspace: &Path, out: Option<&str>) -> PathBuf {
    match out {
        None | Some("") | Some("__default__") => default_plan_path(workspace),
        Some(rel) => {
            let p = PathBuf::from(rel);
            if p.is_absolute() {
                p
            } else {
                workspace.join(p)
            }
        }
    }
}

pub fn extract_last_assistant_text(messages: &[Value]) -> Option<String> {
    for msg in messages.iter().rev() {
        if msg.get("role").and_then(|r| r.as_str()) != Some("assistant") {
            continue;
        }
        let text = msg.get("content").and_then(|c| c.as_str()).unwrap_or("").trim();
        if !text.is_empty() {
            return Some(text.to_string());
        }
    }
    None
}

pub fn save_plan(workspace: &Path, content: &str, out: Option<&str>) -> Result<PathBuf, String> {
    let path = resolve_plan_path(workspace, out);
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let ts = Utc::now().format("%Y-%m-%d %H:%M UTC");
    let body = content.trim();
    let text = if body.starts_with('#') {
        format!("{body}\n")
    } else {
        format!("# Task plan ({ts})\n\n{body}\n")
    };
    fs::write(&path, text).map_err(|e| e.to_string())?;
    Ok(path)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use tempfile::TempDir;

    #[test]
    fn saves_plan_with_header() {
        let dir = TempDir::new().unwrap();
        let path = save_plan(dir.path(), "step one", None).unwrap();
        let text = fs::read_to_string(path).unwrap();
        assert!(text.contains("Task plan"));
        assert!(text.contains("step one"));
    }

    #[test]
    fn extracts_assistant() {
        let msgs = vec![
            json!({"role": "user", "content": "hi"}),
            json!({"role": "assistant", "content": "plan here"}),
        ];
        assert_eq!(extract_last_assistant_text(&msgs).as_deref(), Some("plan here"));
    }
}
