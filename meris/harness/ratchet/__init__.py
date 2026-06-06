"""Ratchet — harness self-evolution (signals → proposals → apply)."""

from meris.harness.ratchet.apply import apply_proposal, is_allowed_target, revert_proposal
from meris.harness.ratchet.digest import (
    accept_insight,
    digest_workspace,
    dismiss_insight,
    format_digest_report,
)
from meris.harness.ratchet.events import count_events, load_events, record_event
from meris.harness.ratchet.insights import count_pending_insights, list_insights, load_insight
from meris.harness.ratchet.proposal import Proposal, list_proposals, load_proposal, reject_proposal
from meris.harness.ratchet.learn import run_learn, scan_project
from meris.harness.ratchet.post_run import ratchet_post_run
from meris.harness.ratchet.profile import load_profile_text, rebuild_profile
from meris.harness.ratchet.scan import scan_workspace

__all__ = [
    "Proposal",
    "accept_insight",
    "apply_proposal",
    "count_events",
    "count_pending_insights",
    "digest_workspace",
    "dismiss_insight",
    "format_digest_report",
    "is_allowed_target",
    "list_insights",
    "list_proposals",
    "load_events",
    "load_insight",
    "load_profile_text",
    "load_proposal",
    "ratchet_post_run",
    "rebuild_profile",
    "record_event",
    "reject_proposal",
    "revert_proposal",
    "run_learn",
    "scan_project",
    "scan_workspace",
]
