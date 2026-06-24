"""Pre-commit / CI guard — block secrets and paths that must not ship in git."""

from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from meris.harness.paths import harness_root

# Paths that must never be committed (fnmatch against repo-relative posix paths).
DEFAULT_FORBIDDEN_PATH_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "!.env.example",
    ".meris/sessions/**",
    ".meris/plan/**",
    ".meris/ratchet/**",
    ".meris/events/**",
    ".meris/context/**",
    ".meris/ui/**",
    ".meris/settings.local.*",
    ".meris/commit-guard.local.yaml",
    "**/settings.local.yaml",
    "**/settings.local.yml",
    "**/settings.local.json",
    ".cursor/**",
    "**/__pycache__/**",
    "**/*.pyc",
    "dist-test/**",
    "vendor/meris-agent/**",
    "**/credentials.json",
    "**/*_credentials.json",
)

# (regex, rule_id, human label)
DEFAULT_SECRET_PATTERNS: tuple[tuple[str, str, str], ...] = (
    (r"(?<![/\w])sk-(?:proj-)?[A-Za-z0-9_-]{20,}", "secret:openai_key", "OpenAI-style API key"),
    (r"(?<![/\w])ghp_[A-Za-z0-9]{36,}", "secret:github_pat", "GitHub personal access token"),
    (r"(?<![/\w])github_pat_[A-Za-z0-9_]{20,}", "secret:github_pat", "GitHub fine-grained PAT"),
    (r"(?<![/\w])pypi-AgEI[A-Za-z0-9_-]{50,}", "secret:pypi_token", "PyPI upload token"),
    (r"mysql\+pymysql://[^/\s]+:[^@\s]+@", "secret:mysql_url", "MySQL URL with embedded password"),
    (r"MERIS_CLOUD_JWT_SECRET\s*=\s*[a-fA-F0-9]{16,}", "secret:jwt", "Meris Cloud JWT secret value"),
    (r"TWINE_PASSWORD\s*=\s*['\"]?pypi-", "secret:twine", "PyPI token in TWINE_PASSWORD"),
)

COMMIT_GUARD_CONFIG_NAMES = ("commit-guard.yaml", "commit-guard.local.yaml")

_PLACEHOLDER_LINE = re.compile(
    r"example|placeholder|your[-_]|xxx|\.\.\.|secrets\.|__token__|\$\{\{|"
    r"don't commit|do not commit|never commit|不要提交|勿复制|pypi-\.\.\.",
    re.I,
)


@dataclass(frozen=True)
class CommitGuardRules:
    forbidden_paths: tuple[str, ...]
    secret_patterns: tuple[tuple[str, str, str], ...]


@dataclass(frozen=True)
class CommitFinding:
    rule: str
    path: str
    detail: str

    def format(self) -> str:
        return f"[{self.rule}] {self.path}: {self.detail}"


def _parse_guard_yaml(raw: object) -> tuple[list[str], list[tuple[str, str, str]]]:
    if not isinstance(raw, dict):
        return [], []
    extra_paths: list[str] = []
    for item in raw.get("extra_forbidden_paths") or []:
        if isinstance(item, str) and item.strip():
            extra_paths.append(item.strip())
    extra_patterns: list[tuple[str, str, str]] = []
    for item in raw.get("extra_patterns") or []:
        if not isinstance(item, dict):
            continue
        regex = item.get("regex")
        rule = item.get("rule")
        label = item.get("label")
        if isinstance(regex, str) and isinstance(rule, str) and isinstance(label, str):
            if regex.strip() and rule.strip() and label.strip():
                extra_patterns.append((regex.strip(), rule.strip(), label.strip()))
    return extra_paths, extra_patterns


def load_commit_guard_rules(root: Path) -> CommitGuardRules:
    """Defaults plus optional `.meris/commit-guard.yaml` and `.meris/commit-guard.local.yaml`."""
    root = root.resolve()
    hroot = harness_root(root)
    extra_paths: list[str] = []
    extra_patterns: list[tuple[str, str, str]] = []
    for name in COMMIT_GUARD_CONFIG_NAMES:
        fp = hroot / name
        if not fp.is_file():
            continue
        try:
            raw = yaml.safe_load(fp.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        paths, patterns = _parse_guard_yaml(raw)
        extra_paths.extend(paths)
        extra_patterns.extend(patterns)
    return CommitGuardRules(
        forbidden_paths=DEFAULT_FORBIDDEN_PATH_PATTERNS + tuple(extra_paths),
        secret_patterns=DEFAULT_SECRET_PATTERNS + tuple(extra_patterns),
    )


def _posix_rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _match_forbidden(path: str, rules: CommitGuardRules) -> str | None:
    negated = [p[1:] for p in rules.forbidden_paths if p.startswith("!")]
    patterns = [p for p in rules.forbidden_paths if not p.startswith("!")]
    if any(fnmatch.fnmatch(path, pat) for pat in negated):
        return None
    for pat in patterns:
        if fnmatch.fnmatch(path, pat):
            return pat
    return None


def _scan_text(path: str, text: str, rules: CommitGuardRules) -> list[CommitFinding]:
    findings: list[CommitFinding] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        if _PLACEHOLDER_LINE.search(line):
            continue
        for regex, rule, label in rules.secret_patterns:
            try:
                matched = re.search(regex, line)
            except re.error:
                continue
            if matched:
                snippet = line.strip()[:80]
                findings.append(
                    CommitFinding(
                        rule=rule,
                        path=path,
                        detail=f"line {line_no}: {label} — {snippet}",
                    )
                )
                break
    return findings


def check_paths(paths: list[str], rules: CommitGuardRules | None = None) -> list[CommitFinding]:
    rules = rules or CommitGuardRules(
        forbidden_paths=DEFAULT_FORBIDDEN_PATH_PATTERNS,
        secret_patterns=DEFAULT_SECRET_PATTERNS,
    )
    out: list[CommitFinding] = []
    for rel in paths:
        rel = rel.replace("\\", "/")
        if not rel:
            continue
        pat = _match_forbidden(rel, rules)
        if pat:
            out.append(CommitFinding("forbidden_path", rel, f"matches `{pat}`"))
    return out


def check_file_content(
    root: Path,
    rel: str,
    *,
    rules: CommitGuardRules | None = None,
) -> list[CommitFinding]:
    rules = rules or load_commit_guard_rules(root)
    fp = root / rel
    if not fp.is_file():
        return []
    try:
        text = fp.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [CommitFinding("read_error", rel, str(exc))]
    if rel.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".woff", ".woff2")):
        return []
    return _scan_text(rel, text, rules)


def run_commit_guard(
    root: Path,
    paths: list[str],
    *,
    scan_content: bool = True,
    rules: CommitGuardRules | None = None,
) -> list[CommitFinding]:
    root = root.resolve()
    rules = rules or load_commit_guard_rules(root)
    rels = sorted({p.replace("\\", "/") for p in paths if p.strip()})
    findings = check_paths(rels, rules)
    if scan_content:
        for rel in rels:
            if _match_forbidden(rel, rules):
                continue
            findings.extend(check_file_content(root, rel, rules=rules))
    return findings


def _git_lines(root: Path, *args: str) -> list[str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "git failed").strip())
    return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]


def staged_paths(root: Path) -> list[str]:
    return _git_lines(root, "diff", "--cached", "--name-only", "--diff-filter=ACMR")


def tracked_paths(root: Path) -> list[str]:
    return _git_lines(root, "ls-files")


def diff_paths(root: Path, rev_range: str) -> list[str]:
    return _git_lines(root, "diff", "--name-only", "--diff-filter=ACMR", rev_range)


def findings_failed(findings: list[CommitFinding]) -> bool:
    return bool(findings)


def format_findings(findings: list[CommitFinding]) -> str:
    return "\n".join(f.format() for f in findings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Meris commit guard — secrets & forbidden paths")
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--cached", action="store_true", help="Check git staged files (pre-commit)")
    group.add_argument("--tracked", action="store_true", help="Check all tracked files (CI)")
    group.add_argument("--diff", metavar="REV_RANGE", help="Check files changed in rev range")
    parser.add_argument("--paths", nargs="*", help="Explicit paths to check")
    parser.add_argument("--no-content", action="store_true", help="Path rules only, skip content scan")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    root = args.cwd.resolve()
    if args.paths is not None:
        paths = args.paths
    elif args.cached:
        paths = staged_paths(root)
    elif args.tracked:
        paths = tracked_paths(root)
    elif args.diff:
        paths = diff_paths(root, args.diff)
    else:
        paths = staged_paths(root)

    if not paths:
        return 0

    findings = run_commit_guard(
        root,
        paths,
        scan_content=not args.no_content,
    )
    if args.json:
        import json

        print(json.dumps([f.__dict__ for f in findings], ensure_ascii=False, indent=2))
    elif findings:
        print("Commit guard FAILED — remove or unstage before committing:\n")
        print(format_findings(findings))
        print("\nSee CONTRIBUTING.md · install hook: bash scripts/install-git-hooks.sh")
    else:
        print(f"Commit guard OK ({len(paths)} path(s) checked)")

    return 1 if findings_failed(findings) else 0


if __name__ == "__main__":
    sys.exit(main())
