"""Digest session history → insight candidates (rule + optional LLM)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from meris.harness.paths import harness_root
from meris.harness.ratchet.insights import (
    Insight,
    list_insights,
    load_insight,
    move_insight,
    new_insight_id,
    save_insight,
)
from meris.harness.ratchet.proposal import Proposal, ProposalTarget, new_proposal_id, save_proposal
from meris.harness.sessions import SessionRecord, list_sessions


@dataclass(frozen=True)
class DigestPattern:
    slug: str
    kind: str
    matchers: tuple[str, ...]
    min_sessions: int
    lesson: str
    target: str
    summary: str
    content: str
    question: str


DEFAULT_DIGEST_PATTERNS: tuple[DigestPattern, ...] = (
    DigestPattern(
        slug="settings-yaml-local",
        kind="user_habit",
        matchers=(
            "settings.local",
            "settings.yaml",
            "深合并",
            "只覆盖",
            "local 只",
            "yaml",
        ),
        min_sessions=2,
        lesson="L-insight-settings-yaml",
        target=".meris/rules/user-prefs.md",
        summary="settings 用 YAML，local 只做最小覆盖",
        question="你多次提到 YAML 配置与 settings.local 最小覆盖，是否写入 Harness？",
        content="""<!-- ratchet:L-insight-settings-yaml -->

## 配置习惯（用户确认）

- 团队共享：`.meris/settings.yaml`（可提交）
- 个人覆盖：`.meris/settings.local.yaml`（gitignore），**只写** ep、dynamic.enabled 等少量字段
- **不要**在 local 里整段复制 `byMode` / `rules`（深合并会**替换**列表，易踩路由坑）
- 注释用 YAML `#`，不用 JSONC
""",
    ),
    DigestPattern(
        slug="no-release-yet",
        kind="user_habit",
        matchers=(
            "不打包",
            "不要 release",
            "不发布",
            "先不 release",
            "continue optimizing",
            "不要 pypi",
        ),
        min_sessions=2,
        lesson="L-insight-no-release",
        target=".meris/rules/user-prefs.md",
        summary="暂不发版，优先 dogfood 与 Harness 优化",
        question="你多次表示先不打包/发布，是否写入 Harness 提醒 Agent？",
        content="""<!-- ratchet:L-insight-no-release -->

## 发布节奏（用户确认）

- 除非用户**明确要求**，不要提议 PyPI / GitHub Release / 升版本号
- 优先：dogfood、`meris benchmark run`、Ratchet 闭环、文档与路由打磨
""",
    ),
    DigestPattern(
        slug="harness-first",
        kind="project_preference",
        matchers=(
            "ratchet",
            "dogfood",
            "自我进化",
            "harness",
            "benchmark run",
        ),
        min_sessions=2,
        lesson="L-insight-harness-first",
        target=".meris/rules/user-prefs.md",
        summary="优先改 Harness，少动 Python 除非必要",
        question="你多次强调 Ratchet / dogfood / Harness-first，是否固化成规则？",
        content="""<!-- ratchet:L-insight-harness-first -->

## 工作方式（用户确认）

- 同类失误优先 `meris ratchet scan` / `digest` → 改 `.meris/rules` 或 `.meris/skills`
- 改 Python 源码前问：能否用 Harness 规则解决？
- 任务结束可建议：`meris benchmark run` 或 `meris ratchet status`
""",
    ),
    DigestPattern(
        slug="minimal-diff",
        kind="user_habit",
        matchers=(
            "最小 diff",
            "minimal scope",
            "不要 over",
            "别 over-engineer",
            "focused diff",
        ),
        min_sessions=2,
        lesson="L-insight-minimal-diff",
        target=".meris/rules/user-prefs.md",
        summary="最小改动，避免过度工程",
        question="你多次要求最小 diff / 不要 over-engineer，是否写入 Harness？",
        content="""<!-- ratchet:L-insight-minimal-diff -->

## 改动范围（用户确认）

- 只改与任务直接相关的文件；不顺手重构
- 不新增「一行 helper」式抽象；匹配现有代码风格
- 无请求的测试/文档不主动加
""",
    ),
)


def _parse_ts(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _session_in_window(rec: SessionRecord, since: datetime) -> bool:
    for field in (rec.updated_at, rec.created_at):
        dt = _parse_ts(field)
        if dt and dt >= since:
            return True
    return False


def collect_user_messages(
    workspace: Path,
    *,
    since_days: int = 30,
    max_sessions: int = 100,
) -> list[tuple[str, str]]:
    """Return (session_id, user_message_text) pairs within window."""
    ws = workspace.resolve()
    since = datetime.now(timezone.utc) - timedelta(days=since_days)
    out: list[tuple[str, str]] = []
    for rec in list_sessions(ws)[:max_sessions]:
        if not _session_in_window(rec, since):
            continue
        for msg in rec.messages:
            if msg.get("role") != "user":
                continue
            content = (msg.get("content") or "").strip()
            if content:
                out.append((rec.id, content))
    return out


def _text_matches(text: str, matchers: tuple[str, ...]) -> bool:
    lower = text.lower()
    for m in matchers:
        if m.lower() in lower:
            return True
    return False


def _lesson_in_harness(workspace: Path, lesson: str) -> bool:
    marker = f"ratchet:{lesson}"
    ws = workspace.resolve()
    profile = ws / ".meris" / "profile.md"
    if profile.is_file() and marker in profile.read_text(encoding="utf-8"):
        return True
    hroot = harness_root(ws)
    for sub in ("rules", "skills"):
        d = hroot / sub
        if not d.is_dir():
            continue
        for fp in d.glob("*.md"):
            if marker in fp.read_text(encoding="utf-8"):
                return True
    return False


def _insight_blocked(workspace: Path, pattern: DigestPattern) -> bool:
    if _lesson_in_harness(workspace, pattern.lesson):
        return True
    for st in ("pending", "dismissed", "accepted"):
        for ins in list_insights(workspace, status=st):
            if ins.lesson == pattern.lesson:
                return True
    from meris.harness.ratchet.proposal import list_proposals

    for prop in list_proposals(workspace, status=None):
        if prop.lesson == pattern.lesson and prop.status in ("pending", "applied"):
            return True
    return False


def digest_sessions_rule_based(
    workspace: Path,
    *,
    since_days: int = 30,
    min_sessions: int | None = None,
    patterns: tuple[DigestPattern, ...] = DEFAULT_DIGEST_PATTERNS,
) -> list[Insight]:
    """Mine user messages for repeated themes; no LLM."""
    ws = workspace.resolve()
    pairs = collect_user_messages(ws, since_days=since_days)
    created: list[Insight] = []

    for pat in patterns:
        if _insight_blocked(ws, pat):
            continue
        threshold = min_sessions if min_sessions is not None else pat.min_sessions
        hits: dict[str, list[str]] = {}
        for sid, text in pairs:
            if _text_matches(text, pat.matchers):
                hits.setdefault(sid, []).append(text[:120])

        if len(hits) < threshold:
            continue

        evidence = sorted(hits.keys())[:8]
        ins = Insight(
            id=new_insight_id(),
            kind=pat.kind,
            pattern=pat.summary,
            question=pat.question,
            count=len(hits),
            evidence=evidence,
            suggested_target=pat.target,
            suggested_content=pat.content.strip(),
            lesson=pat.lesson,
            status="pending",
            source="rule",
        )
        created.append(ins)

    return created


def digest_workspace(
    workspace: Path,
    *,
    since_days: int = 30,
    min_sessions: int = 2,
    save: bool = True,
    use_llm: bool = False,
) -> list[Insight]:
    """Run rule-based digest synchronously."""
    ws = workspace.resolve()
    created = digest_sessions_rule_based(
        ws, since_days=since_days, min_sessions=min_sessions
    )
    if save:
        for ins in created:
            save_insight(ws, ins)
    return created


async def digest_workspace_async(
    workspace: Path,
    *,
    since_days: int = 30,
    min_sessions: int = 2,
    save: bool = True,
    use_llm: bool = False,
) -> list[Insight]:
    """Rule digest + optional LLM pass."""
    ws = workspace.resolve()
    created = digest_sessions_rule_based(
        ws, since_days=since_days, min_sessions=min_sessions
    )
    if use_llm:
        from meris.harness.ratchet.digest_llm import digest_sessions_llm

        created.extend(await digest_sessions_llm(ws, since_days=since_days, existing=created))
    if save:
        for ins in created:
            save_insight(ws, ins)
    return created


def insight_to_proposal(insight: Insight) -> Proposal:
    content = insight.suggested_content
    marker = f"<!-- ratchet:{insight.lesson} -->"
    if marker not in content:
        content = f"{marker}\n\n{content.lstrip()}"
    return Proposal(
        id=new_proposal_id(),
        lesson=insight.lesson,
        summary=insight.pattern or insight.question[:200],
        target=ProposalTarget(
            path=insight.suggested_target,
            action="create",
            content=content,
        ),
        confidence="medium",
        signals=[f"digest:{insight.source}", f"insight:{insight.id}"],
        verify=[],
    )


def accept_insight(workspace: Path, insight_id: str, *, save_proposal_file: bool = True) -> Proposal | None:
    """Move insight to accepted and create a pending Ratchet proposal."""
    ws = workspace.resolve()
    ins = load_insight(ws, insight_id)
    if not ins or ins.status != "pending":
        return None
    proposal = insight_to_proposal(ins)
    if save_proposal_file:
        save_proposal(ws, proposal)
    move_insight(ws, insight_id, "accepted")
    return proposal


def dismiss_insight(workspace: Path, insight_id: str) -> bool:
    ins = load_insight(workspace, insight_id)
    if not ins or ins.status != "pending":
        return False
    move_insight(workspace, insight_id, "dismissed")
    return True


def format_digest_report(insights: list[Insight]) -> str:
    if not insights:
        return "No new insights."
    lines = [f"{len(insights)} insight candidate(s):"]
    for ins in insights:
        lines.append(f"- {ins.id} [{ins.lesson}] ×{ins.count} — {ins.question}")
        if ins.evidence:
            lines.append(f"  sessions: {', '.join(ins.evidence[:4])}")
    return "\n".join(lines)
