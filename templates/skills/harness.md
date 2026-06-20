---
name: harness
description: Meris Harness 配置与约定（settings、sessions、skills、DoD）
---

# Example skill — copy to .meris/skills/ and customize

## When to use
Load this skill when working on Meris harness configuration.

## Key paths
- `.meris/settings.yaml` — permissions, sensors, hooks, mcpServers, models
- `.meris/sessions/` — persisted agent sessions
- `.meris/skills/` — on-demand knowledge (this directory)

## Conventions
- DoD commands live in AGENTS.md
- postEdit sensors run after write/edit
- Use `meris session resume <id>` to continue interrupted work
