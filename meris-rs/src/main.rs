//! `meris-rs` — native CLI for harness primitives; delegates full agent loop to Python `meris`.

use clap::{Parser, Subcommand};
use meris_rs::{
    chat_completions, check_bash_sandbox, check_tool_allowed, compress_messages, estimate_tokens,
    get_bash_timeout, get_sandbox_mode, load_settings, os_sandbox_probe_workspace,
    probe_provider, resolve_config, run_bash_in_workspace, run_readonly_tool, verdict_to_json,
    READONLY_TOOLS,
};
use serde_json::Value;
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
    /// Execute read_file | glob | grep
    Run {
        #[arg(long)]
        workspace: PathBuf,
        #[arg(long)]
        tool: String,
        #[arg(long, default_value = "{}")]
        args: String,
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
                                    return 1;
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
                for t in READONLY_TOOLS {
                    println!("{t}");
                }
                0
            }
            ToolsAction::Run {
                workspace,
                tool,
                args,
            } => {
                let args_v: Value =
                    serde_json::from_str(&args).unwrap_or(Value::Object(Default::default()));
                let out = run_readonly_tool(&workspace, &tool, &args_v);
                print!("{out}");
                0
            }
        },
        Commands::Version => {
            println!("meris-rs {}", env!("CARGO_PKG_VERSION"));
            0
        }
        Commands::Run { meris_args } => delegate_meris(&meris_args),
    };
    std::process::exit(code);
}

fn delegate_meris(args: &[String]) -> i32 {
    let meris = which_meris();
    let Some(meris) = meris else {
        eprintln!("Error: `meris` not found on PATH — pip install -e .");
        return 1;
    };
    let status = Command::new(meris)
        .args(args)
        .stdin(Stdio::inherit())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .status();
    match status {
        Ok(s) => s.code().unwrap_or(1),
        Err(e) => {
            eprintln!("Error spawning meris: {e}");
            1
        }
    }
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
