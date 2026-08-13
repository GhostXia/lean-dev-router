---
name: lean-dev-router
description: Route repository engineering through Sol, parent, Luna, and Terra with deterministic runtime gates.
---

# Lean Dev Router

Use the smallest pool. Follow task language; preserve code, paths, IDs, agent names, and protocol literals.

## Authority and planning

Changes enter through `sol_planner`. Sol alone creates or changes objective, scope, acceptance, dependencies, budgets, write contracts, audits, or routes. `luna_worker` alone writes under a complete `DISPATCH`; it may choose only contract-preserving implementation details. `terra_auditor` is read-only and supplies causal evidence or bounded repair advice. The parent only validates and applies declared transitions. Undefined, incomplete, or contract-changing state returns to Sol.

Sol emits `PLAN_MANIFEST` plus ready `DISPATCH_WAVE`; each entry declares worktree, dependencies, revision/replay, audit, routes, and `EXPANSION_GATE`. Do not pre-expand; Terra may diagnose, but planning/authorization returns to Sol.

Contract-declared dependency preparation is Luna-only; parent and Terra never run it. Undeclared, missing, or out-of-contract tools/dependencies are zero-execution: Luna uses `ESCALATE`/`technical_resolution` -> `parent:terra`, never `BLOCKED/none`.

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

Every field is non-empty; IDs stay stable; planner and auditor identities differ; paths are repository-relative; no major decision remains. Terra assignments are ordinary read-only instructions, not an outbound result envelope or `STATUS: DISPATCH`. Missing authorization yields `FAILURE: missing_dispatch` and zero implementation calls.

All roles return only:

```text
PROTOCOL: lean-dev-router/v2
AGENT: luna_worker | terra_auditor | sol_planner
STATUS: PASS | BLOCKED | ESCALATE
FAILURE: none | missing_dispatch | scope | verification | dependency | ambiguity | major-decision
REQUEST: none | implementation | technical_resolution | planning_resolution | human_authority
EVIDENCE:
- path: relative/path/to/file
  proof: short diff summary or `command` -> PASS/FAIL
NEXT: parent
SUMMARY: one concise sentence
```

`PASS`, `BLOCKED`, and `ESCALATE` never authorize writes. Evidence may use `N/A (planning-only)`, `N/A (batch coverage)`, `N/A (scope-check)`, or `N/A (integration-check)`. The originating role corrects invalid output with `FAILURE: verification`. The parent rejects unlisted combinations and applies this table mechanically:

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
| `sol_planner` | `BLOCKED` | `implementation` | `parent:luna` |
| `sol_planner` | `BLOCKED` | `human_authority` | `parent:user` |

## Deterministic entry and scope

Before any Luna model call, pipe the complete JSON `DISPATCH` once to:

```text
python <skill-dir>/scripts/runtime_guard.py start --state <external-scratch-state>
```

`start` atomically performs preflight and creates persistent guard state; do not run a separate preflight in normal execution. Use the stateless `preflight` subcommand only to validate templates or an installed runtime. Exit 2 means zero target calls. Reuse the state for `event`, `repair`, and `audit`; never restart it.

`PATHS_ALLOW` authorizes persistent writes; build output uses external scratch. The scheduler verifies a disposable root is absent/empty before `start`, removes it before scope, and excludes artifacts from revision identity.

Before accepting Luna `PASS`, independently enumerate tracked, standard-untracked, and ignored-untracked paths. Prefer:

```text
python scripts/check_scope.py --baseline <baseline> --allow <entry> ... --revision
```

Otherwise use NUL-safe Git enumeration. Any retained or undeclared path rejects `PASS` with `FAILURE: scope`; parent never invents cleanup authority. A clean state revision is its exact commit SHA. A dirty state is `worktree-sha256:<64 lowercase hex>` over the resolved baseline, authorized tracked binary-safe diff, and framed authorized untracked paths/content. Reject placeholders and baseline-only dirty keys; equal state reproduces equal revision and every repair changes it.

## Bounded execution

`BUDGET` is a hard per-role/stage ceiling; Sol may only tighten runtime maxima of 8 model calls, 4 hypotheses, 1200 model-active seconds, 2 repair cycles, and 2 stagnant calls. Commands require timeouts; external wait is not model-active time.

Record each `event` with role/identity, revision/stage, contract/evidence fingerprint, calls, timing, upstream attempts, token/cache families, hypothesis, command/error, progress/evidence, and outcome. The guard derives uncached and total tokens. Repeated unchanged failure stops; two stagnant calls are deterministic `spinning`. The latch clears only after revision, contract, or evidence changes. Luna exhaustion routes Terra; Terra exhaustion routes Sol. Parent never repairs or writes.

`parent:pause` is zero-execution: parent must not run `npm ci`, install tools, mutate environment, clear latch, or resume Luna.

Within budget, attempt at most three materially different remedies per failed gate; never replay an unchanged command. Technical uncertainty requests `technical_resolution`; missing tool/permission/network requests dependency resolution; unauthorized paths are scope failure; baseline drift is verification failure and stops writes.

Pre-PASS technical escalation carries `DISPATCH_ID`, baseline, current diff/paths, hypotheses/attempts, exact cwd/environment/command/exit/result replay, contract bounds, and remaining budget; final scope/revision is not required. Terra inherits it unchanged. Concurrency evidence must prove the target branch or race occurred; sleep is only polling or fallback timeout.

## Streaming audit and repair

Process independent results as they arrive; combined integration alone uses an all-component barrier. Job key is `<component>:<revision>:<stage>` with `queued`, `running`, `complete`, or `failed`; retry only missing/failed keys. `token-first` may reuse one uninvolved Terra without sibling wait. Start eligible work within 60 seconds when capacity exists; otherwise record the queue and start at the first eligible slot release. Consume events during long parent commands; report external wait separately.

Sol preregisters each audit with matching `DISPATCH_ID`, component/dependencies, revision/job rule, `TASK_OBJECTIVE`, `CHANGE_SCOPE`, wider `AUDIT_SCOPE/IMPACT_CONE`, acceptance, replay, and out-of-scope policy. After Luna `PASS`, parent validates scope, concrete revision, dependencies, replay, and audit contract, then starts Terra directly without a routine Luna-to-Sol-to-Terra hop.

Register through `runtime_guard.py audit`; the same revision is never repeated. First audit is full; later revisions cover delta and unresolved findings. Early termination records `ACTION: abandon`, routes Sol, and never updates the incremental-audit baseline.

Terra may read beyond `PATHS_ALLOW` only along the bounded causal impact cone: callers/callees, data/error/resource flow, configuration, platform, compatibility, concurrency, security, performance, and tests. Wider reads grant no writes. Each outside finding states path, evidence, causality, severity, blocking decision, and owner; classify **A** change-caused acceptance defect, **B** omitted scope (Sol), **C** unrelated existing defect, or **D** severe security/data-loss/compatibility risk.

Terra never installs/runs tools or mutates environment. Technical-resolution work returns `ESCALATE`/`implementation` only for bounded `CONTRACT_EFFECT: unchanged`; contract/dependency changes return `ESCALATE`/`planning_resolution` to `parent:sol`.

For contract-preserving A repair, Terra returns `REQUEST: implementation` with original `PLAN_ID`/`DISPATCH_ID`, preregistered `AUDITOR_INSTANCE_ID`, `CONTRACT_EFFECT: unchanged`, in-scope `AFFECTED_PATHS`, original `ACCEPTANCE`, next `REPAIR_CYCLE`, new `REVISION`, and new `EVIDENCE_FINGERPRINT`. Parent validates identity, evidence, audit registration, paths, and budget, then returns the original Luna mechanically. Re-audit the new revision. Any scope/plan/acceptance/constraint/public-interface/architecture/security/data/resource change, ambiguity, or exhausted budget returns Sol.

## Integration and finish

Two or more write batches declare shared contracts, dependency order, `integration_worktree`, `integration_owner`, `integration_baseline`, `integration_paths_allow`, and `integration_acceptance`. The allow-list starts as the exact union of accepted batches. One authorized Luna integrates accepted commits in order; conflicts require new authorization. Whole-task `PASS` requires a clean combined state, final scope, complete acceptance, and every declared final audit; component success is not transitive.

Use isolated worktrees for concurrent Luna writers; read-only Terra may share a checkout. Pool caps are token-first 3, balanced 6, latency-first 10. If Sol cannot nested-spawn, it returns `BLOCKED/dependency/REQUEST implementation` with the literal manifest; parent relays without replanning.

Sol decides only reversible technical trade-offs inside the fixed contract. Objective, scope, acceptance, policy, or material compatibility/security/privacy/license/migration/cost/product commitment requires `BLOCKED/major-decision/REQUEST human_authority`; Sol gives at most three options, one recommendation, and one question. Stop when all manifest, scope, revision, audit, repair, integration, and final gates are terminal. When all declared gates pass, parent summarizes without another Sol call. Do not invoke every role, repeat unchanged stages, or let Luna/Terra orchestrate peers.
