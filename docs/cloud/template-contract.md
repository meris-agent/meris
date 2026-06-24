# Meris Cloud — session template contract

Meris Cloud session templates should embed the same **environment contract**
fields as local `.meris/environments/*.yaml`, so Agent behavior matches
between `meris ui` and Cloud sandboxes.

Reference example (open repo): [`docs/examples/environment-contract-ci-triage.yaml`](../examples/environment-contract-ci-triage.yaml)

## Template JSON (API / UI)

Cloud `POST /v1/sessions` and workspace templates may include:

```json
{
  "name": "ci-failure-triage",
  "repo_url": "https://github.com/org/repo.git",
  "workspace_id": "uuid",
  "scope_repos": ["https://github.com/org/other.git"],
  "template": {
    "environment_contract": {
      "name": "ci-failure-triage",
      "goal": "Classify CI failure, propose minimal fix, leave evidence",
      "blocked_actions": [
        "push to main",
        "delete tests without approval"
      ],
      "evaluators": [
        "pytest tests/ -m 'not integration' -q",
        "meris harness check"
      ],
      "budget": {
        "max_repair_rounds": 3,
        "max_wall_clock_minutes": 30
      },
      "dod_commands": [
        "pytest tests/ -m 'not integration' -q",
        "meris harness check"
      ],
      "blocked_paths": ["**/generated/**"],
      "handoff_path": ".meris/handoff.md",
      "benchmark_tasks": ".meris/benchmark/tasks.json"
    }
  }
}
```

## Field mapping

| Contract field | Cloud sandbox | Local Meris |
|----------------|---------------|-------------|
| `blocked_paths` | Session FS policy | `.meris/settings.yaml` → `blockedPaths` |
| `dod_commands` | Worker onComplete | `sensors` + AGENTS DoD |
| `evaluators` | Same as DoD | `meris harness check` + pytest |
| `budget.max_repair_rounds` | SSE session limits | `max_turns` in loop |
| `handoff_path` | Write on failure | `.meris/handoff.md` |
| `benchmark_tasks` | Optional post-run | `.meris/benchmark/tasks.json` |

## UI checklist (Cloud Web)

When creating a template in Cloud admin / UI:

1. **Git URL** — primary repo (maps to cwd / 主项目)
2. **DoD commands** — pre-fill from template (not empty clone only)
3. **Blocked paths** — sync to session policy
4. **Scope repos** — optional read-only multi-repo (task scope)
5. **Regression** — link to `meris benchmark regression` for Harness changes

## Trajectory → Ratchet (opt-in)

Local agent (open repo):

```bash
meris ratchet cluster              # show failure clusters
meris ratchet cluster --propose    # create proposals when count ≥ 2
```

Enable after failed runs (optional in `.meris/settings.yaml`):

```yaml
ratchet:
  clusterOnPostRun: true
```

Cloud backlog: export session events JSONL → same cluster pipeline (future).

## Related

- [deploy-baota.md](deploy-baota.md) — production nginx
- [runbook.md](runbook.md) — ops
- Local: [docs/harness/testing.md](../harness/testing.md)
