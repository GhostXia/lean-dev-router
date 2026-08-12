---
name: lean-dev-router
description: Route repository engineering through deterministic Terra planning, Sol exceptions, Luna implementation, and independent Terra audit.
---

# Lean Dev Router

Use the smallest pool. Parent schedules; Luna writes; Terra audits; Sol owns exceptions.

## Language

Follow the parent task's primary language; when unspecified, use its dominant
language. Use English when no natural-language signal exists. Keep code,
commands, paths, model IDs, and agent names unchanged.

## Authority and entry

- Start changes with one read-only `terra_planner` classification derived from
  the objective and repository. Eligible work continues there; failure routes
  directly to Sol. Parent does not classify.
- `terra_planner` directly replaces routine Sol planning only for the exact
  eligible L1/L2 predicate below. It is read-only, cannot schedule or wait,
  implement, audit, amend after execution, or request `human_authority`.
- `sol_planner` plans every failed predicate, L3 task, ambiguity, required path
  outside `SCOPE_ROOTS`, contract expansion, more than one write batch, risk,
  or major decision. There is no routine Terra-to-Sol review hop.
- Parent makes no engineering decisions; Sol does not continuously schedule.
  Deployment, destructive action, external commitment, and policy remain user-authorized.

## Terra planner eligibility and identity

The predicate is deterministic and exact: `LEVEL` is L1 or L2;
`OBJECTIVE_FIXED` is true; `BASELINE`, `SCOPE_ROOTS`, and `ACCEPTANCE` are
non-empty; `OPEN_MAJOR_DECISIONS` is false; `RISK_FLAGS` is none;
`EXTERNAL_ACTIONS` is none; `MAX_DISPATCHES` is exactly 1;
`COMPONENT_COUNT` is 1 or 2; and `DEPENDENCY_DEPTH` is at most 1. A required path outside `SCOPE_ROOTS`, ambiguity, contract expansion, or more than one
write batch fails the predicate and routes directly to Sol; there is no routine Terra-to-Sol review.
`REQUIRED_PATHS`, `WRITE_BATCH_COUNT`, `CONTRACT_EXPANDED`, and `AMBIGUITY`
must be explicit canonical evidence. `PATHS_ALLOW` is a non-empty list of
repository-relative paths inside `SCOPE_ROOTS`; malformed or missing evidence
routes to Sol.

Risk flags: `security`, `privacy`, `public-contract`,
`data-schema-or-migration`, `destructive`, `production`,
`external-commitment`, `license`, `material-compatibility`, `concurrency`,
`irreversible`, and `material-cost`. Risk routes are invalid; Sol owns L3/exceptions.

Every plan carries `PLAN_ID`, `PLANNER_ROLE`, and `PLANNER_INSTANCE_ID`; the
role is `terra_planner`. One `AGENT_INSTANCE_ID`
has one immutable role lease per `PLAN_ID`. `AUDITOR_INSTANCE_ID` differs from
`PLANNER_INSTANCE_ID` and cannot have planned or implemented that `PLAN_ID`.
Luna validates planner authority and identity in `DISPATCH`; Terra audit stays
independent and read-only.

Eligible Terra may inspect, issue one Luna `DISPATCH`, preregister an audit,
and emit a finite manifest. It cannot implement, audit,
schedule/wait, amend after execution, or request authority.

## Bounded planning waves

Sol emits `PLAN_MANIFEST` invariants plus ready `DISPATCH_WAVE`; entries declare
worktree, dependencies, revision, replay, audit, routes, and `EXPANSION_GATE`.
Eligible Terra emits the same finite shape. Parent never pre-expands work.

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
BUDGET:
  MODEL_CALL_LIMIT: positive integer
  HYPOTHESIS_LIMIT: positive integer
  MODEL_ACTIVE_SECONDS_LIMIT: positive integer
  REPAIR_CYCLE_LIMIT: positive integer
  STAGNANT_CALL_LIMIT: positive integer
NEXT: parent
```

Every field is non-empty, paths are repository-relative, and no major decision
remains. Planner/auditor identity fields are required. Luna rejects missing
authority, role reuse, risk-bearing Terra routes, or writable profiles with
`FAILURE: missing_dispatch`; results never authorize writes. A Terra assignment
is a read-only instruction, not an outbound result envelope.

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

Before the first Luna call, parent passes the complete DISPATCH once to
`<skill-dir>/scripts/runtime_guard.py start --state <external-scratch-state>`.
Use `event`, `repair`, and `audit` against that state; never restart it.
Exit 2 means zero target calls. The guard validates Sol dispatches and the exact
eligible Terra fast path before spawning.

`BUDGET` is a hard budget per role/stage: at most 8 calls, 4 hypotheses, 1200
model-active seconds, 2 repairs, and 2 stagnant calls; a planner may only
shrink it. Every call records tokens/cache, time, attempts, progress, and outcome.
Repeated failure without progress stops; two stagnant calls are the
deterministic `spinning` signal. A stop latches until revision, contract, or
evidence changes. Parent never repairs or writes after Luna failure.

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

Sol or eligible Terra preregisters the same `DISPATCH_ID`, `TASK_OBJECTIVE`,
`CHANGE_SCOPE`, broader `AUDIT_SCOPE/IMPACT_CONE`, acceptance, dependencies,
revision/job-key rule, out-of-scope policy, replay, and the same or tighter
`BUDGET`. After Luna `PASS`, the parent verifies those
gates and starts the preregistered Terra audit directly. Terra planner only
preregisters; it does not launch or schedule the audit. No routine Luna-to-Sol-to-Terra hop is used.
Register each audit through `runtime_guard.py audit`; the same revision is never
repeated. First audit is full; later revisions cover delta and findings. On
early termination, parent records `ACTION: abandon` and reason, routes to Sol,
and never updates the incremental-audit baseline.

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
