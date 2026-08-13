---
name: lean-dev-router
description: 通过 Sol 例外规划、受限 Terra High parent 快速路径、Luna 实施与独立 Terra 审计路由仓库工程。
---

# Lean Dev Router

使用最小角色池：Sol 负责例外，parent 调度，Luna 写入，Terra 审计。

## 语言

遵循父任务的主要语言；没有信号时使用英文。代码、命令、路径、模型 ID 和 Agent 名称保持不变。

## 权限与入口

- Sol 固定目标、范围、验收、依赖、预算、契约、审计与路由；只有 Sol 可以签发或修改 Sol DISPATCH，或请求 human_authority。
- parent 只是机械调度器，只能使用下述条件式 Terra High 主模型能力；不得自行发明架构、范围、验收、约束、风险决策或产品政策。
- Luna 在完整入站 DISPATCH 下是唯一写入者。Terra 独立且只读；最终审计只能由预注册的 terra_auditor 执行。
- 部署、破坏性操作、外部承诺和用户政策不属于本路由授权。

## 有界规划波次

Sol 输出包含全局不变量和可执行 DISPATCH_WAVE 的 PLAN_MANIFEST，每项声明 worktree、依赖、revision、复现、审计、路由和 EXPANSION_GATE。parent 不预展开远期工作；未定义或改变契约的状态返回 Sol。

## 协议

parent 必须原样转发下面完整入站契约后 Luna 才能写入。`PLANNER_CAPABILITY` 是条件字段：普通 Sol 包保持兼容；快速路径使用 `PLANNER_ROLE: parent` 与下列精确能力。

```text
PROTOCOL: lean-dev-router/v2
STATUS: DISPATCH
TARGET: implementation
DISPATCH_ID: stable unique component/write identifier
PLAN_ID: stable plan identifier
PLANNER_ROLE: sol_planner | parent
PLANNER_CAPABILITY: bounded_l1_l2_dispatch (parent fast path only)
PLANNER_INSTANCE_ID: immutable planner or parent instance identifier
AUDITOR_INSTANCE_ID: independent terra_auditor instance identifier
TASK_SUMMARY: one bounded objective
BASELINE: commit hash
PATHS_ALLOW:
- relative/path/or/subtree
ACCEPTANCE:
- objective check and expected result
CONSTRAINTS:
- fixed implementation or compatibility bound
BUDGET:
  MODEL_CALL_LIMIT: positive integer
  HYPOTHESIS_LIMIT: positive integer
  MODEL_ACTIVE_SECONDS_LIMIT: positive integer
  REPAIR_CYCLE_LIMIT: positive integer
  STAGNANT_CALL_LIMIT: positive integer
NEXT: parent
```

选定角色所需字段必须非空，ID 稳定，planner 与 auditor 不同，路径必须是仓库相对路径。授权缺失时 Luna 不得检查实现或写入，返回 `FAILURE: missing_dispatch`。Terra 任务是普通只读指令，不是出站结果信封，也不能使用 `STATUS: DISPATCH`。

角色返回紧凑结果信封：

```text
PROTOCOL: lean-dev-router/v2
AGENT: luna_worker | terra_auditor | sol_planner
STATUS: PASS | BLOCKED | ESCALATE
FAILURE: none | missing_dispatch | scope | verification | dependency | ambiguity | major-decision
REQUEST: none | implementation | technical_resolution | planning_resolution | human_authority
EVIDENCE:
- path: relative/path/to/file
  proof: short diff summary or command -> PASS/FAIL
NEXT: parent
SUMMARY: one concise sentence
```

结果不会授权写入；证据可使用 `N/A (planning-only)`、`N/A (batch coverage)`、`N/A (scope-check)` 或 `N/A (integration-check)`。封闭 handoff 表是唯一依据：

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

parent 能力只是 Terra High 主模型前置条件，不是第四个子 Agent，也不是第二个 Sol。runtime guard 只有在证据明确且固定时才接受：

- `PLANNER_ROLE: parent` 且 `PLANNER_CAPABILITY: bounded_l1_l2_dispatch`；`LEVEL` 为 L1 或 L2；`OBJECTIVE_FIXED`、`OPEN_MAJOR_DECISIONS` 与所有变更标记必须是精确布尔值。
- `BASELINE`、`SCOPE_ROOTS`、`ACCEPTANCE`、`CONSTRAINTS` 非空；`RISK_FLAGS`、`EXTERNAL_ACTIONS` 为 none；禁止架构、安全、兼容性、契约、范围、验收和约束变更。
- `MAX_DISPATCHES=1`、`COMPONENT_COUNT=1`、`WRITE_BATCH_COUNT=1`、`DEPENDENCY_DEPTH=0`；`INTEGRATION`、`CONFLICT`、`CONTRACT_EXPANDED`、`AMBIGUITY` 必须显式 false/none。
- `PATHS_ALLOW` 非空，`REQUIRED_PATHS` 可为空，但允许和必需路径都必须位于固定仓库相对 `SCOPE_ROOTS` 内。
- parent 上限是 4 次模型调用、2 个假设、600 秒主动时间、1 次修复、1 次停滞。证据缺失或不合资格在 Luna 前失败并路由 `parent:sol`。

L3、风险、冲突/集成、多批次、B/D 发现、歧义、耗尽，或契约/范围/验收/约束/架构/安全/兼容性变化都路由 parent:sol。B 发现不得进入 Luna 修复。普通 Sol DISPATCH 保持 v2 兼容并使用 8/4/1200/2/2 上限。

## 范围、产物与版本

`PATHS_ALLOW` 只授权持久写入，相关路径仅是可读上下文。构建产物放在仓库外 scratch，或在验收前删除的临时产物根目录。接受 PASS 前运行 `python scripts/check_scope.py --baseline <baseline> --allow <entry> ... --revision`，不可用时记录三条 Git fallback 枚举。干净状态使用提交 SHA；授权脏状态使用 `worktree-sha256:<64 lowercase hex>`。

## 风险熔断与复现

`runtime_guard.py start --state <external-scratch-state>` 原子执行预检并初始化状态；`runtime_guard.py audit` 注册最终审计，修复包复用同一状态且不得重启。Guard 记录调用、主动/墙钟时间、上游尝试、token、假设、进展、错误和身份。无新证据的重复失败、spinning、预算耗尽或 baseline 漂移都会 fail-closed。复现证据包含 cwd、环境差异、完整命令、退出码和紧凑结果。

## Terra 因果审计与修复

最终审计在 Luna 前预注册，只能由独立 `terra_auditor` 执行；parent 不得自审。Terra 检查 diff 及因果调用者/被调用者、数据/错误/资源流、配置、平台、兼容性、并发、安全、性能和测试。每个发现带路径、证据、因果、严重性、阻断决定和负责人：

- **A** 是改动造成的验收缺陷；只有 `CONTRACT_EFFECT: unchanged`、匹配 DISPATCH_ID、范围内 AFFECTED_PATHS、验收不变且预算剩余时才可返回 Luna。
- **B** 是完成目标所需但遗漏的范围，**D** 是严重安全/数据丢失/兼容风险；二者均路由 parent:sol，不得进入 Luna 修复。**C** 是无关既有问题，通常仅跟进。

## 集成

两个或更多写入批次必须声明 `integration_owner`、`integration_baseline`、`integration_paths_allow`、`integration_acceptance`、依赖顺序和干净 integration worktree。组件 PASS 不等于整体 PASS。冲突或兼容性改动需要新的 Sol 授权写批次；组合态使用 `N/A (integration-check)` 与 `N/A (scope-check)` 证据。

## 执行与用户门禁

并行 Luna 写入使用隔离 worktree；只读 Terra 可以共享 checkout。只有 EXPANSION_GATE、例外、谓词失败或用户决策才召回 Sol。目标、产品、政策、架构、安全、兼容性、许可、迁移、成本或不可逆选择通过 parent 返回 human_authority。

## 内容

| 路径 | 说明 |
|:---|:---|
| `.agents/skills/lean-dev-router/` | 路由 Skill 与确定性 runtime guard |
| `skill-variants/` | 英文主版本、中文版本与优化变体 |
| `agents/` | 三个子配置：`luna_worker`、`sol_planner`、`terra_auditor` |
| `scripts/validate_repo.py` | 无依赖仓库一致性检查 |
| `lean-dev-router-self-test-guide.md` | 路由与范围证据测试指南 |

## 角色

| 角色 | 职责 |
|:---|:---|
| **parent** | 机械调度；仅可使用受限 Terra High 主模型快速路径 |
| **sol_planner** | 例外规划、DISPATCH 授权与用户决策门禁 |
| **luna_worker** | 在 PATHS_ALLOW 内唯一写入者 |
| **terra_auditor** | 独立只读因果审计与修复建议 |

## 最终门禁

运行 `python scripts/validate_repo.py` 与 `python -m unittest discover -s tests -v`。确认主 Skill 与英文变体完全相等、变体结构和大小合规、只有三个子配置、路由封闭、parent 谓词严格、最终 auditor 独立、集成范围干净且 revision 具体后再报告完成。
