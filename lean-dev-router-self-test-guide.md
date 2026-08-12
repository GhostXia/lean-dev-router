# Lean Dev Router — Self-Test Guide

**Purpose:** Help you measure, on your own machine and codebase, whether `lean-dev-router` reduces token usage across task difficulties, and whether engineering quality degrades compared with direct Sol or direct Luna runs.

This guide is intentionally practical. It does **not** claim savings in advance. Your numbers are the source of truth.

---

## 1. What You Are Testing

You will compare three setups on the same tasks:

| Group | Setup | Intent |
|-------|--------|--------|
| **A. Direct Sol** | `gpt-5.6-sol` only at a fixed **medium** reasoning effort for the primary comparison. No lean-dev-router. | Strong baseline for quality and cost of “just use Sol”. |
| **B. Direct Luna** | `gpt-5.6-luna` only (max). No routing skill. | Cheap baseline; may fail more on ambiguous work. |
| **C. Lean Router** | `$lean-dev-router` with `terra_planner`, `sol_planner`, `luna_worker`, `terra_auditor`, plus a fixed controller model/effort chosen before testing. Eligible L1/L2 runs start with Terra's finite plan; failed predicates and L3 start with Sol. For a cost-focused run, `gpt-5.6-luna` + `high` is a reasonable controller default. | The system under test. |

Optional later (do **not** mix into the primary comparison):

| Group | Setup |
|-------|--------|
| **D. Lean + Caveman** | Lean Router plus response-compression skill |

Do not vary the Direct Sol reasoning effort inside the primary dataset. If you also want a high-effort quality ceiling, run it as a separate **A-high** comparison and do not mix it with Group A.

Primary questions:

1. How much token (or proxy) cost does Lean save vs Direct Sol at L1 / L2 / L3 difficulty?
2. Does Lean pass the same acceptance checks with comparable engineering quality?

---

## 2. Prerequisites

- A Codex environment that can load custom agents and skills.
- `lean-dev-router` installed as documented by the project (skill + four agent TOML files).
- A git repo you can branch and reset safely.
- Ability to run your project’s tests or verification commands.
- Preferably a usage panel that shows input/output tokens. If not available, use the proxy metrics in §5.
- Record the Codex surface and version for every experiment (for example, `codex --version`; if the CLI is unavailable, record the app/package version and say so).
- Pin the controller model and reasoning effort before the experiment. For Group C, record the controller plus every subagent's effective model and effort; do not change them per task.
- Use one disposable worktree or clone per run. Do not run the experiment on a working directory containing unrelated changes.

**Disable other skills** (including Caveman) during Groups A–C so the comparison stays clean.

---

## 3. Difficulty Tiers

Use at least **two tasks per tier** (six tasks total recommended). For a quantitative conclusion, repeat each task/group cell at least twice; treat a single run per cell as a pilot only because model and tool behavior is nondeterministic.

| Tier | Characteristics | Example task shapes |
|------|-----------------|---------------------|
| **L1 — Simple** | Single file or tiny surface; clear acceptance; almost no architecture choice | Add input validation; fix an obvious logic bug; add one unit test |
| **L2 — Medium** | 2–5 files; local design choices; tests required | Add an optional API field end-to-end; unify error handling on one path |
| **L3 — Complex** | Cross-module; compatibility, security, migration, or concurrency risk | Change a public interface with compatibility; fix a race; add rate limiting |

Choose tasks from **your** codebase when possible. Synthetic demos are acceptable if the acceptance criteria are objective.

---

## 4. Standard Task Packet (Required)

Every task must use the same packet structure so prompt length does not bias one group.

```text
[Goal]
One-sentence desired outcome.

[Scope]
Allowed files / paths.
Forbidden files / paths.

[Constraints]
Language, style, dependencies, compatibility rules, whether new dependencies are allowed.

[Acceptance]
Exact commands to run and expected outcomes. Must be objectively checkable.

[Forbidden]
Unrelated refactors, scope expansion, drive-by cleanup.

[Baseline]
Starting commit hash: <hash>
```

For every write run, capture the baseline commit and allowed paths before Luna starts. In Group C, the authorized planner places them with task summary, planner identity, objective acceptance, and fixed constraints in a standard inbound `DISPATCH`; the parent may relay but not author or amend it. In a direct-Luna Group B run, the parent supplies the packet because the router is not in use. Paths needed only for reading remain context and do not become write authorization.

In Group C, include exact model-call, hypothesis, model-active, repair, and stagnation budgets. Run the installed Skill's `scripts/runtime_guard.py start` before spawning Luna and record every subsequent model call as an event.

### Example (L2)

```text
[Goal]
Add an optional `note` field to POST /api/orders and wire validation + tests.

[Scope]
handlers/orders.go, service/order.go, tests/order_test.go

[Constraints]
No DB schema change. `note` max length 200. Invalid note returns HTTP 400.

[Acceptance]
go test ./... -run Order
Invalid note must return 400.

[Forbidden]
Refactor unrelated modules. Change other API fields.

[Baseline]
abc1234
```

---

## 4.1 Codex Runtime and Routing Controls

For Group C, use native Codex subagents as the default path. Start with one
read-only terra_planner classification; Terra derives the canonical eligibility
evidence from the objective and repository, while the parent only relays it. A mechanically eligible L1/L2 task uses one
read-only `terra_planner` call, one bounded Luna `DISPATCH`, and an independent
Terra audit; a failed predicate, L3, ambiguity, risk, expansion, outside path,
or second write batch routes directly to `sol_planner` with no routine
Terra-to-Sol review. Keep dependent stages sequential. Independent read-only
work may share a checkout; independent Luna writes may run in parallel only
when each writer has a dedicated worktree or independent checkout and branch.
Never let multiple agents write to the same worktree.

Before a dependent or write handoff, verify that the intended Agent loaded, its configured model and reasoning effort are honored, and the first result follows `lean-dev-router/v2`. In the CLI, use `/agent` to inspect agent threads; when available, record `codex --version` before the run.

If native spawning is unavailable or the custom Agent configuration is not honored, use one independent Codex session per role as a fallback. Pass only the compact handoff, relevant paths, constraints, and evidence. Use an isolated worktree or branch for writes and record the fallback in the results.

Do not treat an unrelated background process or session as equivalent to native parent-child routing. Do not silently substitute the default agent or model. See the [official Codex subagents documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents) when the client behavior is unclear.

### 4.2 Terra planner eligibility and independence checks

Record the eligibility packet before the first agent call. Terra is eligible only
when `LEVEL` is L1/L2, `OBJECTIVE_FIXED` is true, `BASELINE`, `SCOPE_ROOTS`, and
`ACCEPTANCE` are non-empty, `OPEN_MAJOR_DECISIONS` is false, `RISK_FLAGS` and
`EXTERNAL_ACTIONS` are none, `MAX_DISPATCHES` is 1, `COMPONENT_COUNT` is at
most 2, and `DEPENDENCY_DEPTH` is at most 1. `REQUIRED_PATHS`,
`WRITE_BATCH_COUNT`, `CONTRACT_EXPANDED`, and `AMBIGUITY` must also be present
canonically; `REQUIRED_PATHS` may be explicitly empty, while the latter three
must be exactly `1`, `false`, and `false` respectively.
`PATHS_ALLOW` must be a non-empty repository-relative list, and every allowed
or required path must stay inside the repository-relative `SCOPE_ROOTS` list.
Malformed scalar or absolute-path evidence routes to Sol without throwing. The risk set is security, privacy,
public-contract, data-schema-or-migration, destructive, production,
external-commitment, license, material-compatibility, concurrency, irreversible,
and material-cost changes. A required path outside `SCOPE_ROOTS`, ambiguity,
contract expansion, or more than one write batch must route directly to Sol.

For every eligible plan, record `PLAN_ID`, `PLANNER_ROLE`,
`PLANNER_INSTANCE_ID`, and a different `AUDITOR_INSTANCE_ID`. Verify that one
`AGENT_INSTANCE_ID` has one immutable role lease per `PLAN_ID`, and that the
auditor identity has neither planned nor implemented that plan. Luna must reject
missing planner identity, risk-bearing Terra routes, writable Terra profiles,
and `human_authority` requests. Terra may inspect and analyze read-only, issue
one bounded Luna `DISPATCH`, preregister the independent audit, and emit a finite
manifest; it cannot schedule, wait, implement, audit, amend after execution, or
request authority. The valid Terra handoffs are only `PASS/none`, `BLOCKED/none`,
`BLOCKED/implementation`, and `ESCALATE/planning_resolution`.

Run negative controls by changing one predicate at a time (L3, an empty field,
each risk flag, `MAX_DISPATCHES=2`, a third component, depth 2, an outside path,
or a reused role identity). The result must be direct `sol_planner`; do not add a
routine Terra-to-Sol review call. Keep these controls separate from acceptance
task costs and report them with the same replay evidence.

### 4.3 Runtime budget and spinning controls

Use an external scratch state file. Confirm an incomplete dispatch exits 2 with
zero child calls. Verify that call, hypothesis, active-time, repair, and stagnant
ceilings cannot be raised or exceeded; repeated failure without changed progress
stops; a stopped stage needs changed revision, contract, or evidence; parent and
Terra writes are rejected; duplicate audit revisions do not run; and abandoned
audits do not become incremental baselines.

## 5. Metrics

### 5.1 Cost / token metrics

Prefer real usage numbers when Codex exposes them.

Count the complete run: parent session plus every child Agent/session. Do not compare only the visible parent-thread tokens against the full cost of a routed run. Record the effective model and reasoning effort for each call, not only the configured target.

| Metric | How to record |
|--------|----------------|
| Input tokens | From usage UI / logs |
| Cached / cache-creation input | Record separately; derive uncached input |
| Output tokens | From usage UI / logs |
| Reasoning output tokens | From usage UI / logs |
| Wall / model-active seconds | Per role and stage |
| Upstream attempts / termination | From guard snapshot |
| Total tokens | Input + output |
| Turns | Number of user/agent exchanges until delivery |
| Agent calls | Count of Terra planner / Sol / Luna / Terra auditor invocations |
| Escalations | Luna → Terra auditor, Terra planner or auditor → Sol only when the predicate or audit requires it |
| Diff size | `git diff --stat` at the end |

**If token counts are unavailable**, use consistent proxies for all groups:

- total turns
- number of tool calls
- approximate output character count of agent replies
- agent call counts
- protocol violations or fallback-session calls

Do not mix real tokens and proxies in the same summary table.

For aggregation, report both the mean per-task savings and the ratio of tier totals:

```text
Tier-total savings = 1 - (sum of Lean costs for the tier / sum of Sol costs for the tier)
```

Do not average away a failed acceptance check or a quality regression.

### 5.2 Quality metrics (score 0–2 each; max 12)

| Dimension | 2 | 1 | 0 |
|-----------|---|---|---|
| **Correctness** | All acceptance checks pass | Partial pass | Fail |
| **Scope control** | Only allowed files touched | Minor out-of-scope noise | Clear scope expansion |
| **Tests** | Needed tests present and passing | Weak / incomplete tests | Missing relevant tests |
| **Safety / boundaries** | No obvious safety or boundary issues | Minor issue | Clear vulnerability or bad boundary handling |
| **Maintainability** | Clear, minimal change | Readable but messy | Confusing or harmful structure |
| **Completeness** | Delivered as specified | Runnable but incomplete write-up | Half-finished |

**Quality degradation rule of thumb**

- Lean score ≥ Sol score − 1 **and** acceptance passes → no meaningful degradation
- Lean score ≤ Sol score − 2 **or** acceptance fails → quality risk
- On L3, frequent escalations with total cost near Sol → limited savings (expected finding, not a protocol failure)

---

## 6. Execution Protocol

Repeat this for **each task × each group**.

### Step 0 — Prepare

1. Create a **disposable worktree or clone** and a branch named by task and group, e.g. `test/l2-orders-note-A`.
2. Record the baseline commit hash and confirm the worktree starts clean with `git status --short`.
3. Record the Codex surface/version, effective model/effort settings, and active optional skills. Confirm other compression/routing skills are off for A–C.
4. Prepare an empty row in your results sheet.

### Step 1 — Issue the task

Paste **only** the standard task packet.

- **Group A:** Instruct the session to use Sol only; do not invoke lean-dev-router.
- **Group B:** Instruct the session to use Luna only; do not invoke lean-dev-router.
- **Group C:** Instruct the parent session to use `$lean-dev-router`, native subagents, and its routing / compact handoff rules. If native routing falls back to independent sessions, record that fact.

Do not give Group C extra coaching that Groups A/B do not receive.

### Step 2 — Record process data

While the run proceeds, log:

- which agent is active
- effective model and reasoning effort for each call
- native subagent or independent-session fallback
- whether an escalation occurred
- whether each handoff followed `lean-dev-router/v2`
- whether handoffs looked compact / normal / verbose
- whether Sol used Todo/`DISPATCH` to produce independently verifiable, path-bounded batches without needless fragmentation
- for multi-batch deliverables, whether Sol declared shared contracts, integration owner/order/baseline/allow-list, one clean integration state, final integration acceptance, and the Terra-review trigger
- repeated file exploration or duplicated analysis

### Step 3 — Accept or reject

Run the acceptance commands from the packet. Pass/fail must come from commands, not impression.

```bash
git status --short
git diff --stat <baseline-commit>
git diff --name-only --no-renames <baseline-commit> --
git ls-files --others --exclude-standard
git ls-files --others --ignored --exclude-standard
# then the acceptance commands from the packet
```

For each Group C Luna write batch, verify every tracked, standard untracked, and ignored untracked path is covered by its `paths_allow`. Do not accept a reported `PASS` when an extra path exists; record `FAILURE: scope` and the extra paths. Do not silently ignore snapshots, lockfiles, generated files, or formatter output. `git diff --stat` alone is insufficient because it does not show untracked files.

For a Group C task with two or more write batches, treat each component `PASS` as batch-local. Sol assigns one Luna as `integration_owner`; a parent fallback may perform only conflict-free mechanical merges. Integrate accepted batches into one clean worktree in dependency order, record the exact combined commit, and run `integration_acceptance` against that state. Verify tracked paths from `integration_baseline` to the combined commit plus all standard and ignored untracked paths against `integration_paths_allow`, the exact union of accepted batch allow-lists plus any separately authorized integration-repair paths. Record final scope as `path: N/A (scope-check)` and combined-state acceptance as `path: N/A (integration-check)`.

Assign a final Terra integration audit when the user requested independent verification, two or more component batches received Terra verification, or integration crosses a material security, data, concurrency, compatibility, migration, or public-contract boundary. Separate component audits are insufficient when this trigger applies.

### Step 4 — Score quality

Fill the six quality dimensions and write a one-line note if anything failed.

### Step 4a — Negative scope-drift control

Run this once for Group C in a disposable worktree to verify the gate itself:

1. Complete a write batch whose acceptance commands pass and whose declared `paths_allow` contains only the intended files.
2. Add one harmless tracked, standard untracked, or ignored untracked fixture outside `paths_allow` without changing the acceptance result; exercise all three classes across control runs.
3. Confirm the acceptance commands still pass.
4. Run the tracked, standard untracked, and ignored untracked path checks from Step 3.
5. Require the coordinator to reject clean `PASS`, record `FAILURE: scope`, and identify the fixture path. Terra must not be called merely because an obvious extra path exists.

The negative control passes only when green tests plus an extra path are treated as scope drift. Remove the disposable worktree during reset; do not inject this fixture into a valuable checkout.

### Step 4b — Multi-batch integration control

Run this once for Group C with a task whose deliverable is split across at least two isolated write batches:

1. Define one shared contract, explicit dependency order, `integration_worktree`, `integration_owner`, `integration_baseline`, `integration_paths_allow`, `integration_acceptance`, and the Terra-review trigger before dispatch.
2. Make each batch pass its own acceptance and any assigned component audit.
3. Integrate batches incrementally into the clean integration worktree and run the narrow cross-batch check after each merge or wave.
4. Confirm the integration worktree is clean and the combined tracked, standard untracked, and ignored untracked path set is contained in `integration_paths_allow`.
5. Run complete integration acceptance against the final combined commit and, when triggered, run one final Terra audit on that state.
6. Confirm the coordinator rejects whole-task `PASS` if final scope or combined-state acceptance fails, even when every component passed independently.
7. Confirm the failure is reduced to the earliest failing merge or wave and routed to Luna, Terra, Sol, or the user according to cause and authority.

The control passes only when component success and integration success are recorded separately and only combined-state evidence can close the whole task.

### Step 5 — Reset

Prefer deleting the disposable worktree or clone and recreating it from the same baseline. If you reuse one, run the following only after confirming it contains no user changes:

```bash
git status --short
git reset --hard <baseline-commit>
```

Never run the reset command in a primary or otherwise valuable working directory.

Start the next group from the **same** baseline.

---

## 7. Suggested Task Set

Use these shapes if you do not already have local tasks.

### L1

1. Add null/length validation to an existing function and one failing test.
2. Fix a known simple logic bug and add a regression test.

### L2

1. Add an optional request field through handler → service → tests.
2. Standardize error codes on one path and verify with tests.

### L3

1. Change a public function signature with a compatibility path for callers.
2. Fix a concurrency / double-submit issue with a reproducible check.

---

## 8. Results Templates

### 8.1 Per-run log

```text
Task ID:
Tier: L1 | L2 | L3
Group: A Sol | B Luna | C Lean
Baseline commit:
Codex surface/version:
Routing mode: direct | native-subagent | independent-session fallback
Controller model / effort:
Model / skill notes:

Turns:
Sol calls:
Luna calls:
Terra calls:
Escalations:
Protocol violations:

Input tokens:
Output tokens:
Total tokens:          # or proxy metric name + value

Diff stat:
Acceptance: PASS | FAIL
Quality scores (0–2):
  Correctness:
  Scope:
  Tests:
  Safety:
  Maintainability:
  Completeness:
Quality total: /12

Notes:
```

### 8.2 Summary table

```text
Tier | Task | Group | Total tokens (or proxy) | Quality /12 | Acceptance | Escalations | Notes
L1   | T1   | A     |                         |             |             |             |
L1   | T1   | B     |                         |             |             |             |
L1   | T1   | C     |                         |             |             |             |
...
```

### 8.3 Savings calculation

Relative to Direct Sol for the same task:

```text
Savings rate ≈ 1 - (Lean total tokens / Sol total tokens)
```

Compute per task, then report both the mean per-task savings and the tier-total savings:

```text
Tier-total savings = 1 - (sum of Lean costs for the tier / sum of Sol costs for the tier)
```

Keep failed acceptance checks and quality regressions visible in the summary; do not average them away.

---

## 9. How to Interpret Results

| Observation | Likely reading |
|-------------|----------------|
| L1: Lean much cheaper than Sol, quality similar | Router is effective on bounded work |
| L2: Lean between Luna and Sol; Terra used occasionally | Intermediate escalation is doing useful work |
| L3: Many escalations; cost near Sol | Hard decisions still need Sol; savings may be modest |
| Lean fails acceptance while Sol passes | Quality regression risk for that task class |
| Luna cheapest but fails tests / expands scope | Cheap model without routing is not free in quality terms |
| Scope gate rarely triggers and no extra paths appear | Sol decomposition and Luna compliance are working; keep the gate as a low-cost audit signal |
| Handoffs are long / full transcripts leaked | Lean policy not being followed; treat as process failure |

**Do not average away failures.** A single L3 regression can matter more than average L1 savings.

---

## 10. Minimal 30–60 Minute Version

If time is limited:

1. Run **one L1** and **one L2** task.
2. Compare only **A (Sol)** vs **C (Lean)**.
3. Record: turns, escalations, acceptance pass/fail, quality total, `git diff --stat`, tracked path list, standard untracked path list, and ignored untracked path list.

You should still be able to answer:

- Does Lean save on simple work?
- Does Terra catch medium issues without full Sol cost?
- Is the final diff cleaner, similar, or worse?

---

## 11. Test Discipline (Avoid Self-Deception)

1. Same baseline commit for every group of a given task.
2. Same task packet text for every group.
3. Same acceptance commands.
4. No extra hints for the Lean group.
5. Score from commands and the rubric, not “felt smarter”.
6. Record protocol violations (ignored handoff rules, skipped agents, etc.).
7. Keep Caveman / other compressors out of A–C unless you are explicitly testing Group D.

---

## 12. Final Checklist

**Before starting**

- [ ] Groups A / B / C defined
- [ ] Task packets include objective acceptance commands
- [ ] Baseline commits recorded
- [ ] Competing skills disabled for primary runs

**After each run**

- [ ] Acceptance commands executed
- [ ] Token or proxy metrics recorded
- [ ] Quality scores filled
- [ ] Diff stat plus tracked/untracked scope evidence recorded
- [ ] Repo reset to baseline

**After all runs**

- [ ] Per-tier average savings vs Sol computed
- [ ] Tasks with quality drop marked
- [ ] One-paragraph conclusion written: where Lean helps, where it does not

---

## 13. Example Conclusion Format

```text
On this repo (date, Codex version notes):

- L1 average savings vs Sol: ___%
- L2 average savings vs Sol: ___%
- L3 average savings vs Sol: ___%

Quality:
- Lean matched Sol on N/M tasks
- Lean degraded on: <task ids and why>

Practical recommendation:
- Use Lean for: ...
- Prefer Direct Sol for: ...
- Watch out for: ...
```

---

## License note

This test guide is documentation only. It does not modify the MIT-licensed project code. Adapt task packets and acceptance commands to your stack freely.
