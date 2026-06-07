"""Phase G2 — network allowlist (Codex-style)."""

from __future__ import annotations

from meris.harness.sandbox import (
    check_bash_sandbox,
    check_network_allowlist,
    extract_network_hosts,
    get_effective_network_mode,
    get_network_allowlist,
    host_allowed,
)


def test_host_allowed_wildcard() -> None:
    assert host_allowed("api.github.com", "*.github.com")
    assert host_allowed("github.com", "*.github.com")
    assert not host_allowed("evil.com", "*.github.com")


def test_host_allowed_exact() -> None:
    assert host_allowed("api.deepseek.com", "api.deepseek.com")
    assert not host_allowed("api.openai.com", "api.deepseek.com")


def test_extract_hosts_from_curl() -> None:
    hosts = extract_network_hosts("curl -fsSL https://api.deepseek.com/v1/models")
    assert hosts == ["api.deepseek.com"]


def test_allowlist_blocks_unknown_host() -> None:
    settings = {
        "sandbox": {
            "network": "isolated",
            "networkAllowlist": ["api.deepseek.com"],
        }
    }
    assert get_effective_network_mode(settings) == "allowlist"
    issue = check_network_allowlist(
        "curl https://evil.example.com/x",
        settings,
    )
    assert issue and "evil.example.com" in issue


def test_allowlist_allows_listed_host() -> None:
    settings = {
        "sandbox": {
            "networkAllowlist": ["pypi.org", "*.pythonhosted.org"],
        }
    }
    assert check_network_allowlist(
        "pip install meris-agent -i https://pypi.org/simple",
        settings,
    ) is None


def test_strict_blocks_bad_network_command(workspace) -> None:
    settings = {
        "sandbox": {
            "mode": "strict",
            "networkAllowlist": ["github.com"],
        }
    }
    verdict = check_bash_sandbox(
        workspace,
        "curl https://api.example.com",
        settings,
    )
    assert verdict is not None
    assert verdict.blocked is True
    assert "networkAllowlist" in verdict.message or "example.com" in verdict.message


def test_pytest_without_network_ok(workspace) -> None:
    settings = {
        "sandbox": {
            "mode": "strict",
            "networkAllowlist": ["github.com"],
        }
    }
    assert check_bash_sandbox(
        workspace,
        'pytest tests/ -m "not integration" -q',
        settings,
    ) is None
