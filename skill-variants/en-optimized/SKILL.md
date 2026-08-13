---
name: lean-dev-router
description: Route repository engineering through Sol, parent, Luna, and Terra with deterministic runtime gates.
---

# Lean Dev Router

Use the smallest pool. Follow task language; preserve protocol literals.

## Authority and planning

Changes enter through `sol_planner`; only Luna writes under a complete `DISPATCH`, and Terra is read-only. Parent applies declared transitions; incomplete or contract-changing state returns to Sol.

Sol emits `PLAN_MANIFEST` plus ready `DISPATCH_WAVE`; entries declare worktree, dependencies, revision, audit, routes, and `EXPANSION_GATE`. Do not pre-expand.

Contract-declared dependency preparation is Luna-only; parent/Terra never run it. Undeclared or out-of-contract tools are zero-execution: Luna uses `ESCALATE`/`technical_resolution` -> `parent:terra`, never `BLOCKED/none`. Initial/no-product execution is Sol's only route; implementation is repair-only.

## Protocol

Only this complete inbound contract authorizes Luna:

```text
PROTOCOL: lean-dev-router/v2
STATUS: DISPATCH
TARGET: implementation
DISPATCH_ID: stable unique component/write identifier
PLAN_ID: stable plan identifier
PLANNER_ROLE: sol_planner
PLANNER_INSTANCE_ID: immutable planner instance identifier
AUDITOR_INSTANCE_ID: independent auditor instance identifier
TASK_SUMMARY: one bounded objective
BASELINE: commit hash
PATHS_ALLOW:
- relative/path/or/subtree
ACCEPTANCE:
- objective check and expected result
CONSTRAINTS:
- fixed implementation or compatibility bound
BUDGET:
  MODEL_CALL_LIMIT: positive integer
  HYPOTHESIS_LIMIT: positive integer
  MODEL_ACTIVE_SECONDS_LIMIT: positive integer
  REPAIR_CYCLE_LIMIT: positive integer
  STAGNANT_CALL_LIMIT: positive integer
NEXT: parent
```

Fields are non-empty; IDs stable; paths relative; no major decision remains. Terra assignments are read-only, not outbound envelopes or `STATUS: DISPATCH`. Missing authorization yields `FAILURE: missing_dispatch` and zero calls.

All roles return only:

```text
PROTOCOL: lean-dev-router/v2
AGENT: luna_worker | terra_auditor | sol_planner
STATUS: PASS | BLOCKED | ESCALATE
FAILURE: none | missing_dispatch | scope | verification | dependency | ambiguity | major-decision
REQUEST: none | execution | implementation | technical_resolution | planning_resolution | human_authority
EVIDENCE:
- path: relative/path/to/file
  proof: short diff summary or `command` -> PASS/FAIL
NEXT: parent
SUMMARY: one concise sentence
```

`PASS`, `BLOCKED`, and `ESCALATE` never authorize writes. Evidence may use `N/A (planning-only)`, `N/A (batch coverage)`, `N/A (scope-check)`, or `N/A (integration-check)`. The parent rejects unlisted combinations mechanically:

| AGENT | STATUS | REQUEST | Destination |
|:---|:---|:---|:---|
| `luna_worker` | `PASS` | `none` | `parent:manifest_gate` |
| `luna_worker` | `BLOCKED` | `none` | `parent:pause` |
| `luna_worker` | `ESCALATE` | `technical_resolution` | `parent:terra` |
| `terra_auditor` | `PASS` | `none` | `parent:manifest_gate` |
| `terra_auditor` | `BLOCKED` | `none` | `parent:pause` |
| `terra_auditor` | `ESCALATE` | `implementation` | `parent:repair_or_sol` |
| `terra_auditor` | `ESCALATE` | `planning_resolution` | `parent:sol` |
| `sol_planner` | `PASS` | `none` | `parent:manifest_gate` |
| `sol_planner` | `BLOCKED` | `none` | `parent:pause` |
| `sol_planner` | `BLOCKED` | `execution` | `parent:luna` |
| `sol_planner` | `BLOCKED` | `human_authority` | `parent:user` |

## Deterministic entry and scope

Before any Luna model call, pipe the complete JSON `DISPATCH` once to:

```text
python <skill-dir>/scripts/runtime_guard.py start --state <external-scratch-state>
```

`start` atomically performs preflight and creates persistent guard state; do not run separate preflight. Use the stateless `preflight` subcommand for templates. Exit 2 means zero target calls. Reuse state for `event`, `execution`, `repair`, and `audit`; never restart. The guard bounds two unchanged-DISPATCH, clean-BASELINE, zero-product attempts and routes dirty/changed/exhausted/post-evidence retries to Sol.

`PATHS_ALLOW` authorizes persistent writes; build output uses external scratch. The scheduler verifies a disposable root is absent/empty before `start`, removes it before scope, and excludes artifacts from revision identity.

Before accepting Luna `PASS`, independently enumerate tracked, standard-untracked, and ignored-untracked paths. Prefer:

```text
python scripts/check_scope.py --baseline <baseline> --allow <entry> ... --revision
```

Otherwise use NUL-safe Git enumeration. Retained or undeclared paths reject `PASS` with `FAILURE: scope`; parent never invents cleanup authority. Clean state uses its SHA; dirty state uses `worktree-sha256:<64 lowercase hex>`. Reject placeholders and baseline-only keys; equal state reproduces equal revision and repairs change it.

## Bounded execution

`BUDGET` is a hard per-role/stage ceiling; Sol may only tighten runtime maxima of 8 model calls, 4 hypotheses, 1200 model-active seconds, 2 repair cycles, and 2 stagnant calls. Commands require timeouts; external wait is not model-active time.

Record each `event` with identity, revision/stage, fingerprints, calls, timing, attempts, tokens, hypothesis, command/error, progress, and outcome. Guard derives totals. Unchanged failure stops; two stagnant calls are deterministic `spinning`. The latch clears after revision, contract, or evidence changes. Luna exhaustion routes Terra; Terra exhaustion routes Sol. Parent never repairs or writes.

`parent:pause` is zero-execution: parent must not run `npm ci`, install tools, mutate environment, clear latch, or resume Luna. `REQUEST: execution` returns to `parent:luna`; `REQUEST: implementation` is reserved for Terra's contract-preserving repair.

Within budget, use three distinct remedies per failed gate; never replay an unchanged command. Technical uncertainty requests `technical_resolution`; missing tools request dependency resolution; unauthorized paths are scope failure; baseline drift stops writes.

Pre-PASS technical escalation carries `DISPATCH_ID`, baseline, current diff/paths, hypotheses/attempts, exact cwd/environment/command/exit/result replay, contract bounds, and remaining budget; final scope/revision is not required. Terra inherits it unchanged. Concurrency evidence must prove the target branch or race occurred; sleep is only polling or fallback timeout.

## Streaming audit and repair

Process independent results as they arrive; only integration uses an all-component barrier. Job key is `<component>:<revision>:<stage>`; retry only missing/failed keys. `token-first` may reuse uninvolved Terra. Start eligible work within 60 seconds; otherwise record queue. Consume events during long commands.

Sol preregisters each audit with `DISPATCH_ID`, dependencies, revision/job rule, objective, scope, impact cone, acceptance, replay, and policy. After matching Luna `PASS`, concrete revision, scope/replay evidence, explicit dependencies, and telemetry, parent starts Terra; missing execution/product returns `REQUEST: execution` to Luna; contradictory evidence returns Sol without Terra.

Register through `runtime_guard.py audit`; the same revision is never repeated. First audit is full; later revisions cover delta and unresolved findings. Early termination records `ACTION: abandon`, routes Sol, and never updates the incremental-audit baseline.

Terra reads beyond `PATHS_ALLOW` only along the causal impact cone: callers/callees, data/error/resource flow, configuration, platform, compatibility, concurrency, security, performance, and tests. Wider reads grant no writes. Classify findings **A** change defect, **B** omitted scope (Sol), **C** unrelated issue, or **D** severe risk.

Terra never installs/runs tools or mutates environment. Technical-resolution work returns `ESCALATE`/`implementation` only for bounded `CONTRACT_EFFECT: unchanged` repair; initial/no-product execution uses `REQUEST: execution`, and contract/dependency changes return `ESCALATE`/`planning_resolution` to `parent:sol`.

For contract-preserving A repair, Terra returns `REQUEST: implementation` with original IDs, `AUDITOR_INSTANCE_ID`, `CONTRACT_EFFECT: unchanged`, in-scope paths, acceptance, `REPAIR_CYCLE`, new `REVISION`, and evidence. Parent validates identity, evidence, paths, and budget, then returns Luna. Re-audit the new revision. Scope/plan/acceptance/constraint/interface/architecture/security/data/resource changes, ambiguity, or exhaustion return Sol; this route is independent of initial execution.

## Integration and finish

Two or more write batches declare shared contracts, dependency order, `integration_worktree`, `integration_owner`, `integration_baseline`, `integration_paths_allow`, and `integration_acceptance`. One Luna integrates accepted commits; conflicts require new authorization. Whole-task `PASS` requires clean combined state, final scope, acceptance, and final audit.

Use isolated worktrees for concurrent Luna writers; read-only Terra may share a checkout. Pool caps are token-first 3, balanced 6, latency-first 10. If Sol cannot nested-spawn, it returns `BLOCKED/dependency/REQUEST execution` with the literal manifest; parent relays without replanning.

Sol decides only reversible trade-offs. Objective, scope, acceptance, policy, or material compatibility/security/privacy/license/migration/cost/product commitment requires `BLOCKED/major-decision/REQUEST human_authority`; Sol gives three options, one recommendation, and one question. Stop when all gates are terminal; parent summarizes without another Sol call. Do not repeat unchanged stages or let Luna/Terra orchestrate peers.
