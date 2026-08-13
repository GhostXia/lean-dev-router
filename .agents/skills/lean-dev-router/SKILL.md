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
- Contract-declared dependency prep is Luna-only; parent/Terra never run
  undeclared, missing, or out-of-contract tools/dependencies: zero-execution ->
  Luna `ESCALATE`/`technical_resolution` -> `parent:terra`, never `BLOCKED/none`.

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

The parent relays it unchanged. Fields are non-empty, IDs stable, paths relative,
and no major decision remains. Terra assignments are read-only instructions, not an outbound result envelope or `STATUS: DISPATCH`; missing authorization returns
`FAILURE: missing_dispatch` with no implementation.

Roles return one result schema:

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
| `sol_planner` | `BLOCKED` | `execution` | `parent:luna` |
| `sol_planner` | `BLOCKED` | `human_authority` | `parent:user` |

## Scope, artifacts, and revision

`PATHS_ALLOW` authorizes persistent writes only. Build output uses external
scratch. A predeclared disposable root must be absent/clean at preflight and
removed before scope; retained/undeclared paths fail and artifacts never enter
revision identity.

Verify every allow entry together with:

```text
python scripts/check_scope.py --baseline <baseline> --allow <entry> ... --revision
```

Repeat `--allow <paths_allow_entry>` per entry; the helper checks tracked,
standard-untracked, and ignored-untracked paths. If unavailable, run the three
Git enumerations; missing/failed scope evidence rejects `PASS`.

After scope, clean state uses its exact commit SHA; dirty state uses
`worktree-sha256:<64 lowercase hex>` over baseline, authorized tracked binary
diffs, and framed authorized untracked paths/content. Equal state reproduces
equal revision; repairs change it. Reject placeholders and baseline-only keys.

## Risk fuse and replay

Before first Luna, parent passes the DISPATCH once to
`<skill-dir>/scripts/runtime_guard.py start --state <external-scratch-state>`.
Use `execution` for the initial Luna call or a bounded no-product retry, then use
`repair`/`audit` against that state; never restart it. Exit 2 means zero target calls.
`BUDGET` is a hard budget per role/stage with ceilings of 8 calls,
4 hypotheses, 1200 active seconds, 2 repairs, and 2 stagnant calls; Sol may only
tighten them. Tool/external waits are excluded, but commands keep timeouts.

Each `event` records identity, revision/stage, calls, timing, attempts,
token/cache families, hypothesis, command/error, progress/evidence, and termination;
guard derives uncached/total tokens. Unchanged failure stops; two stagnant calls
are deterministic `spinning`. A stop latches until revision, contract, or evidence changes.
Luna exhaustion routes Terra; Terra exhaustion routes Sol; Parent never repairs/writes.

Within the limit, never rerun unchanged commands: technical uncertainty requests
`technical_resolution`, missing tools use dependency handling, unauthorized writes
are scope failures, and baseline drift stops writes. Replay includes cwd, exact
command, exit code, and compact result; pre-PASS diagnosis carries `DISPATCH_ID`,
diff/paths, attempts, contract bounds, and remaining budget.

`parent:pause` is zero-execution: parent must not run `npm ci`, install tools,
mutate environment, clear latch, or resume Luna.

Initial execution is the only `sol_planner/BLOCKED/execution` route: it uses an
unchanged-DISPATCH and matching telemetry. The guard allows two sequential attempts
only when the clean BASELINE and fingerprint are unchanged and the prior attempt
produced zero product; non-sequential, exhausted, dirty/changed, evidence-bearing,
repaired, audited, or dependency-changing retries return to Sol.

## Streaming and preregistered audit

Process independent results as they arrive; only combined integration uses an
all-component barrier. Stable `<component>:<revision>:<stage>` keys are
`queued`/`running`/`complete`/`failed`; retry missing/failed keys. `token-first`
may reuse one uninvolved Terra without sibling wait. With capacity, start within
60 seconds; otherwise record queue and start at first eligible slot release.
Consume events during long commands and report external waits separately.

Sol preregisters each audit with `DISPATCH_ID`, component/dependencies, revision/job
rule, objective, scope, impact cone, acceptance, replay, and policy. Terra starts
only after matching Luna `PASS`, dispatch identity, concrete revision, scope and replay evidence, explicit unchanged dependencies, and telemetry. Missing execution/product returns
`REQUEST: execution` to `parent:luna`; partial/contradictory evidence or contract/
contract/dependency updates return Sol without launching Terra.
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

For a contract-preserving A-class repair Terra returns `REQUEST: implementation`
only after the final-audit prerequisites pass, with
the original `DISPATCH_ID`, preregistered `AUDITOR_INSTANCE_ID`,
`CONTRACT_EFFECT: unchanged`, `AFFECTED_PATHS`
inside `PATHS_ALLOW`, violated acceptance, and bounded repair evidence. Parent
matches the ID to Luna evidence and the preregistered audit, checks those facts
and the default two-cycle repair budget, then mechanically
returns the original Luna. The new state gets a new revision and re-audit.
Any change to scope, plan, acceptance, constraints, public interface,
architecture, security boundary, data format, resource limit, or an ambiguous
or exhausted repair returns to Sol. Terra never writes the repair itself.

Terra never installs/runs tools or mutates environment. dependency changes return to Sol. `ESCALATE`/`implementation`
is repair-only; initial execution and no-product retry use `REQUEST: execution`.
Technical-resolution advice returns `ESCALATE`/`implementation` only when
unchanged; contract/dependency changes and ambiguous evidence return
`ESCALATE`/`planning_resolution` -> `parent:sol`.

## Integration

Two or more write batches require shared contracts, dependency order,
`integration_worktree`, `integration_owner`, `integration_baseline`,
`integration_paths_allow`, and `integration_acceptance`; conflicts need new Luna
authorization. Whole-task `PASS` requires clean combined state, final scope,
acceptance, and final audit.

## Execution and human gate

Parallel Luna writers use isolated worktrees; read-only Terra may share a
checkout. Pool caps are token-first 3, balanced 6, latency-first 10. If Sol
cannot spawn nested workers, it returns
`BLOCKED/dependency/REQUEST execution` with the literal manifest; parent relays.

Sol decides only reversible technical trade-offs within the fixed contract.
Objective, scope, acceptance, policy, material compatibility/security/privacy/
license/migration/cost, or product commitments require
`BLOCKED/major-decision/REQUEST human_authority`. Sol supplies at most three
options, one recommendation, and one question; the parent presents it without
translating the user's answer into a contract.

Stop when manifest, scope, revision, audit, repair, integration, and final gates
are terminal; parent may summarize without another Sol call. Do not repeat stages
without changed evidence or let Luna/Terra orchestrate peers.
