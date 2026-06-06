"""Release check and live benchmark tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from meris.benchmark import load_benchmark_tasks
from meris.harness.release_check import ReleaseCheck, release_ready


def test_release_ready_logic() -> None:
    assert release_ready([ReleaseCheck("a", "ok", ""), ReleaseCheck("b", "warn", "")])
    assert not release_ready([ReleaseCheck("a", "ok", ""), ReleaseCheck("b", "fail", "x")])


def test_benchmark_local_tasks_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    tasks = load_benchmark_tasks(root / "scripts" / "benchmark" / "tasks.json")
    local = [t for t in tasks if t.local]
    assert len(local) >= 2
    ids = {t.id for t in local}
    assert "harness_check_smoke" in ids
    assert "review_smoke" in ids


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_benchmark_read_hello(workspace: Path) -> None:
    """Single cheap live task — requires API key."""
    import os

    from meris.benchmark import run_benchmark, summarize
    from meris.provider import OpenAICompatProvider, ProviderError

    key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    if not key:
        pytest.skip("no API key")

    base = os.getenv("MERIS_BASE_URL") or os.getenv("LLM_BASE_URL") or "https://api.deepseek.com/v1"
    model = os.getenv("MERIS_MODEL") or os.getenv("LLM_MODEL") or "deepseek-chat"
    provider = OpenAICompatProvider(api_key=key, base_url=base, model=model)

    root = Path(__file__).resolve().parents[1]
    from meris.benchmark import BenchmarkTask

    task = BenchmarkTask(
        id="read_hello_live",
        mode="ask",
        task="What does hello.py print? Use read_file only.",
        expect=["hello"],
        max_turns=6,
    )
    try:
        results = await run_benchmark(root, [task], provider=provider)
    except ProviderError as e:
        if "402" in str(e) or "401" in str(e):
            pytest.skip(str(e))
        raise
    assert summarize(results)["passed"] == 1
