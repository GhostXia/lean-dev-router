# Codex Lean Dev Router

Token-efficient Codex coordination for three custom agents:

```text
sol_planner → luna_worker → terra_auditor
                         ↘ sol_planner (only for unresolved or major decisions)
```

## Contents

- `.agents/skills/lean-dev-router/`: the lightweight routing Skill.
- `agents/`: custom Agent TOML files for `luna_worker`, `sol_planner`, and `terra_auditor`.

## Install

Copy `.agents/skills/lean-dev-router/` to `~/.codex/skills/lean-dev-router/`, then copy the three files in `agents/` to `~/.codex/agents/`.

The intended roles are:

- `sol_planner`: initial planning and unresolved or major decisions.
- `luna_worker`: all authorized code, test, documentation, and configuration edits.
- `terra_auditor`: code audit, technical diagnosis, and validation; escalate only when it cannot resolve the issue or a major decision is required.

Use `$lean-dev-router` when a task benefits from this routing policy. The Skill deliberately avoids invoking all agents by default and passes only compact handoff information.
