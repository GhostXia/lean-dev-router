# Lean Dev Router

这是一个面向项目开发的通用多 Agent 协作与升级理论：用不同职责和成本层级的 Agent 分担规划、执行、诊断与验证，并只在必要时向上升级。

我本人目前正在使用 Codex，因此仓库中的具体配置使用 GPT 模型作为例子；这套路由思想不依赖 Codex 或 GPT，也可以迁移到其他 Agent 运行时和模型。

示例调度链：

```text
sol_planner → luna_worker → terra_auditor
                         ↘ sol_planner (only for unresolved or major decisions)
```

## Contents

- `.agents/skills/lean-dev-router/`: the lightweight routing Skill.
- `agents/`: example Agent configuration files for `luna_worker`, `sol_planner`, and `terra_auditor`.

## Install

For Codex, copy `.agents/skills/lean-dev-router/` to `~/.codex/skills/lean-dev-router/`, then copy the three files in `agents/` to `~/.codex/agents/`. Adapt the file format and model identifiers when using another runtime.

The intended roles are:

- `sol_planner`: initial planning and unresolved or major decisions.
- `luna_worker`: all authorized code, test, documentation, and configuration edits.
- `terra_auditor`: code audit, technical diagnosis, and validation; escalate only when it cannot resolve the issue or a major decision is required.

Use `$lean-dev-router` when a task benefits from this routing policy. The Skill deliberately avoids invoking all agents by default and passes only compact handoff information.
