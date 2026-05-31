"""Environment diagnostics — API key, model, harness files."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from meris.config import env_get
from meris.harness.paths import harness_root
from meris.harness.settings import load_settings
from meris.provider import ProviderError, get_provider


@dataclass
class CheckResult:
    name: str
    status: str  # ok | warn | fail
    detail: str


def _resolve_env() -> dict[str, str]:
    provider_kind = (env_get("PROVIDER") or os.getenv("LLM_PROVIDER") or "openai").lower()
    api_key = (
        os.getenv("ANTHROPIC_API_KEY")
        if provider_kind in ("anthropic", "claude")
        else (
            os.getenv("OPENAI_API_KEY")
            or os.getenv("LLM_API_KEY")
            or os.getenv("DEEPSEEK_API_KEY")
            or ""
        )
    )
    return {
        "provider": provider_kind,
        "api_key": api_key,
        "base_url": (
            env_get("BASE_URL")
            or os.getenv("LLM_BASE_URL")
            or os.getenv("DEEPSEEK_BASE_URL")
            or "https://api.deepseek.com/v1"
        ),
        "model": (
            env_get("MODEL")
            or os.getenv("LLM_MODEL")
            or os.getenv("ANTHROPIC_MODEL")
            or os.getenv("DEEPSEEK_MODEL")
            or (
                "claude-sonnet-4-20250514"
                if provider_kind in ("anthropic", "claude")
                else "deepseek-chat"
            )
        ),
    }


def check_harness(workspace: Path) -> list[CheckResult]:
    ws = workspace.resolve()
    results: list[CheckResult] = []
    hroot = harness_root(ws)
    settings_rel = f"{hroot.name}/settings.json"
    for name in ("AGENTS.md", "PROGRESS.md", settings_rel):
        p = ws / name
        if p.is_file():
            results.append(CheckResult(name, "ok", "present"))
        else:
            results.append(CheckResult(name, "warn", "missing — run meris init-harness"))
    settings = load_settings(ws)
    mcp_n = len(settings.get("mcpServers") or {})
    results.append(CheckResult("mcpServers", "ok" if mcp_n else "warn", f"{mcp_n} configured"))
    return results


def check_env() -> list[CheckResult]:
    env = _resolve_env()
    results: list[CheckResult] = []
    results.append(CheckResult("Provider", "ok", env["provider"]))
    key = env["api_key"]
    key_label = "ANTHROPIC_API_KEY" if env["provider"] in ("anthropic", "claude") else "LLM_API_KEY"
    if not key or key == "not-needed":
        results.append(CheckResult("API key", "fail", f"set {key_label} or OPENAI_API_KEY"))
    elif len(key) < 8:
        results.append(CheckResult("API key", "warn", "key looks too short"))
    else:
        masked = key[:4] + "…" + key[-4:] if len(key) > 10 else "****"
        results.append(CheckResult("API key", "ok", masked))
    results.append(CheckResult("Base URL", "ok", env["base_url"]))
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
