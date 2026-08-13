---
name: lean-dev-router
description: Compact bounded parent fast path for lean-dev-router.
---

# Lean Dev Router

Sol plans exceptions; parent schedules; Luna writes; Terra audits.

## Protocol

The parent relays a complete v2 DISPATCH. `PLANNER_CAPABILITY: bounded_l1_l2_dispatch` is conditional for the parent; the ordinary Sol packet remains compatible.

```text
PROTOCOL: lean-dev-router/v2
STATUS: DISPATCH
TARGET: implementation
DISPATCH_ID: stable identifier
PLAN_ID: stable plan
PLANNER_ROLE: sol_planner | parent
PLANNER_CAPABILITY: bounded_l1_l2_dispatch (parent only)
PLANNER_INSTANCE_ID: immutable planner identity
AUDITOR_INSTANCE_ID: independent terra_auditor identity
TASK_SUMMARY: bounded objective
BASELINE: commit hash
PATHS_ALLOW:
- relative/path
ACCEPTANCE:
- objective check
CONSTRAINTS:
- fixed bound
BUDGET:
  MODEL_CALL_LIMIT: positive integer
  HYPOTHESIS_LIMIT: positive integer
  MODEL_ACTIVE_SECONDS_LIMIT: positive integer
  REPAIR_CYCLE_LIMIT: positive integer
  STAGNANT_CALL_LIMIT: positive integer
NEXT: parent
```

```text
PROTOCOL: lean-dev-router/v2
AGENT: luna_worker | terra_auditor | sol_planner
STATUS: PASS | BLOCKED | ESCALATE
FAILURE: none | missing_dispatch | scope | verification | dependency | ambiguity | major-decision
REQUEST: none | implementation | technical_resolution | planning_resolution | human_authority
EVIDENCE:
- path: relative/path
  proof: command -> PASS/FAIL
NEXT: parent
SUMMARY: concise result
```

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
| `sol_planner` | `BLOCKED` | `implementation` | `parent:luna` |
| `sol_planner` | `BLOCKED` | `human_authority` | `parent:user` |

## Fast path eligibility

- Accept only L1/L2, fixed objective/acceptance/constraints, no major decision, risk, external action, integration, conflict, ambiguity, expansion, or architecture/security/compatibility change.
- Require one component, one dispatch, one write batch, dependency depth 0, and allowed/required paths inside fixed SCOPE_ROOTS.
- Parent ceilings are 4 calls, 2 hypotheses, 600 active seconds, 1 repair, and 1 stagnant call; missing evidence routes parent:sol before Luna.
- L3, B/D findings, exhaustion, or contract/scope changes route parent:sol; B never enters Luna repair.
- Final audit is conditional. A PLAN_MANIFEST declaration, any risk flag, or the integration gate requires the issuer to preregister its contract before Luna. After Luna PASS, runtime `audit begin` starts an independent terra_auditor; parent/planner cannot self-audit.
- Audit begin/complete/abandon requires `AUDITOR_ROLE: terra_auditor`, preregistered `AUDITOR_INSTANCE_ID`, and matching executing `AGENT_INSTANCE_ID` under case-insensitive normalization and the Terra role lease. Missing/mismatched fields fail closed; this is coordination, not cryptographic authentication.

## Integration

Use PLAN_MANIFEST, DISPATCH_WAVE, and EXPANSION_GATE. Two batches require integration_owner, integration_baseline, integration_paths_allow, integration_acceptance, and a final combined-state Terra audit; record N/A (batch coverage), N/A (scope-check), and N/A (integration-check) evidence.

## Final gates

Run runtime_guard.py start before Luna; only when audit is declared, run runtime `audit begin` after Luna PASS. Then run `python scripts/validate_repo.py` and the unittest suite. Scope evidence uses `python scripts/check_scope.py`; dirty revisions use `worktree-sha256:<64 lowercase hex>`. A Terra A repair requires CONTRACT_EFFECT: unchanged.
