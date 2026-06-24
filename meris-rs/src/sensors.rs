//! Sensor bridge — postEdit commands + Python onComplete delegation (P5-4 M2).

use regex::Regex;
use serde_json::Value;
use std::collections::HashMap;
use std::path::Path;
use std::process::{Command, Stdio};
use std::time::Duration;

const POST_EDIT_TIMEOUT: u64 = 120;
const ON_COMPLETE_TIMEOUT: u64 = 300;

pub fn post_edit_commands(settings: &HashMap<String, Value>) -> Vec<String> {
    settings
        .get("sensors")
        .and_then(|s| s.get("postEdit"))
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|x| x.as_str().map(str::trim).filter(|s| !s.is_empty()))
                .map(str::to_string)
                .collect()
        })
        .unwrap_or_default()
}

pub fn on_complete_enabled(settings: &HashMap<String, Value>) -> bool {
    settings
        .get("sensors")
        .and_then(|s| s.get("onComplete"))
        .and_then(|v| v.as_bool())
        .unwrap_or(true)
}

fn format_failure(output: &str) -> String {
    let mut lines = vec![output.trim().chars().take(1800).collect::<String>()];
    let lower = output.to_lowercase();
    let mut hints: Vec<&str> = Vec::new();
    if lower.contains("import:forge") || lower.contains("forge/") {
        hints.push("Run: meris harness check — remove forge/ imports; use from meris....");
    }
    if lower.contains("paths:readme") || lower.contains("meris/readme") {
        hints.push("Use README.md at repo root — read .meris/rules/paths.md");
    }
    if lower.contains("pytest") && lower.contains("exit=") {
        hints.push(r#"Fix failing tests: pytest tests/ -m "not integration" -q"#);
    }
    if lower.contains("harness check") || lower.contains("meris harness") {
        hints.push("Run: meris harness check — fix static harness violations");
    }
    if !hints.is_empty() {
        lines.push("hints:".into());
        for h in hints {
            lines.push(format!("- {h}"));
        }
    }
    lines.join("\n")
}

pub fn run_shell_commands(
    workspace: &Path,
    cmds: &[String],
    timeout_secs: u64,
) -> (bool, String) {
    if cmds.is_empty() {
        return (true, "(no commands)".into());
    }
    let ws = match workspace.canonicalize() {
        Ok(p) => p,
        Err(e) => return (false, format!("workspace: {e}")),
    };
    let mut outputs: Vec<String> = Vec::new();
    for cmd in cmds {
        let mut command = Command::new(if cfg!(windows) { "cmd" } else { "sh" });
        if cfg!(windows) {
            command.arg("/C").arg(cmd);
        } else {
            command.arg("-c").arg(cmd);
        }
        let child = command
            .current_dir(&ws)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn();
        let Ok(mut proc) = child else {
            outputs.push(format!("$ {cmd}\nexit=1\n(spawn failed)"));
            return (false, outputs.join("\n\n"));
        };
        let deadline = Duration::from_secs(timeout_secs);
        let start = std::time::Instant::now();
        loop {
            if let Ok(Some(status)) = proc.try_wait() {
                let mut out = String::new();
                if let Some(mut stdout) = proc.stdout.take() {
                    let _ = std::io::Read::read_to_string(&mut stdout, &mut out);
                }
                if let Some(mut stderr) = proc.stderr.take() {
                    let mut err = String::new();
                    let _ = std::io::Read::read_to_string(&mut stderr, &mut err);
                    if !err.is_empty() {
                        out.push_str(&err);
                    }
                }
                let code = status.code().unwrap_or(1);
                let snippet: String = out.chars().rev().take(2000).collect::<String>().chars().rev().collect();
                outputs.push(format!("$ {cmd}\nexit={code}\n{snippet}"));
                if code != 0 {
                    return (false, format_failure(&outputs.join("\n\n")));
                }
                break;
            }
            if start.elapsed() > deadline {
                let _ = proc.kill();
                outputs.push(format!("$ {cmd}\nexit=1\n(timeout after {timeout_secs}s)"));
                return (false, format_failure(&outputs.join("\n\n")));
            }
            std::thread::sleep(Duration::from_millis(50));
        }
    }
    (true, outputs.join("\n\n"))
}

pub fn run_post_edit_sensors(
    workspace: &Path,
    settings: &HashMap<String, Value>,
) -> (bool, String) {
    let cmds = post_edit_commands(settings);
    if cmds.is_empty() {
        return (true, String::new());
    }
    run_shell_commands(workspace, &cmds, POST_EDIT_TIMEOUT)
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

fn parse_sensor_json(stdout: &str) -> Option<(bool, String)> {
    let v: Value = serde_json::from_str(stdout.trim()).ok()?;
    let ok = v.get("ok").and_then(|b| b.as_bool())?;
    let output = v
        .get("output")
        .and_then(|o| o.as_str())
        .unwrap_or("")
        .to_string();
    Some((ok, output))
}

/// Run DoD / onComplete via Python `meris harness on-complete --json`.
pub fn run_on_complete_sensors(workspace: &Path) -> Option<(bool, String)> {
    let meris = which_meris()?;
    let ws = workspace.canonicalize().ok()?;
    let output = Command::new(&meris)
        .args([
            "harness",
            "on-complete",
            "--cwd",
            ws.to_str()?,
            "--json",
        ])
        .output()
        .ok()?;
    if !output.status.success() && output.stdout.is_empty() {
        return None;
    }
    parse_sensor_json(&String::from_utf8_lossy(&output.stdout))
}

/// Optional Python bridge for postEdit (used when settings empty but testing bridge).
pub fn run_post_edit_via_meris(workspace: &Path) -> Option<(bool, String)> {
    let meris = which_meris()?;
    let ws = workspace.canonicalize().ok()?;
    let output = Command::new(&meris)
        .args(["harness", "post-edit", "--cwd", ws.to_str()?, "--json"])
        .output()
        .ok()?;
    parse_sensor_json(&String::from_utf8_lossy(&output.stdout))
}

pub fn parse_dod_commands(agents_md: &str) -> Vec<String> {
    let section_re = Regex::new(r"(?i)##\s*(?:完成定义|Definition of Done)").unwrap();
    let Some(m) = section_re.find(agents_md) else {
        return vec![];
    };
    let rest = &agents_md[m.start()..];
    let next_re = Regex::new(r"\n##\s+").unwrap();
    let section = if let Some(n) = next_re.find(&rest[m.end() - m.start()..]) {
        &rest[..m.end() - m.start() + n.start()]
    } else {
        rest
    };
    let item_re = Regex::new(r"(?m)^[-*]\s*`([^`]+)`").unwrap();
    let mut cmds: Vec<String> = item_re
        .captures_iter(section)
        .filter_map(|c| c.get(1).map(|m| m.as_str().trim().to_string()))
        .collect();
    let fence_re = Regex::new(r"(?is)```(?:bash|sh|shell)?\s*\n(.*?)```").unwrap();
    if let Some(cap) = fence_re.captures(section) {
        for line in cap.get(1).unwrap().as_str().lines() {
            let line = line.trim();
            if !line.is_empty() && !line.starts_with('#') {
                cmds.push(line.to_string());
            }
        }
    }
    let mut seen = std::collections::HashSet::new();
    cmds.into_iter()
        .filter(|c| seen.insert(c.clone()))
        .take(8)
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_dod_from_sample() {
        let md = "## Definition of Done\n\n- `pytest tests/ -q`\n";
        let cmds = parse_dod_commands(md);
        assert_eq!(cmds, vec!["pytest tests/ -q"]);
    }

    #[test]
    fn post_edit_empty_ok() {
        let dir = tempfile::TempDir::new().unwrap();
        let settings = HashMap::new();
        let (ok, out) = run_post_edit_sensors(dir.path(), &settings);
        assert!(ok);
        assert!(out.is_empty());
    }
}
