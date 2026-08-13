---
name: lean-dev-router
description: lean-dev-router 的紧凑 parent 快速路径。
---

# Lean Dev Router

Sol 规划例外；parent 调度；Luna 写入；Terra 审计。

## 协议

parent 原样转发完整 v2 DISPATCH。`PLANNER_CAPABILITY: bounded_l1_l2_dispatch` 只对 parent 条件生效；普通 Sol 包保持兼容。

```text
PROTOCOL: lean-dev-router/v2
STATUS: DISPATCH
TARGET: implementation
DISPATCH_ID: stable identifier
PLAN_ID: stable plan
PLANNER_ROLE: sol_planner | parent
PLANNER_CAPABILITY: bounded_l1_l2_dispatch (parent only)
PLANNER_INSTANCE_ID: immutable planner identity
AUDITOR_INSTANCE_ID: independent terra_auditor identity
TASK_SUMMARY: bounded objective
BASELINE: commit hash
PATHS_ALLOW:
- relative/path
ACCEPTANCE:
- objective check
CONSTRAINTS:
- fixed bound
BUDGET:
  MODEL_CALL_LIMIT: positive integer
  HYPOTHESIS_LIMIT: positive integer
  MODEL_ACTIVE_SECONDS_LIMIT: positive integer
  REPAIR_CYCLE_LIMIT: positive integer
  STAGNANT_CALL_LIMIT: positive integer
NEXT: parent
```

```text
PROTOCOL: lean-dev-router/v2
AGENT: luna_worker | terra_auditor | sol_planner
STATUS: PASS | BLOCKED | ESCALATE
FAILURE: none | missing_dispatch | scope | verification | dependency | ambiguity | major-decision
REQUEST: none | implementation | technical_resolution | planning_resolution | human_authority
EVIDENCE:
- path: relative/path
  proof: command -> PASS/FAIL
NEXT: parent
SUMMARY: concise result
```

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
| `sol_planner` | `BLOCKED` | `implementation` | `parent:luna` |
| `sol_planner` | `BLOCKED` | `human_authority` | `parent:user` |

## 快速路径资格

- 仅接受 L1/L2、固定目标/验收/约束，无重大决策、风险、外部操作、集成、冲突、歧义、扩展或架构/安全/兼容性变化。
- 只能有一个组件、一个 dispatch、一个写批次，依赖深度 0，允许/必需路径均在固定 SCOPE_ROOTS 内。
- parent 上限为 4 次调用、2 个假设、600 秒主动时间、1 次修复、1 次停滞；证据缺失在 Luna 前路由 parent:sol。
- L3、B/D、耗尽或契约/范围变化路由 parent:sol；B 不得进入 Luna 修复。最终审计只能由独立 terra_auditor 执行。

## 集成

使用 PLAN_MANIFEST、DISPATCH_WAVE 和 EXPANSION_GATE。两个批次必须声明 integration_owner、integration_baseline、integration_paths_allow、integration_acceptance，并记录 N/A (batch coverage)、N/A (scope-check)、N/A (integration-check) 证据。

## 最终门禁

运行 runtime_guard.py start、runtime_guard.py audit、`python scripts/validate_repo.py` 和 unittest。范围证据使用 `python scripts/check_scope.py`；脏 revision 使用 `worktree-sha256:<64 lowercase hex>`。Terra A 修复必须有 CONTRACT_EFFECT: unchanged。
