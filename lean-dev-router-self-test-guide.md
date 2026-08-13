# Lean Dev Router self-test guide

This guide measures routing behavior, cost, scope safety, and independent audit evidence without changing the target repository. It is a controlled guide, not a runtime profile.

## Routes under test

The ordinary route is Sol DISPATCH -> Luna write -> independent `terra_auditor` audit. The optional Terra High host-model capability is represented only as `PLANNER_ROLE: parent` plus `PLANNER_CAPABILITY: bounded_l1_l2_dispatch`; it is accepted for one strict L1/L2 component with one dispatch and one write batch. L3, risk, integration/conflict, ambiguity, contract or scope expansion, architecture/security/compatibility changes, B/D findings, and exhaustion route `parent:sol`.

The parent fast-path ceilings are 4 model calls, 2 hypotheses, 600 model-active seconds, 1 repair cycle, and 1 stagnant call. Sol retains 8 calls, 4 hypotheses, 1200 seconds, 2 repairs, and 2 stagnant calls. Missing or ineligible evidence must fail before Luna.

## Four-case controlled run

Use one fresh session, one immutable plan identity, an independent `terra_auditor` identity, and a temporary runtime-guard state outside the repository. Capture real planner/parent/auditor instance IDs, destination, and model call count.

1. Eligible L1: fixed objective/acceptance/constraints, no risk/action, one component/dispatch/write batch, depth 0, paths inside fixed `SCOPE_ROOTS`. Expected destination: Luna; budget: 4/2/600/1/1.
2. L3 or risk: change exactly one strict predicate. Expected destination: `parent:sol`; Luna calls: 0.
3. Identity collision: set `AUDITOR_INSTANCE_ID == PLANNER_INSTANCE_ID` or use the parent identity as final auditor. Expected rejection before target calls.
4. B finding: return an audit finding classified B. Expected `parent:sol`; no Luna repair call.

If native subagent/Codex execution is available, run these cases once without mocks and record the real identities, destinations, and call counts. If it is unavailable, report `BLOCKED/dependency` and do not substitute unit tests for this evidence.

## Scope evidence

`PATHS_ALLOW` authorizes persistent writes; relevant paths are read context. Before accepting a writer PASS, run:

```powershell
python scripts/check_scope.py --baseline <baseline> --allow <entry> ... --revision
```

Record tracked, ordinary untracked, and ignored untracked paths as tracked/untracked scope evidence. If the helper is unavailable, record equivalent Git commands:

```powershell
git diff --name-only --no-renames <baseline> --
git ls-files --others --exclude-standard
git ls-files --others --ignored --exclude-standard
```

Every path must be inside the exact allow-list. A clean committed state uses its SHA; an authorized dirty state uses `worktree-sha256:<64 lowercase hex>`. Build output belongs in external scratch or a declared disposable artifact root removed before scope passes.

## Audit and repair

Pre-register the final audit with `DISPATCH_ID`, `PLAN_ID`, revision, `AUDITOR_INSTANCE_ID`, `TASK_OBJECTIVE`, `CHANGE_SCOPE`, broader `AUDIT_SCOPE/IMPACT_CONE`, dependencies, acceptance, replay evidence, and an out-of-scope policy. The parent never self-audits. Terra findings are A (change-caused acceptance defect), B (necessary omitted scope), C (unrelated existing defect), or D (severe security/data-loss/compatibility risk). Only an in-scope A repair with `CONTRACT_EFFECT: unchanged`, unchanged acceptance, and remaining budget can return to Luna. B and D always route Sol.

Two or more write batches additionally require `integration_owner`, `integration_baseline`, `integration_paths_allow`, `integration_acceptance`, dependency order, and a clean integration worktree. Combined-state evidence uses `N/A (integration-check)` and `N/A (scope-check)`.

## Replay record

For each non-default check record cwd, environment delta, exact command, exit code, compact result, planner/parent/auditor identity, destination, model calls, hypothesis, and remaining budget. Do not rerun an unchanged command without changed evidence or hypothesis. Sleep is only polling or a backstop timeout; concurrent tests must prove the target branch.

## Verification commands

```powershell
python scripts/validate_repo.py
python -m unittest discover -s tests -v
```

The validator must report PASS, and the native four-case run must be reported separately from unit-test results.
