---
name: lean-dev-router
description: Route project development through one sol_planner coordinator and complexity-scaled pools of luna_worker and terra_auditor agents, with compact handoffs and parallel execution for independent work. Use for implementation, fixes, refactors, planning, audits, or code review when token- or latency-efficient subagent coordination is desired.
---

# Lean Dev Router

Use the fewest agents that satisfy the selected token-versus-latency priority. For complex routed work, use exactly one `sol_planner` to coordinate as many `luna_worker` and `terra_auditor` instances as task complexity justifies.

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

- Default to native Codex subagents using the configured custom Agent TOML files. For a clear bounded task, call one `luna_worker` directly. For complex, ambiguous, or decomposable work, call exactly one `sol_planner` and let it partition, delegate, wait, and consolidate. / 默认使用 Codex 原生 subagent 和已配置的 Agent TOML 文件。明确且边界清晰的任务直接调用一个 `luna_worker`；复杂、模糊或可拆分任务只调用一个 `sol_planner`，由其分解、委派、等待和归并。
- Let the single Sol coordinator run multiple Luna and Terra workers in parallel when their assignments are independent. Parallel Luna writes require separate worktrees or otherwise isolated branches; never let multiple writers modify the same worktree. / 当任务相互独立时，由单个 Sol 协调者并行运行多个 Luna 和 Terra。并行 Luna 写入必须使用独立 worktree 或其他隔离分支；不得让多个写入者修改同一工作区。
- Before a dependent or write handoff, verify that the intended Agent loaded, its model and reasoning effort are honored, and its first result follows `lean-dev-router/v1`. / 在有依赖或写入的交接前，确认目标 Agent 已加载、模型和思考强度生效，且首次结果遵循 `lean-dev-router/v1`。
- When available, check `codex --version` before relying on native routing; in the CLI use `/agent` to inspect agent threads. / 条件允许时，在依赖原生路由前检查 `codex --version`；CLI 中使用 `/agent` 检查 Agent 线程。
- If a Sol session cannot spawn nested workers, the parent acts only as a mechanical relay: execute Sol's exact worker manifest, return compact worker results to the same Sol, and let Sol make all routing and consolidation decisions. If native spawning is entirely unavailable, use independent Codex sessions with the same manifest and isolated worktrees for writes. / 如果 Sol 会话不能嵌套启动 worker，父会话只做机械中继：严格执行 Sol 的 worker 清单，将紧凑结果送回同一个 Sol，并由 Sol 完成所有路由与归并决策。原生调用完全不可用时，使用相同清单启动独立 Codex session，写入任务使用隔离 worktree。
- Codex's native background-agent UI is still a native subagent workflow. Treat unrelated background processes or sessions as fallback, not as equivalent parent-child routing. / Codex 原生后台 Agent 界面仍属于原生 subagent 流程；其他后台进程或独立 session 只能作为 fallback，不能视为等价的父子路由。

## Worker scaling and fan-out / Worker 扩缩与分发

- Use exactly one `sol_planner` per routed task. Sol chooses worker count, role mix, ordering, and concurrency from task size, independence, dependency depth, and risk; never create multiple Sol coordinators for the same task. / 每个路由任务只使用一个 `sol_planner`。Sol 根据任务规模、独立性、依赖深度和风险决定 worker 数量、角色组合、顺序及并发；同一任务不得创建多个 Sol 协调者。
- Default to `token-first` unless the user prioritizes elapsed time. Use requested concurrent worker caps of 3 for `token-first`, 6 for `balanced`, and 10 for `latency-first`; the cap covers Luna and Terra combined and is a routing heuristic, not a runtime guarantee. / 用户未强调耗时时默认 `token-first`。并发 worker 请求上限为：`token-first` 3 个、`balanced` 6 个、`latency-first` 10 个；上限包含 Luna 与 Terra 总数，属于调度启发式，不是运行时保证。
- Parallelize independent read, implementation, test, or review batches. For uniform item sets, start with `min(mode cap, ceil(items / 30))`, then adjust for complexity and risk. Keep dependent stages sequential; use disjoint waves when fewer workers start. / 对相互独立的读取、实现、测试或审查批次进行并行。对相对均匀的项目集合，先使用 `min(模式上限, ceil(项目数 / 30))`，再按复杂度和风险调整。有依赖的阶段保持串行；可用 worker 较少时使用互不重叠的波次。
- Give every worker an exact disjoint assignment, fixed constraints, acceptance criteria, relevant paths, a batch identifier, and the same output schema. For item batches, require first `EVIDENCE` as `path: N/A (batch coverage)` with assigned versus processed identifiers. / 为每个 worker 提供精确且互不重叠的任务、固定约束、验收标准、相关路径、批次标识和统一输出结构。项目批次的首条 `EVIDENCE` 必须使用 `path: N/A (batch coverage)` 并记录已分配与已处理标识。
- Sol waits for all required workers, verifies complete non-overlapping coverage, merges and deduplicates results, and decides follow-up routing. Use a different Terra to verify high-risk or conflicting findings; never let an auditor verify its own finding. / Sol 等待所有必要 worker，检查覆盖完整且互不重叠，归并去重结果并决定后续路由。高风险或冲突发现交给不同的 Terra 复核，不得自审。

## Route

- Send a clear, bounded implementation task directly to `luna_worker`.
- Send an initially ambiguous, decomposable, or cross-task request, or one requiring major architectural, scope, interface, data-model, compatibility, security-boundary, dependency, or acceptance decisions, to one `sol_planner`. Let Sol coordinate all Luna and Terra work until completion.
- When a `luna_worker` cannot resolve an implementation, debugging, testing, or local technical-choice problem, it returns a compact Terra escalation to the Sol coordinator; it never resolves the major decision itself.
- Sol sends `terra_auditor`'s actionable technical resolution to the relevant `luna_worker` for edits and validation.
- In a standalone Luna fast path, invoke one Sol only if Terra cannot establish a supported solution or identifies a major decision. In a Sol-coordinated task, Terra returns that escalation to the existing Sol; never create another Sol. Sol sends an in-scope technical decision back to the relevant Luna and uses the human decision gate below for user-owned decisions.
- Use `terra_auditor` after implementation only for explicit review requests or material correctness, security, migration, compatibility, or regression risk.

## Human decision gate / 用户决策门

- Let `sol_planner` decide reversible technical trade-offs that stay within the fixed objective, scope, acceptance criteria, and user-authorized policy. / `sol_planner` 可以裁定不改变既定目标、范围、验收标准和用户授权策略的可逆技术取舍。
- Require user authority for changes to the objective, scope, acceptance criteria, direction, philosophy, or product priority; conflicts with explicit user intent; and irreversible or material compatibility, security, privacy, license, migration, or cost commitments. / 修改目标、范围、验收标准、方向、理念或产品优先级，违背用户明确意图，以及不可逆或重大的兼容性、安全、隐私、许可、迁移或成本承诺，必须交由用户决定。
- For a user-owned decision, return `STATUS: BLOCKED`, `FAILURE: major-decision`, and `NEXT: parent`. Put up to three viable options, decisive trade-offs, affected paths, and one recommendation in `EVIDENCE`; make `SUMMARY` the single question for the user. Do not add `NEXT: user`: the route is `sol_planner → parent → user`. / 对属于用户的决策，返回 `STATUS: BLOCKED`、`FAILURE: major-decision`、`NEXT: parent`；在 `EVIDENCE` 中列出最多三个可行方案、关键取舍、受影响路径和一个推荐，并让 `SUMMARY` 成为需要询问用户的唯一问题。不要增加 `NEXT: user`；正确路径是 `sol_planner → parent → user`。
- Pause implementation until the user answers. Resume through the existing Sol coordinator when one exists; otherwise route directly to `luna_worker` when the answer fully fixes the constraints, invoking one Sol only when the plan must be revised. / 用户答复前暂停实施；已有 Sol 协调者时由同一个 Sol 恢复调度；否则在答复已完整确定约束时直接交给 `luna_worker`，只有需要重整方案时才调用一个 Sol。

## Handoff

Pass only:

- objective and fixed constraints;
- acceptance criteria;
- relevant paths or diff;
- concise evidence and test results;
- attempted fixes, if any;
- the single decision or action needed next.

Do not forward full transcripts, repeated context, complete logs, or broad repository dumps. Only the single `sol_planner` may orchestrate Luna and Terra workers.

## Stop

- Stop when the requested result and necessary validation are complete.
- Do not invoke all three agents by default.
- Do not repeat an agent call without new evidence or a changed decision.
- Summarize the final outcome once; omit internal handoff repetition.
