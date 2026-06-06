//! `meris-rs` — native CLI for harness primitives; `run` delegates to Python or native loop (M5).

use clap::{Parser, Subcommand};
use meris_rs::{
    chat_completions, check_bash_sandbox, check_tool_allowed, compress_messages, estimate_tokens,
    get_bash_timeout, get_sandbox_mode, load_settings, list_sessions, load_session, os_sandbox_probe_workspace,
    probe_provider, resolve_config, run_agent, run_bash_in_workspace, run_builtin_tool,
    tool_schemas_json, verdict_to_json, AgentConfig, BUILTIN_TOOL_NAMES, load_review_task,
};
use serde_json::{json, Value};
use std::fs;
use std::path::PathBuf;
use std::process::{Command, Stdio};

#[derive(Parser)]
#[command(name = "meris-rs", version, about = "Meris Agent native core")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Token utilities
    Context {
        #[command(subcommand)]
        action: ContextAction,
    },
    /// Check tool permission against workspace settings
    Permissions {
        #[arg(long)]
        workspace: PathBuf,
        #[arg(long)]
        tool: String,
        #[arg(long, default_value = "{}")]
        args: String,
    },
    /// Bash sandbox (cwd-locked run + policy check)
    Sandbox {
        #[command(subcommand)]
        action: SandboxAction,
    },
    /// OpenAI-compatible LLM chat (P5-2)
    Provider {
        #[command(subcommand)]
        action: ProviderAction,
    },
    /// Read-only tools (P5-3)
    Tools {
        #[command(subcommand)]
        action: ToolsAction,
    },
    /// Native agent loop (P5-4 M1 — read-only modes)
    Agent {
        #[command(subcommand)]
        action: AgentAction,
    },
    /// Print version and build info
    Version,
    /// Delegate to Python `meris` CLI (same argv minus `run`)
    Run {
        #[arg(trailing_var_arg = true, allow_hyphen_values = true)]
        meris_args: Vec<String>,
    },
}

#[derive(Subcommand)]
enum ContextAction {
    /// Estimate tokens for text
    Tokens { text: String },
    /// Compress messages JSON from stdin or file
    Compress {
        #[arg(long)]
        input: Option<PathBuf>,
        #[arg(long, default_value_t = 48)]
        max_messages: usize,
        #[arg(long)]
        max_tokens: Option<usize>,
        #[arg(long, default_value_t = 2000)]
        max_tool_tokens: usize,
    },
}

#[derive(Subcommand)]
enum SandboxAction {
    /// Scan bash command for sandbox issues (JSON to stdout)
    Check {
        #[arg(long)]
        workspace: PathBuf,
        #[arg(long)]
        command: String,
        #[arg(long)]
        mode: Option<String>,
    },
    /// Run shell command with cwd locked to workspace
    Run {
        #[arg(long)]
        workspace: PathBuf,
        #[arg(long)]
        timeout: Option<u64>,
        #[arg(trailing_var_arg = true, allow_hyphen_values = true)]
        cmd: Vec<String>,
    },
    /// Report OS sandbox / bubblewrap availability (JSON)
    Probe {
        #[arg(long)]
        workspace: PathBuf,
    },
}

#[derive(Subcommand)]
enum ProviderAction {
    /// Show resolved base URL / model / key presence (JSON)
    Probe {
        #[arg(long)]
        base_url: Option<String>,
        #[arg(long)]
        model: Option<String>,
    },
    /// Chat completions — messages JSON on stdin or --input
    Chat {
        #[arg(long)]
        base_url: Option<String>,
        #[arg(long)]
        model: Option<String>,
        #[arg(long)]
        input: Option<PathBuf>,
        #[arg(long, help = "Tools JSON array")]
        tools: Option<PathBuf>,
        #[arg(long, default_value_t = 120)]
        timeout: u64,
    },
}

#[derive(Subcommand)]
enum ToolsAction {
    /// List native read-only tools
    List,
    /// Export OpenAI function schemas (parity with Python ToolRegistry)
    Schemas {
        #[arg(long, help = "Exclude bash (ask/plan/review modes)")]
        read_only: bool,
    },
    /// Execute read_file | glob | grep | bash
    Run {
        #[arg(long)]
        workspace: PathBuf,
        #[arg(long)]
        tool: String,
        #[arg(long, default_value = "{}")]
        args: String,
    },
}

#[derive(Subcommand)]
enum AgentAction {
    /// Run agent loop (native tools + provider; read-only modes recommended)
    Run {
        #[arg(long)]
        workspace: PathBuf,
        #[arg(long)]
        task: String,
        #[arg(long, default_value = "ask")]
        mode: String,
        #[arg(long, default_value_t = 30)]
        max_turns: u32,
        #[arg(long)]
        session_id: Option<String>,
        #[arg(long)]
        resume: bool,
        #[arg(long, help = "Prompt stdin for non-readonly tools (@meris-approve protocol)")]
        require_approval: bool,
        #[arg(long, help = "Skip DoD sensors at end (run mode)")]
        no_sensor: bool,
        #[arg(long, help = "Append JSONL events (Phase E4)")]
        event_stream: Option<PathBuf>,
        #[arg(long, help = "Save plan markdown when mode=plan completes")]
        save_plan: bool,
        #[arg(long, help = "Plan output path (default .meris/plan/tasks.md)")]
        plan_output: Option<String>,
    },
    /// Session management (Python-compatible JSON)
    Session {
        #[command(subcommand)]
        action: SessionAction,
    },
}

#[derive(Subcommand)]
enum SessionAction {
    /// List sessions newest-first
    List {
        #[arg(long)]
        workspace: PathBuf,
    },
    /// Print one session as JSON
    Show {
        #[arg(long)]
        workspace: PathBuf,
        #[arg(long)]
        id: String,
    },
}

fn read_messages(input: Option<PathBuf>) -> Result<Vec<Value>, String> {
    let text = match input {
        Some(p) => fs::read_to_string(&p).map_err(|e| e.to_string())?,
        None => {
            let mut buf = String::new();
            std::io::Read::read_to_string(&mut std::io::stdin(), &mut buf)
                .map_err(|e| e.to_string())?;
            buf
        }
    };
    serde_json::from_str(&text).map_err(|e| e.to_string())
}

fn main() {
    let cli = Cli::parse();
    let code = match cli.command {
        Commands::Context { action } => match action {
            ContextAction::Tokens { text } => {
                println!("{}", estimate_tokens(&text));
                0
            }
            ContextAction::Compress {
                input,
                max_messages,
                max_tokens,
                max_tool_tokens,
            } => match read_messages(input) {
                Ok(msgs) => {
                    let out = compress_messages(&msgs, max_messages, max_tokens, max_tool_tokens);
                    println!(
                        "{}",
                        serde_json::to_string_pretty(&out).unwrap_or_else(|_| "[]".into())
                    );
                    0
                }
                Err(e) => {
                    eprintln!("Error: {e}");
                    1
                }
            },
        },
        Commands::Permissions {
            workspace,
            tool,
            args,
        } => {
            let settings = load_settings(&workspace);
            let args_v: Value = serde_json::from_str(&args).unwrap_or(Value::Object(Default::default()));
            match check_tool_allowed(&tool, &args_v, &settings) {
                Some(err) => {
                    eprintln!("{err}");
                    1
                }
                None => {
                    println!("ok");
                    0
                }
            }
        }
        Commands::Sandbox { action } => match action {
            SandboxAction::Check {
                workspace,
                command,
                mode,
            } => {
                let settings = load_settings(&workspace);
                let mode_s = mode
                    .map(|m| m.trim().to_lowercase())
                    .filter(|m| matches!(m.as_str(), "off" | "warn" | "strict"))
                    .unwrap_or_else(|| get_sandbox_mode(&settings));
                match check_bash_sandbox(&command, &mode_s) {
                    Some(v) => {
                        println!("{}", serde_json::to_string(&verdict_to_json(&v)).unwrap());
                        if v.blocked { 1 } else { 0 }
                    }
                    None => {
                        println!(r#"{{"ok":true,"mode":"{mode_s}"}}"#);
                        0
                    }
                }
            }
            SandboxAction::Run {
                workspace,
                timeout,
                cmd,
            } => {
                if cmd.is_empty() {
                    eprintln!("Error: missing command after --");
                    1
                } else {
                    let settings = load_settings(&workspace);
                    let shell_cmd = if cmd.len() == 1 {
                        cmd[0].clone()
                    } else {
                        cmd.join(" ")
                    };
                    let mode = get_sandbox_mode(&settings);
                    let timeout_secs = timeout.unwrap_or_else(|| get_bash_timeout(&settings));
                    let execute = || match run_bash_in_workspace(
                        &workspace,
                        &shell_cmd,
                        timeout_secs,
                        &settings,
                    ) {
                        Ok((code, out)) => {
                            print!("exit={code}\n{out}");
                            if code == 0 { 0 } else { code as i32 }
                        }
                        Err(e) => {
                            eprintln!("{e}");
                            1
                        }
                    };
                    if let Some(v) = check_bash_sandbox(&shell_cmd, &mode) {
                        if v.blocked {
                            eprintln!("{}", v.message);
                            1
                        } else {
                            execute()
                        }
                    } else {
                        execute()
                    }
                }
            }
            SandboxAction::Probe { workspace } => {
                let settings = load_settings(&workspace);
                println!(
                    "{}",
                    serde_json::to_string_pretty(&os_sandbox_probe_workspace(
                        &workspace, &settings
                    ))
                    .unwrap()
                );
                0
            }
        },
        Commands::Provider { action } => match action {
            ProviderAction::Probe { base_url, model } => {
                let probe = probe_provider(base_url.as_deref(), model.as_deref());
                println!(
                    "{}",
                    serde_json::to_string_pretty(&json!({
                        "apiKeySet": probe.api_key_set,
                        "baseUrl": probe.base_url,
                        "model": probe.model,
                    }))
                    .unwrap()
                );
                0
            }
            ProviderAction::Chat {
                base_url,
                model,
                input,
                tools,
                timeout,
            } => match resolve_config(base_url.as_deref(), model.as_deref()) {
                Ok(cfg) => match read_messages(input) {
                    Ok(messages) => {
                        let tools_v = match tools {
                            Some(p) => match fs::read_to_string(&p) {
                                Ok(t) => serde_json::from_str::<Vec<Value>>(&t).ok(),
                                Err(e) => {
                                    eprintln!("Error: tools file: {e}");
                                    std::process::exit(1);
                                }
                            },
                            None => None,
                        };
                        let tools_slice = tools_v.as_deref();
                        match chat_completions(&cfg, &messages, tools_slice, timeout) {
                            Ok(msg) => {
                                println!("{}", serde_json::to_string(&msg).unwrap());
                                0
                            }
                            Err(e) => {
                                eprintln!("{e}");
                                1
                            }
                        }
                    }
                    Err(e) => {
                        eprintln!("Error: {e}");
                        1
                    }
                },
                Err(e) => {
                    eprintln!("{e}");
                    1
                }
            },
        },
        Commands::Tools { action } => match action {
            ToolsAction::List => {
                for t in BUILTIN_TOOL_NAMES {
                    println!("{t}");
                }
                0
            }
            ToolsAction::Schemas { read_only } => {
                println!("{}", tool_schemas_json(read_only));
                0
            }
            ToolsAction::Run {
                workspace,
                tool,
                args,
            } => {
                let settings = load_settings(&workspace);
                let args_v: Value =
                    serde_json::from_str(&args).unwrap_or(Value::Object(Default::default()));
                let out = run_builtin_tool(&workspace, &tool, &args_v, &settings);
                print!("{out}");
                0
            }
        },
        Commands::Agent { action } => match action {
            AgentAction::Run {
                workspace,
                task,
                mode,
                max_turns,
                session_id,
                resume,
                require_approval,
                no_sensor,
                event_stream,
                save_plan,
                plan_output,
            } => match run_agent(AgentConfig {
                workspace,
                task,
                mode,
                max_turns,
                session_id,
                resume,
                require_approval,
                run_sensors_at_end: !no_sensor,
                event_stream,
                save_plan,
                plan_output,
            }) {
                Ok(result) => {
                    for line in result.lines {
                        println!("{line}");
                    }
                    match result.status.as_str() {
                        "completed" => 0,
                        "dod_failed" | "max_turns" => 2,
                        _ => 2,
                    }
                }
                Err(e) => {
                    eprintln!("Error: {e}");
                    1
                }
            },
            AgentAction::Session { action } => match action {
                SessionAction::List { workspace } => match list_sessions(&workspace) {
                    Ok(records) => {
                        for rec in records {
                            println!(
                                "{}  {}  {}  {}",
                                rec.id, rec.mode, rec.status, rec.task.chars().take(60).collect::<String>()
                            );
                        }
                        0
                    }
                    Err(e) => {
                        eprintln!("Error: {e}");
                        1
                    }
                },
                SessionAction::Show { workspace, id } => match load_session(&workspace, &id) {
                    Ok(Some(rec)) => {
                        println!("{}", serde_json::to_string_pretty(&rec).unwrap());
                        0
                    }
                    Ok(None) => {
                        eprintln!("Error: session not found: {id}");
                        1
                    }
                    Err(e) => {
                        eprintln!("Error: {e}");
                        1
                    }
                },
            },
        },
        Commands::Version => {
            println!("meris-rs {}", env!("CARGO_PKG_VERSION"));
            0
        }
        Commands::Run { meris_args } => {
            if let Some(code) = try_direct_native_run(&meris_args) {
                code
            } else {
                delegate_meris(&meris_args)
            }
        }
    };
    std::process::exit(code);
}

fn delegate_meris(args: &[String]) -> i32 {
    let meris = which_meris();
    let Some(meris) = meris else {
        eprintln!("Error: `meris` not found on PATH — pip install -e .");
        return 1;
    };
    let mut command = Command::new(meris);
    command
        .args(args)
        .stdin(Stdio::inherit())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit());
    if should_inject_native_loop_auto() {
        command.env("MERIS_NATIVE_LOOP", "auto");
    }
    let status = command.status();
    match status {
        Ok(s) => s.code().unwrap_or(1),
        Err(e) => {
            eprintln!("Error spawning meris: {e}");
            1
        }
    }
}

fn env_tri(name: &str) -> Option<bool> {
    let key = format!("MERIS_{name}");
    match std::env::var(&key).ok().as_deref().map(|s| s.trim().to_lowercase()) {
        Some(ref s) if s == "0" || s == "false" || s == "no" => Some(false),
        Some(ref s) if s == "1" || s == "true" || s == "yes" => Some(true),
        Some(ref s) if s == "auto" => None,
        Some(_) => None,
        None => None,
    }
}

fn native_disabled() -> bool {
    env_tri("NATIVE") == Some(false)
}

fn native_loop_disabled() -> bool {
    env_tri("NATIVE_LOOP") == Some(false)
}

fn native_loop_enabled_for_run_entry() -> bool {
    if native_loop_disabled() || native_disabled() {
        return false;
    }
    match env_tri("NATIVE_LOOP") {
        Some(true) => true,
        Some(false) => false,
        None => true,
    }
}

fn should_inject_native_loop_auto() -> bool {
    if std::env::var("MERIS_NATIVE_LOOP").is_ok() {
        return false;
    }
    !native_disabled()
}

struct DirectRunArgs {
    mode: String,
    task: String,
    workspace: PathBuf,
    session_id: Option<String>,
    event_stream: Option<PathBuf>,
    save_plan: bool,
    plan_output: Option<String>,
    max_turns: u32,
}

fn try_direct_native_run(args: &[String]) -> Option<i32> {
    if !native_loop_enabled_for_run_entry() {
        return None;
    }
    let parsed = parse_direct_run_args(args)?;
    let run_sensors = parsed.mode == "run";
    match run_agent(AgentConfig {
        workspace: parsed.workspace,
        task: parsed.task,
        mode: parsed.mode,
        max_turns: parsed.max_turns,
        session_id: parsed.session_id,
        resume: false,
        require_approval: false,
        run_sensors_at_end: run_sensors,
        event_stream: parsed.event_stream,
        save_plan: parsed.save_plan,
        plan_output: parsed.plan_output,
    }) {
        Ok(result) => {
            for line in result.lines {
                println!("{line}");
            }
            Some(match result.status.as_str() {
                "completed" => 0,
                "dod_failed" | "max_turns" => 2,
                _ => 2,
            })
        }
        Err(e) => {
            eprintln!("Error: {e}");
            Some(1)
        }
    }
}

fn parse_direct_run_args(args: &[String]) -> Option<DirectRunArgs> {
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
        if flag == "--ratchet"
            || flag == "--resume"
            || flag == "--require-approval"
            || flag == "--json"
            || flag.starts_with("--provider")
            || flag.starts_with("--max-turns")
        {
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
        max_turns: 30,
    })
}

fn parse_direct_review_args(args: &[String]) -> Option<DirectRunArgs> {
    for flag in args.iter().skip(1) {
        if flag == "--ratchet"
            || flag == "--resume"
            || flag == "--require-approval"
            || flag == "--json"
            || flag.starts_with("--provider")
        {
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
    })
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
