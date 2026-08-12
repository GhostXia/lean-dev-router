---
name: lean-dev-router
description: Route repository-bound engineering through Sol planning, parent scheduling, Luna implementation, and Terra causal audit with compact auditable handoffs.
---

# Lean Dev Router

Use the smallest pool. Sol plans; parent schedules; Luna writes; Terra audits.

## Language

Follow the task's primary/dominant language; absent a signal, use English. Keep
code, commands, paths, model IDs, and agent names unchanged.

## Authority and entry

- Changes start with `sol_planner`, which fixes objective, scope, acceptance,
  dependencies, budgets, contracts, audits, and routes. Only Sol authors/amends
  `DISPATCH` or requests human authority.
- Sol does not continuously schedule, wait on workers, or consolidate routine
  events. The parent executes the declared state machine without engineering
  judgment. Undefined, incomplete, or contract-changing states return to Sol.
- Sol fixes measurable bounds, retryable states, and public/data/security
  invariants; Luna retains equivalent local implementation choices.
- `luna_worker` implements only a valid contract and makes only local choices
  that preserve it. `terra_auditor` is read-only and supplies causal evidence,
  audit findings, and bounded repair advice; it never authorizes a write.
- Audits/diagnosis may start with Terra; planning or authorization returns Sol.
- Deployment, destructive action, external commitment, and product policy are
  outside this routing authority unless the user explicitly authorizes them.

## Bounded planning waves

Sol emits `PLAN_MANIFEST` invariants plus ready `DISPATCH_WAVE`; entries declare
worktree, dependencies, revision, replay, audit, routes, and `EXPANSION_GATE`.
Parent requests Sol only at that gate or exception; do not pre-expand work.

## Protocol

Luna may write only after receiving this complete inbound contract:

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

The parent relays it unchanged. Every field is non-empty, IDs are stable,
planner and auditor identities differ, paths are repository-relative, and no
major decision remains. A Terra assignment is an ordinary
read-only instruction, not an outbound result envelope (only Luna write
authorization) and never `STATUS: DISPATCH`. Missing authorization makes Luna
perform no implementation and return `FAILURE: missing_dispatch`.

Roles return one result schema:

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

`PASS`, `BLOCKED`, and `ESCALATE` never authorize writes. Evidence may use
`N/A (planning-only)`, `N/A (batch coverage)`, `N/A (scope-check)`, or
`N/A (integration-check)`. If required fields or evidence are missing, the
originating role corrects its result with `FAILURE: verification`.

The parent applies these mechanical actions; prose cannot override them:

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

## Scope, artifacts, and revision

`PATHS_ALLOW` authorizes persistent writes only. Build output goes to external
scratch. A disposable artifact root must be predeclared, absent or clean at
preflight, and removed before scope passes. Retained or undeclared standard or
ignored untracked paths fail; artifacts never enter revision identity.

Verify every allow entry together with:

```text
python scripts/check_scope.py --baseline <baseline> --allow <entry> ... --revision
```

Use a repeated `--allow <paths_allow_entry>` flag for each entry. The helper
checks tracked, standard-untracked, and ignored-untracked paths. If the helper
is unavailable, run the documented three Git enumerations and do not invent a
dirty revision. Missing or failed scope evidence rejects `PASS`.

After scope passes, resolve state. A clean committed state
uses its exact commit SHA. A dirty state uses
`worktree-sha256:<64 lowercase hex>` over the resolved baseline, authorized
tracked binary diffs, and authorized untracked path/content with safe framing.
The same state reproduces the same revision; any repair changes it. Reject
placeholders such as `<luna-revision>` and baseline-only dirty keys.

## Risk fuse and replay

Before first Luna, parent passes the DISPATCH once to
`<skill-dir>/scripts/runtime_guard.py start --state <external-scratch-state>`.
Use `repair`/`audit` against that state; never restart it. Exit 2 means zero target calls.
`BUDGET` is a hard budget per role/stage with ceilings of 8 calls,
4 hypotheses, 1200 active seconds, 2 repairs, and 2 stagnant calls; Sol may only
tighten them. Tool/external waits are excluded, but commands keep timeouts.

Each `event` records identity, revision/stage, calls, wall/active time, upstream
attempts, all token/cache families, hypothesis, command/error, progress/evidence,
and termination. The guard derives uncached and total tokens. Repeated failure
without changed progress stops; two stagnant calls are the deterministic `spinning` signal.
A stop latches until revision, contract, or evidence changes. Luna exhaustion
routes Terra; Terra exhaustion routes Sol. Parent never repairs or writes after
Luna failure/interruption.

Within the limit use at most three distinct attempts per failing gate; never
rerun an unchanged command without changed state, evidence, or hypothesis.
Technical uncertainty requests `technical_resolution`; missing tools use
dependency handling; unauthorized writes are scope failures; Baseline drift is
verification failure. Replay is cwd, environment delta, exact command, exit code, and compact result.
Pre-PASS diagnosis also carries `DISPATCH_ID`, current
diff/paths, attempts, contract bounds, and remaining budget. Concurrent tests
must prove the target failure/competition branch; sleep is only polling or a backstop timeout,
never synchronization proof.

## Streaming and preregistered audit

Process each independent component result as it arrives; never wait for
unrelated siblings. Only combined integration uses an all-component barrier.
Use stable `<component>:<revision>:<stage>` job keys with `queued`, `running`,
`complete`, or `failed`; retry only missing or failed keys. `token-first` may
reuse one uninvolved Terra but cannot create a sibling wait. When timestamps
exist, start within 60 seconds if capacity exists, otherwise record the queue
reason and start at the first eligible slot release. Keep event consumption
responsive during long parent commands and report external waits separately.

Sol preregisters each audit with the same `DISPATCH_ID`, component,
dependencies, revision/job-key
rule, `TASK_OBJECTIVE`, `CHANGE_SCOPE`, broader `AUDIT_SCOPE/IMPACT_CONE`,
acceptance, replay evidence, and out-of-scope policy. After Luna `PASS`, the
parent verifies scope, concrete revision, dependencies, replay, and audit
contract, then launches Terra directly. No routine Luna-to-Sol-to-Terra hop is
required. An incomplete or undefined precondition returns to Sol.
Register via `runtime_guard.py audit`; the same revision is never repeated.
First audit is full; later revisions cover delta and findings.
On early termination, parent records `ACTION: abandon` and reason, routes to
Sol, and never updates the incremental-audit baseline.

## Terra causal audit and repair

Terra reads beyond `PATHS_ALLOW` through the causal impact cone: callers and
callees, data/error/resource flow, configuration, platforms, compatibility,
concurrency, security, performance, and tests. This is broader read scope, not
write authority or unbounded repository scanning. Outside findings include
path, evidence, causality, severity, blocking decision, and ownership:

- **A**: change-caused acceptance defect; block and repair.
- **B**: necessary path omitted from scope; return to Sol.
- **C**: unrelated existing defect; normally non-blocking follow-up.
- **D**: severe security, data-loss, or compatibility risk; block/escalate.

For a contract-preserving repair Terra returns `REQUEST: implementation` with
the original `DISPATCH_ID`, preregistered `AUDITOR_INSTANCE_ID`,
`CONTRACT_EFFECT: unchanged`, `AFFECTED_PATHS`
inside `PATHS_ALLOW`, violated acceptance, and bounded repair evidence. Parent
matches the ID to Luna evidence and the preregistered audit, checks those facts
and the default two-cycle repair budget, then mechanically
returns the original Luna. The new state gets a new revision and re-audit.
Any change to scope, plan, acceptance, constraints, public interface,
architecture, security boundary, data format, resource limit, or an ambiguous
or exhausted repair returns to Sol. Terra never writes the repair itself.

## Integration

Two or more write batches require shared contracts, dependency order,
`integration_worktree`, `integration_owner`, `integration_baseline`,
`integration_paths_allow`, and `integration_acceptance`. The allow-list starts
as the exact union of accepted batches. One Luna combines accepted commits;
conflict resolution is a new authorized write. Whole-task `PASS` requires a
clean combined state, final scope, full acceptance, and any declared final
audit. Component success is not transitive.

## Execution and human gate

Parallel Luna writers use isolated worktrees; read-only Terra may share a
checkout. Default pool caps are token-first 3, balanced 6, latency-first 10.
If Sol cannot spawn nested workers, it returns
`BLOCKED/dependency/REQUEST implementation` with the literal manifest so the
parent can relay it mechanically; the parent fallback never replans.

Sol decides only reversible technical trade-offs within the fixed contract.
Objective, scope, acceptance, policy, material compatibility/security/privacy/
license/migration/cost, or product commitments require
`BLOCKED/major-decision/REQUEST human_authority`. Sol supplies at most three
options, one recommendation, and one question; the parent presents it without
translating the user's answer into a contract.

Stop when all manifest states, scope, revision, audit, repair, integration, and
final gates are terminal. When every declared terminal gate passes, the parent
may summarize completion without another Sol call. Do not invoke every role by
default, repeat a stage without changed evidence, or let Luna or Terra
orchestrate peers.
