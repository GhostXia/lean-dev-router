---
name: lean-dev-router
description: Route project development through sol_planner, luna_worker, and terra_auditor with the minimum necessary agent calls and compact handoffs. Use for implementation, fixes, refactors, planning, or code review when token-efficient subagent coordination is desired.
---

# Lean Dev Router

Use the fewest agents needed. Keep routing sequential; the orchestrator owns every handoff.

## Route

- Send a clear, bounded implementation task directly to `luna_worker`.
- Send an initially ambiguous task or a task requiring major architectural, scope, interface, data-model, compatibility, security-boundary, dependency, or acceptance decisions to `sol_planner`, then send its plan to `luna_worker`.
- When `luna_worker` cannot resolve an implementation, debugging, testing, or local technical-choice problem, send its compact escalation to `terra_auditor`; never send it directly to `sol_planner`.
- Send `terra_auditor`'s actionable technical resolution back to `luna_worker` for all edits and validation.
- Send a problem to `sol_planner` only when `terra_auditor` cannot establish a supported solution or identifies a major decision. Send Sol's decision back to `luna_worker`.
- Use `terra_auditor` after implementation only for explicit review requests or material correctness, security, migration, compatibility, or regression risk.

## Handoff

Pass only:

- objective and fixed constraints;
- acceptance criteria;
- relevant paths or diff;
- concise evidence and test results;
- attempted fixes, if any;
- the single decision or action needed next.

Do not forward full transcripts, repeated context, complete logs, or broad repository dumps. Do not ask subagents to orchestrate other subagents.

## Stop

- Stop when the requested result and necessary validation are complete.
- Do not invoke all three agents by default.
- Do not repeat an agent call without new evidence or a changed decision.
- Summarize the final outcome once; omit internal handoff repetition.
