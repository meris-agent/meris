"""Provider factory — select LLM backend from environment."""

from __future__ import annotations

from pathlib import Path

from meris.provider.base import Provider
from meris.provider.openai_compat import OpenAICompatProvider
from meris.provider.resolve import resolve_provider_config
from meris.provider.router import resolve_task_routing


def get_provider(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> Provider:
    """Return provider from MERIS_PROVIDER preset or env (see ``meris models list``)."""
    cfg = resolve_provider_config(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        model=model,
    )

    if cfg.backend == "anthropic":
        try:
            from meris.provider.anthropic import AnthropicProvider
        except ImportError as e:
            raise ImportError(
                "Anthropic provider requires: pip install meris-agent[anthropic]"
            ) from e
        return AnthropicProvider(api_key=cfg.api_key or None, model=cfg.model)

    return OpenAICompatProvider(
        api_key=cfg.api_key or None,
        base_url=cfg.base_url or None,
        model=cfg.model,
    )


def get_provider_from_overrides(overrides: dict[str, str]) -> Provider:
    """Build a provider from routing overrides."""
    return get_provider(
        provider=overrides.get("provider"),
        model=overrides.get("model"),
        base_url=overrides.get("base_url"),
    )


def get_provider_for_task(
    workspace: Path,
    mode: str,
    task: str,
    *,
    provider: Provider | None = None,
) -> tuple[Provider, str]:
    """
    Provider for an agent run: optional explicit instance, else settings ``models`` routing, else env.
    Returns (provider, routing note for logs — empty if env-only).
    """
    if provider is not None:
        return provider, ""
    overrides, route_note = resolve_task_routing(workspace, mode, task)
    p = get_provider(
        provider=overrides.get("provider"),
        model=overrides.get("model"),
        base_url=overrides.get("base_url"),
    )
    if route_note and overrides.get("provider"):
        note = f"route={route_note} provider={overrides['provider']}"
        if overrides.get("model"):
            note += f" model={overrides['model']}"
        return p, note
    return p, route_note
