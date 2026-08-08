# Lean Dev Router

## English

Lean Dev Router is a general theory for coordinating and escalating multi-agent software development work. It assigns planning, implementation, diagnosis, and validation to agents with different responsibilities and cost levels, escalating only when necessary.

I currently use Codex, so this repository uses GPT model identifiers as concrete examples. The routing theory is not tied to Codex or GPT and can be adapted to other agent runtimes and models.

For further token savings, this router can be combined with projects such as [Caveman](https://github.com/juliusbrussee/caveman), which reduce unnecessary verbosity in engineering workflows. Lean Dev Router reduces unnecessary agent calls and handoff context; Caveman reduces unnecessary prose in agent responses. Together, they can help maximize token efficiency while preserving the technical content that matters. This project currently does not plan to duplicate response-compression features already provided by such projects.

Example routing chain:

```text
sol_planner → luna_worker → terra_auditor
                         ↘ sol_planner (only for unresolved or major decisions)
```

### Contents

- `.agents/skills/lean-dev-router/`: the lightweight routing Skill.
- `agents/`: example Agent configuration files for `luna_worker`, `sol_planner`, and `terra_auditor`.

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

示例调度链：

```text
sol_planner → luna_worker → terra_auditor
                         ↘ sol_planner（仅用于无法解决或涉及重大决策的问题）
```

### 内容

- `.agents/skills/lean-dev-router/`：轻量级调度 Skill。
- `agents/`：`luna_worker`、`sol_planner` 和 `terra_auditor` 的示例 Agent 配置文件。

### 安装

对于 Codex，将 `.agents/skills/lean-dev-router/` 复制到 `~/.codex/skills/lean-dev-router/`，再将 `agents/` 中的三个 TOML 文件复制到 `~/.codex/agents/`。使用其他运行时或模型时，应相应调整文件格式和模型标识。

### 角色

- `sol_planner`：负责初始规划，以及无法解决或涉及重大变动的决策。
- `luna_worker`：负责全部获授权的代码、测试、文档和配置编写与修改。
- `terra_auditor`：负责代码审计、技术诊断和验证；只有无法解决问题或需要重大决策时才升级给 Sol。

当任务适合采用这套路由策略时，可以使用 `$lean-dev-router`。该 Skill 不会默认调用全部 Agent，只传递精简的交接信息。
