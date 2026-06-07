"""Environment diagnostics — API key, model, harness files."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from meris.config import env_get, env_tri
from meris.harness.paths import harness_root
from meris.harness.settings import load_settings, shared_settings_relpath
from meris.harness.sandbox import (
    get_bash_timeout,
    get_effective_network_mode,
    get_mask_secrets,
    get_network_allowlist,
    get_network_mode,
    get_os_sandbox_mode,
    get_sandbox_mode,
    get_sandbox_preset,
    format_codex_preset_hint,
    describe_platform_sandbox,
    probe_os_sandbox,
)
from meris.native import find_native_binary, native_enabled, native_loop_enabled
from meris.provider import ProviderError, get_provider
from meris.provider.resolve import resolve_provider_config


@dataclass
class CheckResult:
    name: str
    status: str  # ok | warn | fail
    detail: str


def _resolve_env() -> dict[str, str]:
    cfg = resolve_provider_config()
    return {
        "provider": cfg.preset_id,
        "provider_label": cfg.label,
        "api_key": cfg.api_key,
        "base_url": cfg.base_url,
        "model": cfg.model,
        "key_env_hint": cfg.key_env_hint,
        "backend": cfg.backend,
    }


def check_harness(workspace: Path) -> list[CheckResult]:
    ws = workspace.resolve()
    results: list[CheckResult] = []
    hroot = harness_root(ws)
    settings_name = shared_settings_relpath(ws)
    file_checks = (
        ("AGENTS.md", ws / "AGENTS.md"),
        ("PROGRESS.md", ws / "PROGRESS.md"),
        (f"{hroot.name}/{settings_name}", hroot / settings_name),
    )
    for label, p in file_checks:
        if p.is_file():
            results.append(CheckResult(label, "ok", "present"))
        else:
            results.append(CheckResult(label, "warn", "missing — run meris init-harness"))
    settings = load_settings(ws)
    mcp_n = len(settings.get("mcpServers") or {})
    results.append(CheckResult("mcpServers", "ok" if mcp_n else "warn", f"{mcp_n} configured"))

    try:
        from meris.harness.ratchet import count_pending_insights, list_proposals

        pending = list_proposals(ws, status="pending")
        n_ins = count_pending_insights(ws)
        parts: list[str] = []
        if pending:
            parts.append(f"{len(pending)} proposal(s) — meris ratchet review")
        if n_ins:
            parts.append(f"{n_ins} insight(s) — meris ratchet insights review")
        if parts:
            results.append(CheckResult("ratchet", "warn", "; ".join(parts)))
        else:
            results.append(CheckResult("ratchet", "ok", "no pending proposals or insights"))
    except Exception:
        results.append(CheckResult("ratchet", "ok", "not initialized"))

    try:
        from meris.harness.guides import estimate_prompt_chars

        chars = estimate_prompt_chars(ws, mode="run")
        if chars > 28_000:
            results.append(
                CheckResult(
                    "system prompt",
                    "warn",
                    f"~{chars} chars — slim AGENTS / use docs/harness (Phase E1)",
                )
            )
        elif chars > 18_000:
            results.append(
                CheckResult(
                    "system prompt",
                    "warn",
                    f"~{chars} chars — move detail to docs/harness/",
                )
            )
        else:
            results.append(CheckResult("system prompt", "ok", f"~{chars} chars"))
    except Exception:
        pass

    mode = get_sandbox_mode(settings)
    timeout = get_bash_timeout(settings)
    os_mode = get_os_sandbox_mode(settings)
    net_mode = get_network_mode(settings)
    eff_net = get_effective_network_mode(settings)
    allowlist = get_network_allowlist(settings)
    preset = get_sandbox_preset(settings)
    mask_on = get_mask_secrets(settings)
    probe = probe_os_sandbox(ws, settings)
    masked_n = len(probe.get("maskedPaths") or [])
    if probe.get("wouldUseBubblewrap"):
        os_note = f", bwrap active, net={eff_net}"
        if allowlist:
            os_note += f", allowlist={len(allowlist)}"
        if mask_on and masked_n:
            os_note += f", mask {masked_n} secret file(s)"
    elif probe.get("wouldUseSeatbelt"):
        os_note = f", seatbelt active, net={eff_net}"
        if allowlist:
            os_note += f", allowlist={len(allowlist)}"
        if mask_on and masked_n:
            os_note += f", mask {masked_n} secret file(s)"
    elif os_mode == "require" and sys.platform == "linux" and not probe.get("bubblewrap"):
        os_note = ", osSandbox=require but bwrap missing"
    elif os_mode == "require" and sys.platform == "darwin" and not probe.get("sandboxExec"):
        os_note = ", osSandbox=require but sandbox-exec missing"
    elif probe.get("bubblewrap"):
        os_note = f", osSandbox={os_mode}, bwrap ok, net={eff_net}"
        if allowlist:
            os_note += f", allowlist={len(allowlist)}"
    elif probe.get("sandboxExec") and os_mode != "off":
        os_note = f", osSandbox={os_mode}, seatbelt ok, net={eff_net}"
    elif os_mode != "off":
        os_note = f", osSandbox={os_mode} (Linux bwrap / macOS seatbelt)"
    else:
        os_note = ""
    native = find_native_binary()
    if native and native_enabled():
        native_note = ", meris-rs active (auto)" if env_tri("NATIVE") is None else ", meris-rs (MERIS_NATIVE=1)"
    elif native:
        native_note = ", meris-rs built — auto when MERIS_NATIVE unset"
    else:
        native_note = ", build: meris native build"
    preset_note = f", preset={preset} ({format_codex_preset_hint(preset)})"
    if mode == "off":
        results.append(
            CheckResult(
                "sandbox",
                "warn",
                f"mode=off, bashTimeout={timeout}s{preset_note} — consider workspace-write (Phase G1){native_note}{os_note}",
            )
        )
    elif mode == "strict":
        results.append(
            CheckResult(
                "sandbox",
                "ok",
                f"mode=strict, bashTimeout={timeout}s{preset_note} — cd/find/pwd blocked{native_note}{os_note}",
            )
        )
    else:
        results.append(
            CheckResult(
                "sandbox",
                "ok",
                f"mode={mode}, bashTimeout={timeout}s{preset_note}, net={eff_net}{native_note}{os_note}",
            )
        )

    plat = describe_platform_sandbox(ws, settings)
    results.append(
        CheckResult(
            "platform sandbox",
            str(plat["status"]),
            str(plat["detail"]) + " — docs/harness/PLATFORM_MATRIX.md",
        )
    )

    binary = find_native_binary()
    loop_val = env_get("NATIVE_LOOP", "").strip().lower()
    if native_loop_enabled():
        results.append(
            CheckResult(
                "native loop",
                "ok",
                "MERIS_NATIVE_LOOP=auto — Rust agent loop active (Route B / G4)",
            )
        )
    elif binary and loop_val in ("0", "false", "no"):
        results.append(
            CheckResult(
                "native loop",
                "warn",
                "meris-rs present but MERIS_NATIVE_LOOP=0 — set auto in .env for Route B",
            )
        )
    elif binary and not loop_val:
        results.append(
            CheckResult(
                "native loop",
                "warn",
                "meris-rs present — add MERIS_NATIVE_LOOP=auto to .env (see ROUTE_B_COMPLETION.md)",
            )
        )
    elif binary and not native_enabled():
        results.append(
            CheckResult(
                "native loop",
                "warn",
                "meris-rs found but MERIS_NATIVE=0 — unset or set MERIS_NATIVE=1",
            )
        )
    else:
        results.append(
            CheckResult(
                "native loop",
                "warn",
                "no meris-rs — meris native build or install_meris_rs_from_ci.ps1",
            )
        )

    if sys.platform == "win32":
        from meris.harness.wsl import probe_wsl_bwrap

        wsl = probe_wsl_bwrap()
        if wsl.get("bwrapInWsl"):
            ver = wsl.get("bwrapVersion") or "ok"
            results.append(CheckResult("WSL sandbox", "ok", f"bwrap in WSL ({ver}) — run meris in WSL"))
        elif wsl.get("wslAvailable"):
            results.append(
                CheckResult(
                    "WSL sandbox",
                    "warn",
                    wsl.get("hint", "Install bubblewrap in WSL: sudo apt install bubblewrap"),
                )
            )
        else:
            results.append(
                CheckResult(
                    "WSL sandbox",
                    "warn",
                    wsl.get("hint", "Install WSL2 for Linux OS sandbox"),
                )
            )

    return results


def check_env() -> list[CheckResult]:
    env = _resolve_env()
    results: list[CheckResult] = []
    results.append(
        CheckResult("Provider", "ok", f"{env['provider']} ({env['provider_label']})"),
    )
    key = env["api_key"]
    key_label = env["key_env_hint"]
    if not key or key == "not-needed":
        results.append(CheckResult("API key", "fail", f"set {key_label} or OPENAI_API_KEY"))
    elif len(key) < 8:
        results.append(CheckResult("API key", "warn", "key looks too short"))
    else:
        masked = key[:4] + "…" + key[-4:] if len(key) > 10 else "****"
        results.append(CheckResult("API key", "ok", masked))
    if env["backend"] == "anthropic":
        results.append(CheckResult("Base URL", "ok", "(native Anthropic API)"))
    else:
        results.append(CheckResult("Base URL", "ok", env["base_url"] or "(missing — set MERIS_BASE_URL)"))
    results.append(CheckResult("Model", "ok", env["model"]))
    return results


async def check_api_live() -> CheckResult:
    env = _resolve_env()
    if not env["api_key"] or env["api_key"] == "not-needed":
        return CheckResult("API probe", "fail", "no key — skipped")
    try:
        provider = get_provider(
            api_key=env["api_key"],
            base_url=env["base_url"],
            model=env["model"],
        )
    except ImportError as e:
        return CheckResult("API probe", "fail", str(e)[:200])
    try:
        msg = await provider.chat(
            [
                {"role": "system", "content": "Reply with exactly: pong"},
                {"role": "user", "content": "ping"},
            ]
        )
        text = (msg.get("content") or "").lower()
        if "pong" in text:
            return CheckResult("API probe", "ok", f"model={provider.model}")
        return CheckResult("API probe", "warn", f"unexpected reply: {text[:80]}")
    except ProviderError as e:
        err = str(e)
        if "401" in err:
            return CheckResult("API probe", "fail", "401 — key invalid or wrong base URL")
        if "402" in err or "Balance" in err:
            return CheckResult("API probe", "fail", "402 — insufficient balance")
        return CheckResult("API probe", "fail", err[:200])


async def run_doctor(workspace: Path, *, probe: bool = True) -> list[CheckResult]:
    results = check_env() + check_harness(workspace)
    if probe:
        results.append(await check_api_live())
    return results
