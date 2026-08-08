[![zread](https://img.shields.io/badge/Ask_Zread-_.svg?style=for-the-badge&color=00b0aa&labelColor=000000&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTQuOTYxNTYgMS42MDAxSDIuMjQxNTZDMS44ODgxIDEuNjAwMSAxLjYwMTU2IDEuODg2NjQgMS42MDE1NiAyLjI0MDFWNC45NjAxQzEuNjAxNTYgNS4zMTM1NiAxLjg4ODEgNS42MDAxIDIuMjQxNTYgNS42MDAxSDQuOTYxNTZDNS4zMTUwMiA1LjYwMDEgNS42MDE1NiA1LjMxMzU2IDUuNjAxNTYgNC45NjAxVjIuMjQwMUM1LjYwMTU2IDEuODg2NjQgNS4zMTUwMiAxLjYwMDEgNC45NjE1NiAxLjYwMDFaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00Ljk2MTU2IDEwLjM5OTlIMi4yNDE1NkMxLjg4ODEgMTAuMzk5OSAxLjYwMTU2IDEwLjY4NjQgMS42MDE1NiAxMS4wMzk5VjEzLjc1OTlDMS42MDE1NiAxNC4xMTM0IDEuODg4MSAxNC4zOTk5IDIuMjQxNTYgMTQuMzk5OUg0Ljk2MTU2QzUuMzE1MDIgMTQuMzk5OSA1LjYwMTU2IDE0LjExMzQgNS42MDE1NiAxMy43NTk5VjExLjAzOTlDMS42MDE1NiAxMC42ODY0IDUuMzE1MDIgMTAuMzk5OSA0Ljk2MTU2IDEwLjMzkOTlaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik0xMy43NTg0IDEuNjAwMUgxMS4wMzg0QzEwLjY4NSAxLjYwMDEgMTAuMzk4NCAxLjg4NjY0IDEwLjM5ODQgMi4yNDAxVjQuOTYwMUMxMC4zOTg0IDUuMzEzNTYgMTAuNjg1IDUuNjAwMSAxMS4wMzg0IDUuNjAwMUgxMy43NTg0QzE0LjExMTkgNS42MDAxIDE0LjM5ODQgNS4zMTM1NiAxNC4zOTg0IDQuOTYwMVYyLjI0MDFDMTQuMzk4NCAxLjg4NjY0IDE0LjExMTkgMS42MDAxIDEzLjc1ODQgMS42MDAxWiIgZmlsbD0iI2ZmZiIvPgo8cGF0aCBkPSJNNCAxMkwxMiA0TDQgMTJaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00IDEyTDEyIDQiIHN0cm9rZT0iI2ZmZiIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIvPgo8L3N2Zz4K&logoColor=ffffff)](https://zread.ai/GhostXia/lean-dev-router)

# Lean Dev Router

## English

Lean Dev Router is a general theory for coordinating and escalating multi-agent software development work. It assigns planning, implementation, diagnosis, and validation to agents with different responsibilities and cost levels, escalating only when necessary.

I currently use Codex, so this repository uses GPT model identifiers as concrete examples. The routing theory is not tied to Codex or GPT and can be adapted to other agent runtimes and models.

For further token savings, this router can be combined with projects such as [Caveman](https://github.com/juliusbrussee/caveman), which reduce unnecessary verbosity in engineering workflows. Lean Dev Router reduces unnecessary agent calls and handoff context; Caveman reduces unnecessary prose in agent responses. Together, they can help maximize token efficiency while preserving the technical content that matters. This project currently does not plan to duplicate response-compression features already provided by such projects.

Because the subagents use explicitly selected models and follow detailed work assignments, the main controller can often use Luna High or an even lower-cost model. This is a cost-optimization guideline rather than a strict requirement; use a more capable controller model when the task involves complex planning, major architectural decisions, or cross-task coordination.

### Handoff protocol

All three roles use one compact, machine-readable handoff protocol:

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

`EVIDENCE` must bind repository claims to a concrete path and a short diff summary or command result. `PASS` means the current stage is complete; `BLOCKED` means required information, authority, or dependency is unavailable; `ESCALATE` means another role must act. The parent should not infer success from an incomplete handoff.

### Codex execution mode

Native Codex subagents are the default. Ask the parent Codex session to spawn the configured role and keep dependent work sequential. Use parallel agents only for independent read-only work; do not let multiple agents write to the same worktree.

Before a dependent or write handoff, verify that the intended Agent loaded, its model and reasoning effort are honored, and its first result follows `lean-dev-router/v1`. If native spawning is unavailable or the configuration is not honored, use one independent Codex session per role as a fallback. Pass only the compact handoff, relevant paths, constraints, and evidence, and use an isolated worktree or branch for writes.

When available, check `codex --version` before relying on native routing. In the Codex CLI, use `/agent` to inspect agent threads. If the client cannot start or expose the expected native workflow, use the fallback instead of silently substituting the default agent or model.

The native Codex background-agent UI is part of the native subagent workflow. Unrelated background processes or independent sessions are fallback mechanisms, not equivalent parent-child routing. See the [official Codex subagents documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents) for current client and custom-agent behavior.

From personal experience, worktrees are recommended for batching independent tasks in parallel, especially when handling multiple pull requests at the same time. Give each task its own worktree and branch; avoid parallel worktrees for tightly dependent tasks or changes that must share the same working state.

Example routing chain:

```text
sol_planner → luna_worker → terra_auditor
                         ↘ sol_planner (only for unresolved or major decisions)
```

### Contents

- `.agents/skills/lean-dev-router/`: the lightweight routing Skill.
- `agents/`: example Agent configuration files for `luna_worker`, `sol_planner`, and `terra_auditor`.
- `lean-dev-router-self-test-guide.md`: a controlled guide for measuring token savings, quality, and routing overhead on your own codebase.

### Install

For Codex, copy `.agents/skills/lean-dev-router/` to `~/.codex/skills/lean-dev-router/`, then copy the three files in `agents/` to `~/.codex/agents/`. Adapt the file format and model identifiers when using another runtime.

### Roles

- `sol_planner`: initial planning and unresolved or major decisions.
- `luna_worker`: all authorized code, test, documentation, and configuration edits.
- `terra_auditor`: code audit, technical diagnosis, and validation; escalate only when it cannot resolve the issue or a major decision is required.

Use `$lean-dev-router` when a task benefits from this routing policy. The Skill deliberately avoids invoking all agents by default and passes only compact handoff information.

---

## 中文

Lean Dev Router 是一套用于协调和升级多 Agent 软件开发任务的通用理论。它让不同职责和成本层级的 Agent 分别负责规划、实施、诊断和验证，并且只在必要时向上升级。

我本人目前正在使用 Codex，因此本仓库使用 GPT 模型标识作为具体示例。这套路由理论不依赖 Codex 或 GPT，也可以迁移到其他 Agent 运行时和模型。

为了进一步节省 Token，可以配合 [Caveman](https://github.com/juliusbrussee/caveman) 这类减少工程中冗余表达的项目使用。Lean Dev Router 负责减少不必要的 Agent 调用和交接上下文，Caveman 负责减少 Agent 回复中的冗余措辞；两者结合可以在保留关键技术内容的同时，进一步提高 Token 使用效率。本项目目前暂不考虑重复实现这类项目已经提供的回复压缩功能。

由于各 Subagent 使用的模型明确、职责边界清晰且工作安排详细，主控对话通常可以使用 Luna High 或更低成本的模型。这是一条成本优化建议，而非硬性要求；当任务涉及复杂规划、重大架构决策或跨任务协调时，仍应使用更强的主控模型。

### 交接协议

三个角色统一使用以下紧凑、可解析的交接协议：

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

`EVIDENCE` 必须将仓库结论绑定到具体路径，并附简短 diff 摘要或命令结果。`PASS` 表示当前阶段完成；`BLOCKED` 表示缺少必要信息、权限或依赖；`ESCALATE` 表示需要其他角色继续处理。主控不得从缺少字段或证据的交接中自行推断成功。

### Codex 执行方式

默认使用 Codex 原生 subagent，由父 Codex 会话调用已配置的角色，并让有依赖的工作按顺序执行。只有相互独立的只读任务才使用并行 Agent；不得让多个 Agent 同时写入同一工作区。

在有依赖或写入的交接前，应确认目标 Agent 已加载、模型和思考强度生效，且首次结果遵循 `lean-dev-router/v1`。如果原生调用不可用或配置未生效，则按角色逐个使用独立 Codex session 作为 fallback；只传递紧凑交接、相关路径、约束和证据，写入时使用隔离 worktree 或分支。

条件允许时，在依赖原生路由前检查 `codex --version`；在 Codex CLI 中使用 `/agent` 检查 Agent 线程。如果客户端无法启动或无法提供预期的原生流程，应使用 fallback，不要静默替换为默认 Agent 或模型。

Codex 原生后台 Agent 界面仍属于原生 subagent 流程；其他后台进程或独立 session 只能作为 fallback，不能视为等价的父子路由。当前 Codex 自定义 Agent 的行为以[官方 Subagents 文档](https://learn.chatgpt.com/docs/agent-configuration/subagents)为准。

个人经验：推荐使用 worktree 批量并行处理相互独立的任务，尤其适合同时推进多个 PR。为每个任务分配独立的 worktree 和分支；对于强依赖任务，或必须共享同一工作状态的改动，不建议并行处理。

示例调度链：

```text
sol_planner → luna_worker → terra_auditor
                         ↘ sol_planner（仅用于无法解决或涉及重大决策的问题）
```

### 内容

- `.agents/skills/lean-dev-router/`：轻量级调度 Skill。
- `agents/`：`luna_worker`、`sol_planner` 和 `terra_auditor` 的示例 Agent 配置文件。
- `lean-dev-router-self-test-guide.md`：用于在自己的代码库中对比 Token 节省、质量和调度开销的受控测试指南。

### 安装

对于 Codex，将 `.agents/skills/lean-dev-router/` 复制到 `~/.codex/skills/lean-dev-router/`，再将 `agents/` 中的三个 TOML 文件复制到 `~/.codex/agents/`。使用其他运行时或模型时，应相应调整文件格式和模型标识。

### 角色

- `sol_planner`：负责初始规划，以及无法解决或涉及重大变动的决策。
- `luna_worker`：负责全部获授权的代码、测试、文档和配置编写与修改。
- `terra_auditor`：负责代码审计、技术诊断和验证；只有无法解决问题或需要重大决策时才升级给 Sol。

当任务适合采用这套路由策略时，可以使用 `$lean-dev-router`。该 Skill 不会默认调用全部 Agent，只传递精简的交接信息。
