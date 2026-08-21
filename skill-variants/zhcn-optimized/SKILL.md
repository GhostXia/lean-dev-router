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
REQUEST: none | execution | implementation | technical_resolution | planning_resolution | human_authority
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
| `sol_planner` | `BLOCKED` | `execution` | `parent:luna` |
| `sol_planner` | `BLOCKED` | `human_authority` | `parent:user` |

## 快速路径资格

- packet 能力字段不能证明授权。parent packet 要求宿主在 packet 外向 runtime guard 传入 `--trusted-parent-instance-id <id> --trusted-parent-model gpt-5.6-terra --trusted-parent-reasoning-effort high`，并与 PLANNER_INSTANCE_ID 和 Terra High 配置匹配，否则在 Luna 前失败。这是协调身份绑定，不是密码学证明。
- 仅接受 L1/L2、固定目标/验收/约束，无重大决策、风险、外部操作、集成、冲突、歧义、扩展或架构/安全/兼容性变化。
- 只能有一个组件、一个 dispatch、一个写批次，依赖深度 0，允许/必需路径均在固定 SCOPE_ROOTS 内。
- parent 上限为 4 次调用、2 个假设、600 秒主动时间、1 次修复、1 次停滞；证据缺失在 Luna 前路由 parent:sol。
- L3、B/D、耗尽或契约/范围变化路由 parent:sol；B 不得进入 Luna 修复。
- 最终审计是条件式能力。PLAN_MANIFEST 声明、任一风险标记或 integration gate 要求审计时，签发方必须在 Luna 前预注册合同；Luna PASS 后 runtime `audit begin` 才启动独立 terra_auditor，parent/planner 不得自审。
- Audit begin/complete/abandon 必须携带 `AUDITOR_ROLE: terra_auditor`、预注册的 `AUDITOR_INSTANCE_ID` 和匹配的实际执行 `AGENT_INSTANCE_ID`，按大小写无关规则规范化并核对 Terra 角色租约。字段缺失或不匹配即 fail-closed；这是协调约束，不是密码学认证。
- 依赖准备仅限 DISPATCH 明确声明后由 Luna 执行。缺失或契约外依赖以 ESCALATE/technical_resolution 交给只读 Terra；parent:pause 不允许安装、修改环境、清除 latch 或恢复 Luna。初始执行和一次有权威零产物记录的重试使用 REQUEST: execution。最终审计要求已登记执行、明确产物状态、匹配的 Luna PASS 和完整匹配 telemetry。
- 可选的 `routing_memory.py decide` 在确定性门禁固定 ELIGIBLE_ACTIONS 后记录建议 action；只有宿主验证的 feedback 才更新按策略版本隔离的仓库外 memory。它不扩大权限，且只有两个选择都积累足够相似证据后才改变默认值。

## 集成

使用 PLAN_MANIFEST、DISPATCH_WAVE 和 EXPANSION_GATE。两个批次必须声明 integration_owner、integration_baseline、integration_paths_allow、integration_acceptance 和最终组合态 Terra 审计，并记录 N/A (batch coverage)、N/A (scope-check)、N/A (integration-check) 证据。

## 最终门禁

Luna 前运行 runtime_guard.py start，由它原子登记第 1 次执行。宿主必须通过 runtime `event` 提交终态 PRODUCT_COUNT 以及精确的调用/时间/token telemetry；仓库单元测试只证明 guard 逻辑，不证明宿主集成。parent 快速路径还传入上述宿主持有的 instance/model/reasoning 参数。非法 packet 在 Luna 前路由 parent:sol；若 Luna 被错误调用，则不得检查或写入，并返回 BLOCKED/none 到 parent:pause。仅在声明审计时，于 Luna PASS 后运行 runtime `audit begin`。随后运行 `python scripts/validate_repo.py` 和 unittest。范围证据使用 `python scripts/check_scope.py`；脏 revision 使用 `worktree-sha256:<64 lowercase hex>`。Terra A 修复必须有 CONTRACT_EFFECT: unchanged。
