//! `meris-rs run` direct native entry parsing.

use crate::review::load_review_task;
use std::path::PathBuf;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DirectRunArgs {
    pub mode: String,
    pub task: String,
    pub workspace: PathBuf,
    pub session_id: Option<String>,
    pub event_stream: Option<PathBuf>,
    pub save_plan: bool,
    pub plan_output: Option<String>,
    pub max_turns: u32,
    pub resume: bool,
}

fn blocks_delegate_flag(flag: &str) -> bool {
    flag == "--ratchet"
        || flag == "--require-approval"
        || flag == "--json"
        || flag.starts_with("--provider")
}

pub fn parse_direct_run_args(args: &[String]) -> Option<DirectRunArgs> {
    if args.is_empty() {
        return None;
    }
    let mode = args[0].clone();
    if mode == "review" {
        return parse_direct_review_args(args);
    }
    if !matches!(mode.as_str(), "ask" | "plan" | "run") {
        return None;
    }
    for flag in args.iter().skip(1) {
        if blocks_delegate_flag(flag) {
            return None;
        }
    }

    let mut workspace = std::env::current_dir().ok()?;
    let mut task: Option<String> = None;
    let mut session_id = None;
    let mut event_stream = None;
    let mut save_plan = mode == "plan";
    let mut plan_output: Option<String> = None;
    let mut no_save = false;
    let mut max_turns = 30u32;
    let mut resume = false;
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--cwd" | "-C" => {
                i += 1;
                workspace = PathBuf::from(args.get(i)?);
                i += 1;
            }
            "--session-id" => {
                i += 1;
                session_id = Some(args.get(i)?.clone());
                i += 1;
            }
            "--event-stream" => {
                i += 1;
                event_stream = Some(PathBuf::from(args.get(i)?));
                i += 1;
            }
            "--out" | "-o" => {
                i += 1;
                plan_output = Some(args.get(i)?.clone());
                i += 1;
            }
            "--no-save" => {
                no_save = true;
                i += 1;
            }
            "--resume" => {
                resume = true;
                i += 1;
            }
            "--max-turns" => {
                i += 1;
                max_turns = args.get(i)?.parse().ok()?;
                i += 1;
            }
            s if s.starts_with('-') => return None,
            s => {
                if task.is_some() {
                    return None;
                }
                task = Some(s.to_string());
                i += 1;
            }
        }
    }
    let task = task?;
    if resume && session_id.is_none() {
        return None;
    }
    if no_save {
        save_plan = false;
    } else if save_plan && plan_output.is_none() {
        plan_output = Some("__default__".into());
    }
    Some(DirectRunArgs {
        mode,
        task,
        workspace,
        session_id,
        event_stream,
        save_plan,
        plan_output,
        max_turns,
        resume,
    })
}

fn parse_direct_review_args(args: &[String]) -> Option<DirectRunArgs> {
    for flag in args.iter().skip(1) {
        if blocks_delegate_flag(flag) || flag == "--resume" {
            return None;
        }
    }
    let mut workspace = std::env::current_dir().ok()?;
    let mut staged = false;
    let mut event_stream = None;
    let mut max_turns = 12u32;
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--cwd" | "-C" => {
                i += 1;
                workspace = PathBuf::from(args.get(i)?);
                i += 1;
            }
            "--staged" => {
                staged = true;
                i += 1;
            }
            "--event-stream" => {
                i += 1;
                event_stream = Some(PathBuf::from(args.get(i)?));
                i += 1;
            }
            "--max-turns" => {
                i += 1;
                max_turns = args.get(i)?.parse().ok()?;
                i += 1;
            }
            s if s.starts_with('-') => return None,
            _ => return None,
        }
    }
    let task = load_review_task(&workspace, staged)?;
    Some(DirectRunArgs {
        mode: "review".into(),
        task,
        workspace,
        session_id: None,
        event_stream,
        save_plan: false,
        plan_output: None,
        max_turns,
        resume: false,
    })
}

pub fn native_loop_enabled_for_run_entry() -> bool {
    if native_loop_disabled() || native_disabled() {
        return false;
    }
    match env_tri("NATIVE_LOOP") {
        Some(true) => true,
        Some(false) => false,
        None => true,
    }
}

pub fn should_inject_native_loop_auto() -> bool {
    if std::env::var("MERIS_NATIVE_LOOP").is_ok() {
        return false;
    }
    !native_disabled()
}

fn env_tri(name: &str) -> Option<bool> {
    let key = format!("MERIS_{name}");
    match std::env::var(&key)
        .ok()
        .as_deref()
        .map(|s| s.trim().to_lowercase())
    {
        Some(ref s) if s == "0" || s == "false" || s == "no" => Some(false),
        Some(ref s) if s == "1" || s == "true" || s == "yes" => Some(true),
        _ => None,
    }
}

fn native_disabled() -> bool {
    env_tri("NATIVE") == Some(false)
}

fn native_loop_disabled() -> bool {
    env_tri("NATIVE_LOOP") == Some(false)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_ask_with_max_turns() {
        let args = vec![
            "ask".into(),
            "hello".into(),
            "--max-turns".into(),
            "5".into(),
        ];
        let p = parse_direct_run_args(&args).expect("parsed");
        assert_eq!(p.mode, "ask");
        assert_eq!(p.task, "hello");
        assert_eq!(p.max_turns, 5);
        assert!(!p.resume);
    }

    #[test]
    fn parse_run_resume_requires_session() {
        let args = vec!["run".into(), "task".into(), "--resume".into()];
        assert!(parse_direct_run_args(&args).is_none());
    }

    #[test]
    fn parse_run_resume_with_session() {
        let args = vec![
            "run".into(),
            "ignored".into(),
            "--resume".into(),
            "--session-id".into(),
            "abc123".into(),
        ];
        let p = parse_direct_run_args(&args).expect("parsed");
        assert!(p.resume);
        assert_eq!(p.session_id.as_deref(), Some("abc123"));
    }

    #[test]
    fn ratchet_flag_delegates() {
        let args = vec!["ask".into(), "x".into(), "--ratchet".into()];
        assert!(parse_direct_run_args(&args).is_none());
    }
}
