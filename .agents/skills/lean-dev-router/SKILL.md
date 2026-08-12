---
name: lean-dev-router
description: Route repository engineering through deterministic Terra planning, Sol exceptions, Luna implementation, and independent Terra audit.
---

# Lean Dev Router

Use the smallest sufficient pool. The parent schedules mechanically; Luna writes;
Terra audits; Sol owns exceptions and user decisions.

## Language

Follow the parent task's primary language; when unspecified, use its dominant
language. Use English when no natural-language signal exists. Keep code,
commands, paths, model IDs, and agent names unchanged.

## Authority and entry

- Start change-producing work with one read-only `terra_planner` classification.
  It derives the canonical eligibility evidence from the user objective and
  repository; eligible work continues there, while a failed predicate routes
  directly to Sol. The parent does not classify the task.
- `terra_planner` directly replaces routine Sol planning only for the exact
  eligible L1/L2 predicate below. It is read-only, cannot schedule or wait,
  implement, audit, amend after execution, or request `human_authority`.
- `sol_planner` plans every failed predicate, L3 task, ambiguity, required path
  outside `SCOPE_ROOTS`, contract expansion, more than one write batch, risk,
  or major decision. There is no routine Terra-to-Sol review hop.
- The parent does not make engineering decisions or continuously schedule;
  Sol does not continuously schedule workers. Deployment, destructive action,
  external commitment, and product policy remain user-authorized.

## Terra planner eligibility and identity

The predicate is deterministic and exact: `LEVEL` is L1 or L2;
`OBJECTIVE_FIXED` is true; `BASELINE`, `SCOPE_ROOTS`, and `ACCEPTANCE` are
non-empty; `OPEN_MAJOR_DECISIONS` is false; `RISK_FLAGS` is none;
`EXTERNAL_ACTIONS` is none; `MAX_DISPATCHES` is exactly 1;
`COMPONENT_COUNT` is at most 2; and `DEPENDENCY_DEPTH` is at most 1. A required path outside `SCOPE_ROOTS`, ambiguity, contract expansion, or more than one
write batch fails the predicate and routes directly to Sol; there is no routine Terra-to-Sol review.
`REQUIRED_PATHS`, `WRITE_BATCH_COUNT`, `CONTRACT_EXPANDED`, and `AMBIGUITY`
must be explicit canonical evidence. `PATHS_ALLOW` is a non-empty list of
repository-relative paths inside `SCOPE_ROOTS`; malformed or missing evidence
routes to Sol.

Risk flags are `security`, `privacy`, `public-contract`,
`data-schema-or-migration`, `destructive`, `production`,
`external-commitment`, `license`, `material-compatibility`, `concurrency`,
`irreversible`, and `material-cost` (including material-cost changes). Any
risk-bearing Terra route is invalid; Sol retains L3 and exception authority.

Every finite plan carries `PLAN_ID`, `PLANNER_ROLE`, and
`PLANNER_INSTANCE_ID`; the role is `terra_planner`. One `AGENT_INSTANCE_ID`
has one immutable role lease per `PLAN_ID`. `AUDITOR_INSTANCE_ID` differs from
`PLANNER_INSTANCE_ID` and cannot have planned or implemented that `PLAN_ID`.
Luna validates planner authority and identity in `DISPATCH`; Terra audit stays
independent and read-only.

For an eligible contract Terra may inspect read-only, analyze, issue one bounded
Luna `DISPATCH`, preregister an independent audit, and emit a finite manifest.
It cannot amend after execution, audit, implement, schedule/wait, or request
human authority. A failed predicate routes directly to Sol without routine
Terra-to-Sol review.

## Bounded planning waves

Sol emits a compact `PLAN_MANIFEST` with global invariants and the ready
`DISPATCH_WAVE`; entries declare id, worktree, dependencies, revision, replay,
audit, transitions, routes, and `EXPANSION_GATE`. Terra emits the same finite
shape only after eligibility. The parent requests Sol only at that gate or an
exception and never pre-expands distant work.

## Protocol

Luna may write only after this complete inbound contract (from Sol or an
eligible terra_planner) arrives unchanged:

```text
PROTOCOL: lean-dev-router/v2
STATUS: DISPATCH
TARGET: implementation
DISPATCH_ID: stable unique component/write identifier
PLAN_ID: stable plan identifier
PLANNER_ROLE: sol_planner | terra_planner
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
NEXT: parent
```

Every field is non-empty, paths are repository-relative, and no major decision
remains. `PLAN_ID`, `PLANNER_ROLE`, `PLANNER_INSTANCE_ID`, and
`AUDITOR_INSTANCE_ID` are required planner identity fields; Terra dispatches
must carry all four. Luna rejects missing planner authority/identity, role reuse, risk-bearing
Terra routes, writable profiles, and `FAILURE: missing_dispatch`; a result is
never authorization. A Terra assignment is an ordinary read-only instruction,
not an outbound result envelope.

Every role returns this compact schema:

```text
PROTOCOL: lean-dev-router/v2
AGENT: luna_worker | terra_auditor | terra_planner | sol_planner
STATUS: PASS | BLOCKED | ESCALATE
FAILURE: none | missing_dispatch | scope | verification | dependency | ambiguity | major-decision
REQUEST: none | implementation | technical_resolution | planning_resolution | human_authority
EVIDENCE:
- path: relative/path/to/file
  proof: short diff summary or `command` -> PASS/FAIL
NEXT: parent
SUMMARY: one concise sentence
```

`PASS`, `BLOCKED`, and `ESCALATE` never authorize writes. Evidence may use
`N/A (planning-only)`, `N/A (batch coverage)`, `N/A (scope-check)`, or
`N/A (integration-check)`. Missing fields require `FAILURE: verification`.

The parent applies only this finite table; prose cannot override it:

| AGENT | STATUS | REQUEST | Mechanical destination |
|:---|:---|:---|:---|
| `luna_worker` | `PASS` | `none` | `parent:manifest_gate` |
| `luna_worker` | `BLOCKED` | `none` | `parent:pause` |
| `luna_worker` | `ESCALATE` | `technical_resolution` | `parent:terra` |
| `terra_auditor` | `PASS` | `none` | `parent:manifest_gate` |
| `terra_auditor` | `BLOCKED` | `none` | `parent:pause` |
| `terra_auditor` | `ESCALATE` | `implementation` | `parent:repair_or_sol` |
| `terra_auditor` | `ESCALATE` | `planning_resolution` | `parent:sol` |
| `terra_planner` | `PASS` | `none` | `parent:manifest_gate` |
| `terra_planner` | `BLOCKED` | `none` | `parent:pause` |
| `terra_planner` | `BLOCKED` | `implementation` | `parent:luna` |
| `terra_planner` | `ESCALATE` | `planning_resolution` | `parent:sol` |
| `sol_planner` | `PASS` | `none` | `parent:manifest_gate` |
| `sol_planner` | `BLOCKED` | `none` | `parent:pause` |
| `sol_planner` | `BLOCKED` | `implementation` | `parent:luna` |
| `sol_planner` | `BLOCKED` | `human_authority` | `parent:user` |

## Scope, artifacts, and revision

`PATHS_ALLOW` covers persistent writes only. Build output goes to external
scratch; disposable artifacts are predeclared, cleaned, and never enter revision
identity; retained artifacts never enter revision identity. Retained standard or
ignored untracked paths fail scope. Run:

```text
python scripts/check_scope.py --baseline <baseline> --allow <entry> ... --revision
```

Repeat `--allow` for every entry and record tracked, standard-untracked, and
ignored-untracked results. A clean state uses its exact commit SHA; a dirty state
uses `worktree-sha256:<64 lowercase hex>` over baseline, authorized patches, and
untracked contents. The same state reproduces the same revision; repair changes
it. Reject placeholders and baseline-only dirty keys.

## Risk fuse and replay

Expensive, concurrent, flaky, environment-sensitive, or uncertain gates use
three materially distinct attempts and twenty model-active minutes per failing
gate. External waits are excluded but commands retain timeouts. Do not rerun an
unchanged command without changed state, new evidence, or a new hypothesis.
Replay is cwd, environment delta, exact command, exit code, and compact result.
Baseline drift is a verification failure; missing tools use dependency handling;
unauthorized paths are scope failures.
Concurrent tests must prove the target failure/competition branch; sleep is only
polling or a backstop timeout, never synchronization proof.

## Streaming and preregistered audit

Process independent results as they arrive; only combined integration uses an
all-component barrier. Use `<component>:<revision>:<stage>` keys with
`queued`, `running`, `complete`, or `failed`; retry only missing or failed keys.
The scheduler may reuse one uninvolved Terra only when it creates no sibling
wait. With capacity, start within 60 seconds; otherwise record the reason and
start at the first eligible slot release. Keep events responsive during long parent commands.

Sol or eligible Terra preregisters `TASK_OBJECTIVE`, `CHANGE_SCOPE`, broader `AUDIT_SCOPE/IMPACT_CONE`, acceptance, dependencies, revision/job-key rule,
out-of-scope policy, and replay. After Luna `PASS`, the parent verifies those
gates and starts the preregistered Terra audit directly. Terra planner only
preregisters; it does not launch or schedule the audit. No routine Luna-to-Sol-to-Terra hop is used.

## Terra causal audit and repair

Terra reads the causal impact cone: callers/callees, data/error/resource flow,
configuration, platforms, compatibility, concurrency, security, performance,
and tests. Findings are **A** change-caused acceptance defect, **B** necessary
omitted scope, **C** unrelated existing issue, or **D** severe security,
data-loss, or compatibility risk. Bind each to path, evidence, causality,
severity, blocking decision, and owner.

An unchanged-contract repair returns `CONTRACT_EFFECT: unchanged`, original
`DISPATCH_ID`, `AFFECTED_PATHS` inside `PATHS_ALLOW`, violated acceptance, and
evidence; parent may return it to Luna for the two-cycle repair budget. Scope,
plan, acceptance, public interface, architecture, security boundary, data
format, resource limit, ambiguity, or exhausted budget returns to Sol.

## Integration

Two or more write batches require `integration_worktree`, `integration_owner`,
`integration_baseline`, `integration_paths_allow`, `integration_acceptance`, and
dependency order. The allow-list is the exact union of accepted batches. One
Luna combines commits; conflict resolution is a new authorization. Whole-task
`PASS` requires clean combined state, final scope, full acceptance, and any
declared final audit; component success is not transitive.

## Execution and human gate

Parallel Luna writers use isolated worktrees; read-only Terra may share one.
Pool caps are token-first 3, balanced 6, latency-first 10. If nested spawning is
unavailable, Sol returns `BLOCKED/dependency/REQUEST implementation` with the
literal manifest for parent relay; the parent never replans.

Sol decides reversible technical choices within fixed bounds. Sol uses REQUEST human_authority for user-owned choices. Objective, scope,
acceptance, policy, material compatibility/security/privacy/license/migration/
cost, or product commitments return `BLOCKED/major-decision/REQUEST
human_authority` with at most three options, one recommendation, and one
question (one question only). Stop when all declared gates pass; do not invoke every role by default.
