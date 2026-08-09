---
name: lean-dev-router
description: Route project development through sol_planner, luna_worker, and terra_auditor with the minimum necessary agent calls and compact handoffs. Use for implementation, fixes, refactors, planning, or code review when token-efficient subagent coordination is desired.
---

# Lean Dev Router

Use the fewest agents needed. Keep routing sequential; the orchestrator owns every handoff.

## Language / 语言

- Follow the parent task's primary language in analysis, handoffs, and final responses. / 分析、交接和最终回复跟随父任务的主要语言。
- If the parent task is bilingual, use the language requested for the current output; if unspecified, use the dominant language. / 如果父任务是双语，按当前输出要求选择语言；未指定时使用占主导地位的语言。
- Keep code, commands, file paths, model IDs, agent names, and other technical identifiers unchanged. / 代码、命令、文件路径、模型 ID、Agent 名称及其他技术标识保持不变。

## Handoff protocol / 交接协议

Every delegated result must use this compact protocol; do not invent role-specific output schemas. / 每次委派结果都必须使用以下紧凑协议，不得继续使用角色专属的输出格式。

```text
PROTOCOL: lean-dev-router/v1
AGENT: luna_worker | terra_auditor | sol_planner
STATUS: PASS | BLOCKED | ESCALATE
FAILURE: none | scope | verification | dependency | ambiguity | major-decision
EVIDENCE:
- path: relative/path/to/file
  proof: short diff summary or `command` -> PASS/FAIL
NEXT: parent | luna_worker | terra_auditor | sol_planner | none
SUMMARY: one concise sentence
```

- `PASS` means the current role's stage is complete; `BLOCKED` means required information, authority, or dependency is unavailable; `ESCALATE` means another role must act. / `PASS` 表示当前角色阶段完成；`BLOCKED` 表示缺少必要信息、权限或依赖；`ESCALATE` 表示需要其他角色继续处理。
- `FAILURE` is `none` for `PASS`; otherwise choose one primary category. / `PASS` 时 `FAILURE` 必须为 `none`；其他状态只选择一个主要失败类别。
- Every repository claim must bind to a concrete relative path and include a short diff summary or command result. For planning-only work with no repository artifact, use `path: N/A (planning-only)` and explain why; never invent a path. / 每个仓库结论都必须绑定具体相对路径，并附简短 diff 摘要或命令结果。纯规划且没有仓库文件时使用 `path: N/A (planning-only)` 并解释原因，不得伪造路径。
- `NEXT` is mandatory and must name the exact next owner. If a handoff is missing a field or evidence, do not infer success; return one compact correction request with `STATUS: BLOCKED` and `FAILURE: verification`. / `NEXT` 必须填写并明确下一个负责人。交接缺字段或证据时不得自行推断成功，应返回一次紧凑的修正请求，并使用 `STATUS: BLOCKED`、`FAILURE: verification`。

## Codex execution mode / Codex 执行方式

- Default to native Codex subagents using the configured custom Agent TOML files. Ask the parent session to spawn the named role; route dependent work sequentially. / 默认使用 Codex 原生 subagent 和已配置的 Agent TOML 文件，由父会话直接调用指定角色；有依赖的工作按顺序执行。
- Use parallel agents only for independent read-only work. Do not run parallel write agents against the same worktree. / 仅对相互独立的只读任务并行；不得让并行写入 Agent 同时修改同一工作区。
- Before a dependent or write handoff, verify that the intended Agent loaded, its model and reasoning effort are honored, and its first result follows `lean-dev-router/v1`. / 在有依赖或写入的交接前，确认目标 Agent 已加载、模型和思考强度生效，且首次结果遵循 `lean-dev-router/v1`。
- When available, check `codex --version` before relying on native routing; in the CLI use `/agent` to inspect agent threads. / 条件允许时，在依赖原生路由前检查 `codex --version`；CLI 中使用 `/agent` 检查 Agent 线程。
- If native spawning is unavailable or the Agent configuration is not honored, use an independent Codex session one role at a time. Pass only the compact handoff, relevant paths, constraints, and evidence; use an isolated worktree or branch for writes. / 如果原生调用不可用或 Agent 配置未生效，则按角色逐个使用独立 Codex session；只传递紧凑交接、相关路径、约束和证据，写入时使用隔离 worktree 或分支。
- Codex's native background-agent UI is still a native subagent workflow. Treat unrelated background processes or sessions as fallback, not as equivalent parent-child routing. / Codex 原生后台 Agent 界面仍属于原生 subagent 流程；其他后台进程或独立 session 只能作为 fallback，不能视为等价的父子路由。

## Route

- Send a clear, bounded implementation task directly to `luna_worker`.
- Send an initially ambiguous task or a task requiring major architectural, scope, interface, data-model, compatibility, security-boundary, dependency, or acceptance decisions to `sol_planner`, then send its plan to `luna_worker`.
- When `luna_worker` cannot resolve an implementation, debugging, testing, or local technical-choice problem, send its compact escalation to `terra_auditor`; never send it directly to `sol_planner`.
- Send `terra_auditor`'s actionable technical resolution back to `luna_worker` for all edits and validation.
- Send a problem to `sol_planner` only when `terra_auditor` cannot establish a supported solution or identifies a major decision. Send Sol's in-scope technical decision back to `luna_worker`; use the human decision gate below for user-owned decisions.
- Use `terra_auditor` after implementation only for explicit review requests or material correctness, security, migration, compatibility, or regression risk.

## Human decision gate / 用户决策门

- Let `sol_planner` decide reversible technical trade-offs that stay within the fixed objective, scope, acceptance criteria, and user-authorized policy. / `sol_planner` 可以裁定不改变既定目标、范围、验收标准和用户授权策略的可逆技术取舍。
- Require user authority for changes to the objective, scope, acceptance criteria, direction, philosophy, or product priority; conflicts with explicit user intent; and irreversible or material compatibility, security, privacy, license, migration, or cost commitments. / 修改目标、范围、验收标准、方向、理念或产品优先级，违背用户明确意图，以及不可逆或重大的兼容性、安全、隐私、许可、迁移或成本承诺，必须交由用户决定。
- For a user-owned decision, return `STATUS: BLOCKED`, `FAILURE: major-decision`, and `NEXT: parent`. Put up to three viable options, decisive trade-offs, affected paths, and one recommendation in `EVIDENCE`; make `SUMMARY` the single question for the user. Do not add `NEXT: user`: the route is `sol_planner → parent → user`. / 对属于用户的决策，返回 `STATUS: BLOCKED`、`FAILURE: major-decision`、`NEXT: parent`；在 `EVIDENCE` 中列出最多三个可行方案、关键取舍、受影响路径和一个推荐，并让 `SUMMARY` 成为需要询问用户的唯一问题。不要增加 `NEXT: user`；正确路径是 `sol_planner → parent → user`。
- Pause implementation until the user answers. Route directly to `luna_worker` when the answer fully fixes the constraints; return to `sol_planner` once only when the plan must be revised. / 用户答复前暂停实施；答复已完整确定约束时直接交给 `luna_worker`，只有需要重整方案时才返回 `sol_planner` 一次。

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
