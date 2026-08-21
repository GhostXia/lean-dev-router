---
name: lean-dev-router
description: Route repository engineering through Sol exceptions, a bounded Terra High parent fast path, Luna implementation, and independent Terra audit.
---

# Lean Dev Router

Use the smallest pool. Sol owns exceptions; the parent schedules; Luna writes; Terra audits.

## Language

Follow the parent task's primary language; when unspecified, use its dominant language. Keep code, commands, paths, model IDs, and agent names unchanged.

## Authority and entry

- Sol fixes objective, scope, acceptance, dependencies, budgets, contracts, audits, and routes. Only Sol authors or amends a Sol DISPATCH or requests human authority.
- The parent is a mechanical scheduler and may use only the conditional Terra High host-model capability described below. It cannot invent architecture, scope, acceptance, constraints, risk decisions, or product policy.
- Luna is the sole writer under a complete inbound DISPATCH. Terra is independent and read-only; when a final audit is required, only the preregistered terra_auditor performs it.
- Deployment, destructive action, external commitment, and user-owned policy remain outside this routing authority.

## Bounded planning waves

Sol emits PLAN_MANIFEST invariants plus the ready DISPATCH_WAVE; each entry declares worktree, dependencies, revision, replay, whether an audit is required, routes, and EXPANSION_GATE. The parent does not pre-expand distant work and returns undefined or contract-changing states to Sol.

## Protocol

Luna may write only after the parent relays this complete inbound contract unchanged. `PLANNER_CAPABILITY` is conditional: Sol packets remain compatible without it; a fast-path packet uses `PLANNER_ROLE: parent` and the exact capability below.

```text
PROTOCOL: lean-dev-router/v2
STATUS: DISPATCH
TARGET: implementation
DISPATCH_ID: stable unique component/write identifier
PLAN_ID: stable plan identifier
PLANNER_ROLE: sol_planner | parent
PLANNER_CAPABILITY: bounded_l1_l2_dispatch (parent fast path only)
PLANNER_INSTANCE_ID: immutable planner or parent instance identifier
AUDITOR_INSTANCE_ID: independent terra_auditor instance identifier
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

Every field required by the selected role is non-empty, IDs are stable, planner and auditor identities differ, and paths are repository-relative. The parent guard rejects an invalid packet and routes `parent:sol` before Luna is spawned. If Luna is nevertheless invoked defensively without valid authorization, it performs no inspection or write and returns `BLOCKED/none` to `parent:pause`. A Terra assignment is an ordinary read-only instruction, not an outbound result envelope and never `STATUS: DISPATCH`.

Roles return one compact envelope:

```text
PROTOCOL: lean-dev-router/v2
AGENT: luna_worker | terra_auditor | sol_planner
STATUS: PASS | BLOCKED | ESCALATE
FAILURE: none | missing_dispatch | scope | verification | dependency | ambiguity | major-decision
REQUEST: none | execution | implementation | technical_resolution | planning_resolution | human_authority
EVIDENCE:
- path: relative/path/to/file
  proof: short diff summary or command -> PASS/FAIL
NEXT: parent
SUMMARY: one concise sentence
```

`PASS`, `BLOCKED`, and `ESCALATE` are results, never write authorization. Evidence may use `N/A (planning-only)`, `N/A (batch coverage)`, `N/A (scope-check)`, or `N/A (integration-check)`. The closed handoff table is authoritative:

| AGENT | STATUS | REQUEST | Mechanical destination |
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

## Fast path eligibility

The parent capability is a Terra High host-model prerequisite, not a fourth child profile and not a second Sol. Packet fields are eligibility claims, not proof of authority. For `preflight` or `start`, the host must pass `--trusted-parent-instance-id <id> --trusted-parent-model gpt-5.6-terra --trusted-parent-reasoning-effort high` outside the packet; runtime guard binds that context to `PLANNER_INSTANCE_ID` and rejects a missing, mismatched, or non-Terra-High binding before Luna. This is a host coordination boundary, not cryptographic attestation. Runtime guard then accepts the packet only when all evidence is explicit and fixed:

- `PLANNER_ROLE: parent` and `PLANNER_CAPABILITY: bounded_l1_l2_dispatch`; `LEVEL` is L1 or L2; `OBJECTIVE_FIXED`, `OPEN_MAJOR_DECISIONS`, and all change flags are exact booleans.
- `BASELINE`, `SCOPE_ROOTS`, `ACCEPTANCE`, and `CONSTRAINTS` are non-empty; `RISK_FLAGS` and `EXTERNAL_ACTIONS` are none; no architecture, security, compatibility, contract, scope, acceptance, or constraint change is allowed.
- `MAX_DISPATCHES` is 1, `COMPONENT_COUNT` is 1, `WRITE_BATCH_COUNT` is 1, and `DEPENDENCY_DEPTH` is 0. `INTEGRATION`, `CONFLICT`, `CONTRACT_EXPANDED`, and `AMBIGUITY` are explicitly false/none.
- `PATHS_ALLOW` is non-empty and `REQUIRED_PATHS` may be empty, but every allowed or required path must stay inside the fixed repository-relative `SCOPE_ROOTS`.
- The parent budget ceiling is 4 model calls, 2 hypotheses, 600 active seconds, 1 repair, and 1 stagnant call. Missing or ineligible evidence fails before Luna and routes `parent:sol`.

L3, risk, conflict/integration, multiple batches, B/D findings, ambiguity, exhaustion, or any contract/scope/acceptance/constraints/architecture/security/compatibility change routes parent:sol. B findings never enter Luna repair. Sol remains fully compatible with ordinary v2 DISPATCH and uses its 8/4/1200/2/2 ceilings.

## Scope, artifacts, and revision

`PATHS_ALLOW` authorizes persistent writes only; relevant paths may be read context. Build output goes to external scratch or a declared disposable artifact root that is removed before scope passes. Before accepting PASS, run `python scripts/check_scope.py --baseline <baseline> --allow <entry> ... --revision`, or record the three Git fallback enumerations. A clean state uses its exact commit SHA; an authorized dirty state uses `worktree-sha256:<64 lowercase hex>` over the baseline, tracked diff, and allowed untracked content.

## Risk fuse and replay

`runtime_guard.py start --state <scratch-state>` atomically preflights and registers attempt 1. The host sends each terminal Luna `event` with explicit `PRODUCT_COUNT` and exact call/time/attempt/token telemetry; missing product is unknown and missing completion pauses. One zero-product retry uses `execution`; repair and `runtime_guard.py audit` reuse state. Unchanged failure, spinning, exhaustion, or drift fails closed. Synthetic tests prove guard logic, not host integration. Replay records cwd, environment delta, command, exit code, and result.

Every runtime audit `begin`, `complete`, or `abandon` packet carries:

```text
AUDITOR_ROLE: terra_auditor
AUDITOR_INSTANCE_ID: preregistered terra_auditor identity
AGENT_INSTANCE_ID: executing terra_auditor identity
```

The identities must match after case-insensitive normalization and retain the `terra_auditor` role lease. Missing fields, parent/Sol roles, mismatches, or another role lease fail closed. These are coordination constraints, not cryptographic authentication.

## Terra causal audit and repair

A final audit is conditional: it is required when the PLAN_MANIFEST, any risk flag, or the integration gate declares it. In those cases the issuing authority preregisters the audit contract before Luna; after Luna PASS and the mechanical gates, the parent runs runtime `audit begin` and launches an independent `terra_auditor`. The parent and planner never self-audit a declared final audit. Terra reads the diff plus causal callers/callees, data/error/resource flow, configuration, platforms, compatibility, concurrency, security, performance, and tests. Findings include path, evidence, causality, severity, blocking decision, and owner:

- **A** is a change-caused acceptance defect. A bounded `CONTRACT_EFFECT: unchanged` repair may return to Luna only with matching DISPATCH_ID, in-scope AFFECTED_PATHS, unchanged acceptance, and remaining repair budget.
- **B** is necessary omitted scope and **D** is severe security, data-loss, or compatibility risk; both route parent:sol and never enter Luna repair. **C** is an unrelated existing defect and is normally a non-blocking follow-up.

Declared dependency preparation is Luna-only. Missing/out-of-contract dependencies use `ESCALATE`/`technical_resolution`, never hidden `BLOCKED`/`none` prose. `parent:pause` permits no install, mutation, latch clearing, or resume. Read-only Terra returns unchanged-contract `implementation` advice or sends changes to Sol. Initial execution and one zero-product retry use `REQUEST: execution`; audit requires registered execution, product status, Luna PASS, and matching telemetry.

## Integration

Two or more write batches require shared `integration_owner`, `integration_baseline`, `integration_paths_allow`, and `integration_acceptance`, plus dependency order, a clean integration worktree, and a final combined-state Terra audit. Component PASS is not whole-task PASS. The integration owner combines accepted commits; conflicts or compatibility edits require a new Sol-authorized write batch. Final combined scope uses `N/A (integration-check)` and `N/A (scope-check)` evidence.

## Execution and human gate

Parallel Luna writers use isolated worktrees; read-only Terra may share a checkout. Sol is recalled only at the EXPANSION_GATE, an exception, a failed predicate, or a user-owned decision. Material objective, product, policy, architecture, security, compatibility, licensing, migration, cost, or irreversible choices return `human_authority` through the parent.

## Contents

| Path | Description |
|:---|:---|
| `.agents/skills/lean-dev-router/` | Routing Skill and deterministic runtime guard |
| `skill-variants/` | Canonical English, Chinese, and optimized variants |
| `agents/` | Three child profiles: `luna_worker`, `sol_planner`, `terra_auditor` |
| `scripts/validate_repo.py` | Dependency-free repository consistency checks |
| `lean-dev-router-self-test-guide.md` | Controlled routing and scope-evidence guide |

## Roles

| Role | Responsibility |
|:---|:---|
| **parent** | Mechanical scheduler; bounded Terra High host-model fast path only |
| **sol_planner** | Exception planning, DISPATCH authority, and human decision gate |
| **luna_worker** | Sole bounded writer in PATHS_ALLOW |
| **terra_auditor** | Independent read-only causal audit and repair advice |

## Final gates

Run `python scripts/validate_repo.py` and `python -m unittest discover -s tests -v`. Confirm canonical Skill equality, aligned size-bounded variants, exactly three child profiles, closed routes, strict parent predicate, conditional independent final auditing, clean integration scope, and concrete revision evidence before reporting completion.
