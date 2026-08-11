---
name: lean-dev-router
description: Route repository-bound software engineering lifecycle work through one sol_planner coordinator by default and complexity-scaled pools of luna_worker and terra_auditor agents. Use for planning, implementation, fixes, refactors, audits, reviews, investigations, incident diagnosis, migrations, upgrades, testing, documentation, configuration, or release-readiness checks when token- or latency-efficient coordination is desired.
---

# Lean Dev Router

Use the fewest agents that satisfy the selected token-versus-latency priority. For complex routed work, use one `sol_planner` by default to coordinate as many `luna_worker` and `terra_auditor` instances as task complexity and volume justify. Use multiple Sol coordinators only when the user explicitly requests them.

## Language

- Follow the parent task's primary language in analysis, handoffs, and final responses.
- If the parent task is bilingual, use the language requested for the current output; if unspecified, use the dominant language.
- Keep code, commands, file paths, model IDs, agent names, and other technical identifiers unchanged.

## Handoff protocol

Execution authorization and delegated results are different message types. A Luna write task starts only from this inbound contract:

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

- Only `sol_planner` may issue a `DISPATCH`. The parent may relay it mechanically but must not author, repair, or broaden it.
- `DISPATCH` is valid only when every field above is present and non-empty, `PATHS_ALLOW` contains repository-relative writable paths, and no major product or architecture decision remains open. A minimal single-step contract is valid for L1 work.
- Inbound `DISPATCH` does not use an `AGENT` field. When no narrower constraint is needed, `minimal change only` is a valid non-empty `CONSTRAINTS` entry.
- Before any implementation tool or write, Luna validates only the contract, not the system topology. Missing or invalid authorization produces `STATUS: BLOCKED`, `FAILURE: missing_dispatch`, and `NEXT: parent`; Luna does not name another agent or edit files.
- `PASS`, `BLOCKED`, and `ESCALATE` are outbound result statuses and never authorize implementation. `PLAN_READY` is not an execution status.
- Workers describe the capability required next and never name another worker or the dispatch authority. The parent maps the current `AGENT` plus `REQUEST` mechanically; it does not infer routing from `EVIDENCE`.

Every delegated result must use this compact outbound protocol; do not invent role-specific output schemas.

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

- `PASS` means the current role's stage is complete; `BLOCKED` means required information, authority, or dependency is unavailable; `ESCALATE` means another role must act.
- `FAILURE` is `none` for `PASS`; otherwise choose one primary category.
- Every repository claim must bind to a concrete relative path and include a short diff summary or command result. Use `path: N/A (planning-only)` only for planning with no repository artifact, `path: N/A (batch coverage)` for assigned-versus-processed item identifiers, `path: N/A (scope-check)` for a repository-wide allow-list result, and `path: N/A (integration-check)` for commands run against the combined integration commit; never invent a path.
- `REQUEST` is mandatory. Use `none` when no new capability is needed, `implementation` to ask the dispatch authority for an authorized implementation or repair, `technical_resolution` for diagnosis or a local technical solution, `planning_resolution` for an in-scope plan or contract decision, and `human_authority` only for a user-owned decision. A `REQUEST` is never write authorization; Luna still requires a valid `DISPATCH`.
- `NEXT` is always `parent`. The parent applies only these allowed transitions: Luna `technical_resolution` to Terra; Terra `implementation` or `planning_resolution` to the existing Sol; Sol `implementation` to Luna with a valid `DISPATCH`; and Sol `human_authority` to the user. `none` returns to the current coordinator or completes the current stage. Reject every other role-and-request combination rather than inferring a route from `EVIDENCE`.
- If a handoff is missing a field or evidence, do not infer success; return one compact correction request with `STATUS: BLOCKED` and `FAILURE: verification`.

## Write scope gate

- Use Sol's Todo/`DISPATCH` plan as the primary scope control for change-producing work, especially when CI is absent. Size Luna write batches so each has one bounded objective, explicit dependencies, a controllable path set, and independent acceptance; do not split work more finely than those properties require. Precise assignments and Luna compliance prevent most drift.
- Treat `relevant paths` as read context, not write authorization. Before any Luna write task starts, Sol must issue a valid inbound `DISPATCH` containing the baseline commit, task summary, acceptance criteria, constraints, and explicit repository-relative `PATHS_ALLOW` entries naming files or directory subtrees. The parent may relay that artifact unchanged but cannot create a direct Luna fast path. Files generated by tests, formatters, package managers, or other tools require prior authorization too.
- Before accepting a Luna `PASS`, prefer the repository helper `python scripts/check_scope.py --baseline <baseline> --allow <paths_allow_entry>` repeated for every authorized path. It mechanically collects tracked changes, standard untracked files, and ignored untracked files, verifies the allow-list, and emits one compact result. Record that output as `path: N/A (scope-check)` evidence; if the helper is unavailable, fall back to `git diff --name-only --no-renames <baseline> --`, `git ls-files --others --exclude-standard`, and `git ls-files --others --ignored --exclude-standard`. On failure list every extra path; do not silently ignore any path class.
- If extra paths exist, preserve Luna's original handoff but do not accept it as terminal success. Record the extras as scope-check evidence with `FAILURE: scope`. An existing Sol may send clearly unrelated changes back to Luna for trimming; use Terra only when technical necessity is unclear. Sol may amend or split the batch only within the fixed objective and acceptance criteria; otherwise use the human decision gate. The standalone parent applies the same gate.
- Keep this check as a low-frequency secondary fuse, not the main scheduler. An in-scope `PASS` does not require Terra review, and a gate that rarely triggers is evidence of good decomposition rather than a reason to remove it.

## Integration convergence gate

- When two or more write batches form one deliverable, a component `PASS` closes only that batch and never implies whole-task success. Before dispatch, Sol must define shared contracts, dependency order, `integration_worktree`, `integration_owner`, `integration_baseline`, `integration_paths_allow`, and `integration_acceptance`. `integration_paths_allow` starts as the exact union of accepted batch allow-lists and may change only through an authorized Luna integration-repair batch.
- Sol coordinates but does not mutate the integration tree. Assign one Luna as `integration_owner` to combine commits in dependency order; a parent fallback may perform only conflict-free mechanical merges. Any conflict resolution or compatibility edit is a new bounded Luna write batch with its own baseline and allow-list. Prefer incremental convergence: run the narrowest useful cross-batch checks after each dependent batch or independent wave, then complete acceptance against the exact combined commit.
- Before terminal whole-task `PASS`, the coordinator must verify the integration worktree is clean and prefer `python scripts/check_scope.py --baseline <integration_baseline> --end <combined_commit> --allow <integration_paths_allow_entry>` repeated for every authorized path. Record its compact output as `path: N/A (scope-check)`, then record the combined commit, integration order, and acceptance commands as `path: N/A (integration-check)`. If the helper is unavailable, use `git diff --name-only --no-renames <integration_baseline> <combined_commit> --`, `git ls-files --others --exclude-standard`, and `git ls-files --others --ignored --exclude-standard`.
- A final Terra integration audit is mandatory when the user requested independent verification, when two or more component batches received Terra verification, or when integration crosses a material security, data, concurrency, compatibility, migration, or public-contract boundary. Otherwise combined-state command evidence is sufficient. Separate component audits never substitute for a required integration audit.
- On integration failure, stop terminal success and identify the earliest failing merge or wave. Use `FAILURE: scope` for unauthorized paths, `verification` for failed acceptance, `dependency` for unavailable commits/tools, and `ambiguity` for unresolved causality. Route an obvious bounded compatibility repair to Luna, unclear cross-component causality to Terra, an in-scope contract or decomposition change to Sol, and any user-owned objective, compatibility, or product trade-off through the human decision gate.

## Codex execution mode

- Default to native Codex subagents using the configured custom Agent TOML files. Start change-producing work with one `sol_planner`; for clear bounded L1 work it issues one minimal `DISPATCH`, while complex work receives fuller decomposition and multiple contracts as needed. Read-only audit or investigation entry may still start with Terra.
- Let the default Sol coordinator run multiple Luna and Terra workers in parallel when their assignments are independent. Give every parallel Luna writer a dedicated worktree or independent checkout on its own branch; a branch alone is not write isolation. Read-only Terra workers may share a checkout.
- Before a dependent or write handoff, verify that the intended Agent loaded, its model and reasoning effort are honored, and its first result follows `lean-dev-router/v2`.
- When available, check `codex --version` before relying on native routing; in the CLI use `/agent` to inspect agent threads.
- If a Sol session cannot spawn nested workers, it returns `BLOCKED/dependency/REQUEST implementation/NEXT parent` and a compact `DISPATCH` manifest in `EVIDENCE`. Each Luna write entry must embed a literal complete artifact containing `PROTOCOL: lean-dev-router/v2`, `STATUS: DISPATCH`, `TARGET: implementation`, `TASK_SUMMARY`, `BASELINE`, `PATHS_ALLOW`, `ACCEPTANCE`, `CONSTRAINTS`, and `NEXT: parent`; worker metadata also contains `id`, `role`, `scope`, `worktree`, and `depends_on`. Multi-batch deliverables additionally declare shared contracts, `integration_worktree`, `integration_owner`, `integration_order`, `integration_baseline`, `integration_paths_allow`, `integration_acceptance`, and whether final Terra review is required. The parent relays each artifact unchanged and returns compact results to the same Sol for consolidation. If native spawning is entirely unavailable, use independent Codex sessions with the same manifest.
- Codex's native background-agent UI is still a native subagent workflow. Treat unrelated background processes or sessions as fallback, not as equivalent parent-child routing.

## Worker scaling and fan-out

- Use one `sol_planner` per routed task by default. Sol chooses worker count, role mix, ordering, and concurrency from task size, volume, independence, dependency depth, and risk. Only an explicit user instruction may enable multiple Sol coordinators; the parent creates them with non-overlapping orchestration scopes, and no Sol may spawn a peer Sol.
- Default to `token-first` unless the user prioritizes elapsed time. Use requested concurrent worker caps of 3 for `token-first`, 6 for `balanced`, and 10 for `latency-first`; the cap covers Luna and Terra combined and is a routing heuristic, not a runtime guarantee.
- Parallelize independent read, implementation, test, or review batches. For uniform item sets, start with `min(mode cap, ceil(items / 30))`, then adjust for complexity and risk. Keep dependent stages sequential; use disjoint waves when fewer workers start.
- Give every worker an exact disjoint assignment, fixed constraints, acceptance criteria, relevant paths, a batch identifier, and the same output schema. For item batches, require first `EVIDENCE` as `path: N/A (batch coverage)` with assigned versus processed identifiers.
- Sol waits for all required workers, verifies complete non-overlapping coverage, merges and deduplicates results, and decides follow-up routing. Use a different Terra to verify high-risk or conflicting findings; never let an auditor verify its own finding.

## Engineering task entry

- Treat repository-bound implementation, fixes, refactors, audits and reviews, investigations and incident diagnosis, migrations and upgrades, tests and QA, documentation and configuration, and release-readiness checks as in scope.
- For change-producing work, send every task to one `sol_planner` for dispatch authorization before any Luna assignment. Sol uses one minimal `DISPATCH` for clear bounded work and fuller decomposition when the work is ambiguous, cross-cutting, or decision-heavy; add Terra only when diagnosis or independent verification is justified.
- For audits, reviews, compliance checks, and release readiness, start with one or more Terra workers. Use Sol only when partitioning, consolidation, conflict resolution, or a major decision is needed; use Luna only after remediation is authorized.
- For investigations, incidents, performance analysis, and debugging, let Terra establish evidence and likely causes, parallelizing independent hypotheses when useful. Sol resolves in-scope technical trade-offs and invokes the human decision gate for user-owned choices; Luna applies the authorized fix.
- For migrations and dependency or platform upgrades, let Sol plan within the authorized scope and define implementation order, Terra inventory compatibility and risk, Luna implement isolated changes, and Terra verify the result.
- This scope does not grant authority for production deployment, destructive actions, external commitments, or changes to business or product policy. Those actions require explicit user approval.

## Route

- Send every change-producing task to one `sol_planner` for dispatch authorization. For clear bounded L1 work, Sol should issue a minimal single-step `DISPATCH`; for ambiguous, decomposable, cross-task, or decision-heavy work, Sol resolves or returns the open decisions before dispatch and coordinates the workers until completion.
- When a `luna_worker` cannot resolve an implementation, debugging, testing, or local technical-choice problem, it returns a compact `technical_resolution` request; the parent mechanically routes it to Terra and returns the result to the existing Sol coordinator.
- Sol sends `terra_auditor`'s actionable technical resolution to the relevant `luna_worker` for edits and validation.
- In a Sol-coordinated task, Terra requests `planning_resolution` when its technical layer cannot decide; the parent returns that request to the existing Sol and never creates another Sol. Sol sends an in-scope technical decision back to the relevant Luna under a new or amended `DISPATCH` and uses the human decision gate below for user-owned decisions.
- Use `terra_auditor` as the entry point for explicit audit, review, investigation, diagnosis, compliance, or release-readiness requests. After implementation, invoke Terra only for an explicit review request or material correctness, security, migration, compatibility, or regression risk.

## Human decision gate

- Let `sol_planner` decide reversible technical trade-offs that stay within the fixed objective, scope, acceptance criteria, and user-authorized policy.
- Require user authority for changes to the objective, scope, acceptance criteria, direction, philosophy, or product priority; conflicts with explicit user intent; and irreversible or material compatibility, security, privacy, license, migration, or cost commitments.
- For a user-owned decision, Sol returns `STATUS: BLOCKED`, `FAILURE: major-decision`, `REQUEST: human_authority`, and `NEXT: parent`. Put up to three viable options, decisive trade-offs, affected paths, and one recommendation in `EVIDENCE`; make `SUMMARY` the single question for the user. The route remains `sol_planner -> parent -> user`.
- Pause implementation until the user answers. Resume through the existing Sol coordinator, which issues a new valid `DISPATCH` after the answer fixes the constraints.

## Handoff

Pass only:

- objective and fixed constraints;
- acceptance criteria;
- relevant paths or diff;
- concise evidence and test results;
- attempted fixes, if any;
- the single decision or action needed next.

Do not forward full transcripts, repeated context, complete logs, or broad repository dumps. Only a parent-created `sol_planner` may orchestrate Luna and Terra workers.

## Stop

- Stop when the requested result and necessary validation are complete.
- Do not invoke all three agents by default.
- Do not repeat an agent call without new evidence or a changed decision.
- Summarize the final outcome once; omit internal handoff repetition.
