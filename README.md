# Lean Dev Router

Lean Dev Router is a compact, auditable routing contract for repository engineering. Sol plans exceptions, the parent schedules, Luna is the sole writer, and Terra performs independent read-only audits.

## Runtime

The directly executable English Skill is [`.agents/skills/lean-dev-router/SKILL.md`](.agents/skills/lean-dev-router/SKILL.md), exactly mirrored by [`skill-variants/en/SKILL.md`](skill-variants/en/SKILL.md). The Chinese and optimized files are replaceable variants for fresh sessions; they are never assembled into runtime context.

Only these child profiles are published:

- `luna_worker` (`gpt-5.6-luna`, max): bounded implementation and validation writes.
- `sol_planner` (`gpt-5.6-sol`, medium): exception planning, DISPATCH authority, and human decision gate.
- `terra_auditor` (`gpt-5.6-terra`, high, read-only): independent causal audit and bounded repair advice.

The parent is not a child profile. A Terra High host-model may use the conditional capability `PLANNER_ROLE: parent` plus `PLANNER_CAPABILITY: bounded_l1_l2_dispatch` for one strict low-risk L1/L2 batch. This is a bounded dispatch capability, not a second Sol and not authority to change architecture, scope, acceptance, constraints, risk, or policy.

## Parent fast path

Runtime guard accepts the parent capability only when evidence is explicit: L1/L2, fixed objective/acceptance/constraints, no major decision/risk/external action, exactly one component/dispatch/write batch, dependency depth 0, no integration/conflict/ambiguity/contract expansion, no contract/scope/acceptance/constraints/architecture/security/compatibility change, and every allowed/required path inside fixed `SCOPE_ROOTS`. Its hard budget is 4 calls, 2 hypotheses, 600 active seconds, 1 repair, and 1 stagnant call. Missing or ineligible evidence fails before Luna and routes `parent:sol`.

L3, risk, conflict or integration, multi-batch work, ambiguity, exhaustion, and B/D audit findings route Sol. B findings never enter Luna repair. Ordinary Sol DISPATCH packets remain backward compatible with v2 and retain the 8/4/1200/2/2 ceilings.

## Protocol and scope

Luna writes only after receiving a complete `PROTOCOL: lean-dev-router/v2` `STATUS: DISPATCH` packet relayed unchanged by the parent. `PATHS_ALLOW` is persistent write authorization; relevant paths are read context. Before accepting PASS, run:

```powershell
python scripts/check_scope.py --baseline <baseline> --allow <entry> ... --revision
```

If that helper is unavailable, record tracked, ordinary untracked, and ignored untracked Git enumerations. Clean revisions use the exact commit SHA; authorized dirty revisions use `worktree-sha256:<64 lowercase hex>`. Build output belongs in external scratch or a declared disposable artifact root removed before scope passes.

## Integration and audit

Two or more write batches require an `integration_owner`, dependency order, `integration_baseline`, `integration_paths_allow`, `integration_acceptance`, and a clean integration worktree. Component PASS is not whole-task PASS. Conflicts or compatibility edits require a new Sol-authorized write batch.

The final audit is preregistered and performed only by an independent `terra_auditor`; the parent never self-audits. Terra classifies findings as A (change-caused acceptance defect), B (necessary omitted scope), C (unrelated existing defect), or D (severe security/data-loss/compatibility risk). Only an in-scope A repair with `CONTRACT_EFFECT: unchanged` may return to Luna; B and D route Sol.

## Installation and verification

Install the Skill directory and the three files in `agents/` as one versioned unit. Start a fresh task after replacement. Check the guard without creating state:

```powershell
$guard = "$env:USERPROFILE/.codex/skills/lean-dev-router/scripts/runtime_guard.py"
python $guard schema
Get-Content dispatch.json -Raw | python $guard preflight
```

From a clean checkout run:

```powershell
python scripts/validate_repo.py
python -m unittest discover -s tests -v
```

The validator enforces the three child profiles, strict parent capability and Sol-only exceptions, closed routes, independent auditor identity, canonical Skill equality, aligned size-bounded variants, and no retired planner registration.

## Contents

| Path | Description |
|:---|:---|
| `.agents/skills/lean-dev-router/` | Skill plus deterministic runtime guard |
| `skill-variants/` | English, Chinese, and optimized variants |
| `agents/` | Three child profile TOMLs |
| `scripts/validate_repo.py` | Dependency-free consistency validator |
| `tests/` | Runtime and repository contract tests |
| `docs/zh-CN/README.md` | Chinese human documentation |
| `lean-dev-router-self-test-guide.md` | Controlled routing and cost test guide |
