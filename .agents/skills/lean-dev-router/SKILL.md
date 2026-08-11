---
name: lean-dev-router
description: Route repository-bound software engineering lifecycle work through one sol_planner coordinator by default and complexity-scaled pools of luna_worker and terra_auditor agents. Use for planning, implementation, fixes, refactors, audits, reviews, investigations, incident diagnosis, migrations, upgrades, testing, documentation, configuration, or release-readiness checks when token- or latency-efficient coordination is desired.
---

# Lean Dev Router

Use the fewest agents that meet the requested token-versus-latency priority. Use one `sol_planner` coordinator by default; multiple Sol coordinators require explicit user direction and non-overlapping scopes.

## Language

Follow the parent task's primary language. Keep code, commands, paths, model IDs, and agent names unchanged.

## Engineering entry and route

- Send every change-producing task to one `sol_planner`. It issues a minimal single-step `DISPATCH` for bounded L1 work or decomposes complex work before any Luna assignment. Only `luna_worker` implements changes.
- Start explicit audit, review, compliance, release-readiness, investigation, diagnosis, or evidence-first debugging with `terra_auditor`. Use Luna only after implementation is authorized; add Sol when planning, consolidation, conflict resolution, or a major decision is needed.
- For migrations and upgrades, Sol fixes scope and order, Terra inventories risk, Luna implements bounded changes, and Terra verifies material risk.
- The parent maps the role/status/request table mechanically and returns results to the existing coordinator. Workers request capabilities, never select peers or infer routes from evidence.
- Production deployment, destructive action, external commitment, and business or product-policy changes remain outside this routing authority.

## Handoff protocol

Execution authorization and delegated results are different message types. Luna may write only after receiving this complete inbound contract:

```text
PROTOCOL: lean-dev-router/v2
STATUS: DISPATCH
TARGET: implementation
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

- Only Sol may author or amend `DISPATCH`; the parent may relay it unchanged. Every field must be present and non-empty, `PATHS_ALLOW` must contain repository-relative writable paths, and no major product or architecture decision may remain open.
- Missing or invalid authorization makes Luna perform no implementation and return `STATUS: BLOCKED`, `FAILURE: missing_dispatch`, and `NEXT: parent`.
- `PASS`, `BLOCKED`, and `ESCALATE` are outbound results, never write authorization. `PLAN_READY` is not an execution status.

Every delegated result uses this schema:

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

`PASS` completes the current stage with `FAILURE: none`; `BLOCKED` pauses for missing information, authority, or dependency; `ESCALATE` requests another capability. `REQUEST` is mandatory and never authorizes a write. `NEXT` is always `parent`. Bind repository claims to a relative path and short diff or command result. Use `path: N/A (planning-only)` only for planning, `path: N/A (batch coverage)` for assigned-versus-processed identifiers, `path: N/A (scope-check)` for repository scope, and `path: N/A (integration-check)` for combined-state evidence. Reject incomplete or unlisted combinations instead of inferring success or routing from prose.

| AGENT | STATUS | REQUEST | Mechanical destination |
|:---|:---|:---|:---|
| `luna_worker` | `PASS` | `none` | `current_coordinator`, stage complete |
| `luna_worker` | `BLOCKED` | `none` | `current_coordinator`, stage paused |
| `luna_worker` | `ESCALATE` | `technical_resolution` | `terra_auditor` |
| `terra_auditor` | `PASS` | `none` | `current_coordinator`, stage complete |
| `terra_auditor` | `BLOCKED` | `none` | `current_coordinator`, stage paused |
| `terra_auditor` | `ESCALATE` | `implementation` | `sol_planner`, authorization required |
| `terra_auditor` | `ESCALATE` | `planning_resolution` | `sol_planner` |
| `sol_planner` | `PASS` | `none` | `current_coordinator`, the top-level parent; task complete |
| `sol_planner` | `BLOCKED` | `none` | `current_coordinator`, the top-level parent; stage paused |
| `sol_planner` | `BLOCKED` | `implementation` | `luna_worker`, with a valid `DISPATCH` |
| `sol_planner` | `BLOCKED` | `human_authority` | `user`, through parent |

## Security and write scope

- `DISPATCH` is a protocol authorization statement, not a cryptographic signature. The parent and Sol are a trusted coordination plane; the protocol does not constrain a malicious agent with host-level write access.
- `PATHS_ALLOW` and `scripts/check_scope.py` constrain declared scope and detect drift; they do not block operating-system writes. Terra's read-only guarantee depends on Codex enforcing `sandbox_mode = "read-only"`. Host sandboxing, filesystem permissions, and worktree isolation enforce write access.
- Sol's bounded decomposition is the primary scope control. Read context is not write authority; generated files also require prior authorization.
- Before accepting Luna `PASS`, prefer `python scripts/check_scope.py --baseline <baseline> --allow <paths_allow_entry>` for every allow entry. It checks tracked, standard untracked, and ignored untracked paths. Record `SCOPE: PASS` as scope-check evidence; never auto-ignore a path class.
- An extra path rejects terminal `PASS` with `FAILURE: scope`. Trim obvious drift, use Terra only when technical necessity is unclear, and amend scope only within the fixed objective and acceptance; otherwise use the human decision gate.

## Integration convergence gate

- Two or more write batches require shared contracts, dependency order, `integration_worktree`, `integration_owner`, `integration_baseline`, `integration_paths_allow`, and `integration_acceptance`. The allow-list begins as the exact union of accepted batch lists and changes only through an authorized Luna repair.
- Sol coordinates without writing. One Luna integration owner combines accepted commits in order; conflict resolution or compatibility edits require a new bounded `DISPATCH`. Parallel writers require isolated worktrees or checkouts.
- Whole-task `PASS` requires a clean combined state, complete integration acceptance, and a final scope check from `integration_baseline` to the combined commit. Component `PASS` and component audits are not transitive.
- Require final Terra review when the user requests it, two or more batches received Terra verification, or integration crosses a material security, data, concurrency, compatibility, migration, or public-contract boundary.

## Codex execution and scaling

- Prefer native Codex custom agents. Verify the intended Agent, model, reasoning effort, sandbox, and first v2 result before dependent or write handoffs. Read-only Terra workers may share a checkout; Luna writers may not.
- If Sol cannot spawn nested workers, it returns `BLOCKED/dependency/REQUEST implementation/NEXT parent` with a `DISPATCH` manifest. Every Luna entry embeds the complete inbound contract plus `id`, `role`, `scope`, `worktree`, and `depends_on`; multi-batch manifests also include the integration fields above. The parent relays artifacts unchanged and returns results to the same Sol. If native spawning is unavailable, use independent sessions with that manifest.
- Default to `token-first`; requested Luna-plus-Terra caps are 3 for `token-first`, 6 for `balanced`, and 10 for `latency-first`. These are heuristics, not guarantees. For uniform items start with `min(mode cap, ceil(items / 30))`, then adjust for complexity, risk, independence, and dependency depth.
- Give workers exact disjoint assignments and acceptance criteria. Run dependencies sequentially, independent work in parallel, verify complete coverage, and use a different Terra for high-risk peer verification.

## Human decision gate

Sol decides only reversible technical trade-offs within fixed objective, scope, acceptance, and authorized policy. User authority is required for changes to those bounds or for irreversible or material compatibility, security, privacy, license, migration, cost, or product commitments.

For a user-owned choice, Sol returns `STATUS: BLOCKED`, `FAILURE: major-decision`, `REQUEST: human_authority`, and `NEXT: parent`, with up to three viable options, trade-offs, affected paths, one recommendation, and one question. Pause implementation; the existing Sol resumes with a new valid `DISPATCH` after the answer.

## Handoff and stop

Pass only the objective, fixed constraints, acceptance, relevant paths or diff, concise evidence, attempted fixes, and the single next decision or action. Do not forward transcripts, repeated context, complete logs, or broad repository dumps.

Stop when acceptance and required validation are complete. Do not invoke all roles by default, repeat an agent call without new evidence, or let Luna or Terra orchestrate peers. Summarize the outcome once.
