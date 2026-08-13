---
name: lean-dev-router
description: 由 Sol、父代理、Luna 和 Terra 通过确定性运行时门禁处理仓库工程。
---

# Lean Dev Router

使用最小代理池。跟随任务语言；代码、路径、ID、代理名和协议字面量保持原样。

## 权限与规划

改动任务从 `sol_planner` 进入。只有 Sol 能创建或改变目标、范围、验收、依赖、预算、写入契约、审计或路由。只有 `luna_worker` 能在完整 `DISPATCH` 下写入，且只能选择不改变契约的实现细节。只读 `terra_auditor` 提供因果证据或有界修复建议。父代理只验证并执行已声明的转换。未定义、不完整或改变契约的状态返回 Sol。

Sol 输出 `PLAN_MANIFEST` 和就绪的 `DISPATCH_WAVE`；每项声明 worktree、依赖、revision/复现、审计、路由和 `EXPANSION_GATE`。不得预展开；Terra 可诊断，但规划/授权返回 Sol。

契约声明的依赖准备仅限 Luna 执行；父代理和 Terra 绝不执行。未声明、缺失或超出契约的工具/依赖属于零执行：Luna 使用 `ESCALATE`/`technical_resolution` -> `parent:terra`，绝不使用 `BLOCKED/none`。初次或无产物执行只能使用 Sol 的 execution 路由；修复仍仅由 Terra 请求。

## 协议

只有以下完整入站契约能授权 Luna：

```text
PROTOCOL: lean-dev-router/v2
STATUS: DISPATCH
TARGET: implementation
DISPATCH_ID: stable unique component/write identifier
PLAN_ID: stable plan identifier
PLANNER_ROLE: sol_planner
PLANNER_INSTANCE_ID: immutable planner instance identifier
AUDITOR_INSTANCE_ID: independent auditor instance identifier
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

每个字段都非空；ID 保持稳定；planner 与 auditor 身份不同；路径相对仓库；不得遗留重大决策。Terra 指派是普通只读指令，不是出站结果信封或 `STATUS: DISPATCH`。授权缺失时返回 `FAILURE: missing_dispatch`，且实施调用数为零。

所有角色只返回：

```text
PROTOCOL: lean-dev-router/v2
AGENT: luna_worker | terra_auditor | sol_planner
STATUS: PASS | BLOCKED | ESCALATE
FAILURE: none | missing_dispatch | scope | verification | dependency | ambiguity | major-decision
REQUEST: none | execution | implementation | technical_resolution | planning_resolution | human_authority
EVIDENCE:
- path: relative/path/to/file
  proof: short diff summary or `command` -> PASS/FAIL
NEXT: parent
SUMMARY: one concise sentence
```

`PASS`、`BLOCKED`、`ESCALATE` 都不授权写入。证据可用 `N/A (planning-only)`、`N/A (batch coverage)`、`N/A (scope-check)` 或 `N/A (integration-check)`。无效输出由原角色以 `FAILURE: verification` 修正。父代理拒绝表外组合，并机械执行下表：

| AGENT | STATUS | REQUEST | Destination |
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

## 确定性入口与范围

任何 Luna 模型调用前，把完整 JSON `DISPATCH` 仅一次传给：

```text
python <skill-dir>/scripts/runtime_guard.py start --state <external-scratch-state>
```

`start` 原子执行预检并创建持久 guard 状态；正常执行不得再单独运行 preflight。无状态 `preflight` 子命令只用于验证模板或已安装运行时。Exit 2 表示目标调用数为零。后续 `event`、`execution`、`repair`、`audit` 复用同一状态，绝不重启。guard 只允许两次顺序递增、DISPATCH 与干净 BASELINE 不变且零产物的执行尝试；脏/改变/耗尽或已有证据的重试回 Sol。

`PATHS_ALLOW` 只授权持久写入；构建输出使用外部临时目录。调度方在 `start` 前验证一次性产物根为空，scope 前删除，且产物不进入 revision 标识。

接受 Luna `PASS` 前，独立枚举 tracked、标准 untracked 和 ignored untracked 路径。优先使用：

```text
python scripts/check_scope.py --baseline <baseline> --allow <entry> ... --revision
```

否则使用 NUL-safe Git 枚举。任何保留或未声明路径都以 `FAILURE: scope` 拒绝 `PASS`；父代理不创造清理权限。干净状态 revision 是精确 commit SHA。dirty 状态使用 `worktree-sha256:<64 lowercase hex>`，输入为已解析 baseline、授权 tracked 二进制安全 diff，以及 framed 授权 untracked 路径与内容。拒绝占位符和只含 baseline 的 dirty key；相同状态复现相同 revision，每次修复都改变它。

## 有界执行

`BUDGET` 是每个角色/阶段的硬上限；Sol 只能收紧运行时最大值：8 次模型调用、4 个假设、1200 秒模型主动时间、2 轮修复和 2 次停滞调用。命令必须有 timeout；外部等待不计模型主动时间。

每个 `event` 记录角色/身份、revision/stage、契约/证据指纹、调用、计时、上游尝试、token/cache families、假设、命令/错误、进展/证据和 outcome。guard 推导 uncached 与总 token。无变化的重复失败停止；两次停滞构成确定性 `spinning`。只有 revision、契约或证据变化才能解锁。Luna 耗尽转 Terra；Terra 耗尽转 Sol。父代理绝不修复或写入。

`parent:pause` 是零执行：父代理不得运行 `npm ci`、安装工具、修改环境、清除 latch 或恢复 Luna。`REQUEST: execution` 返回 `parent:luna`；`REQUEST: implementation` 仅表示 Terra 的契约不变修复。

预算内每个失败 gate 最多尝试三种实质不同的办法；不得重放未改变的命令。技术不确定性请求 `technical_resolution`；缺工具/权限/网络请求依赖处理；越权路径属于 scope failure；baseline 漂移属于 verification failure 并停止写入。

`PASS` 前技术升级携带 `DISPATCH_ID`、baseline、当前 diff/paths、假设/尝试、精确 cwd/环境/命令/退出码/结果复现、契约边界和剩余预算；不要求最终 scope/revision。Terra 原样继承。并发证据必须证明目标分支或竞争确实发生；sleep 只用于轮询或兜底 timeout。

## 流式审计与修复

独立组件结果到达即处理；只有组合集成使用 all-component barrier。job key 为 `<component>:<revision>:<stage>`，状态是 `queued`、`running`、`complete` 或 `failed`；只重试缺失/失败 key。`token-first` 可复用未参与实现的 Terra，不制造 sibling wait。有容量时 60 秒内启动 eligible work，否则记录排队并在第一个可用 slot 释放时启动。父代理执行长命令时仍消费事件，并单独报告外部等待。

Sol 为每次审计预注册相同 `DISPATCH_ID`、组件/依赖、revision/job 规则、`TASK_OBJECTIVE`、`CHANGE_SCOPE`、更宽的 `AUDIT_SCOPE/IMPACT_CONE`、验收、复现和越界策略。匹配的 Luna `PASS` 提供具体 revision、scope/replay 证据、显式依赖和 telemetry 后，父代理才直接启动 Terra；缺少执行或产物返回 `REQUEST: execution` 给 Luna，部分或矛盾证据不启动 Terra 而回 Sol。

通过 `runtime_guard.py audit` 登记；相同 revision 不得重复审计。首次审计完整执行；后续 revision 覆盖 delta 与未解决发现。提前终止记录 `ACTION: abandon`、路由 Sol，且绝不更新增量审计基线。

Terra 只可沿有界因果影响锥读取 `PATHS_ALLOW` 外的 callers/callees、数据/错误/资源流、配置、平台、兼容性、并发、安全、性能和测试。扩大读取不授予写入。每个越界发现给出路径、证据、因果、严重性、阻断决定和归属，并分类为 **A** 改动缺陷、**B** scope 遗漏（Sol）、**C** 无关既有缺陷或 **D** 严重安全/数据丢失/兼容性风险。

Terra 绝不安装/运行工具或修改环境。technical-resolution 只对带 `CONTRACT_EFFECT: unchanged` 的有界修复返回 `ESCALATE`/`implementation`；初次/无产物执行使用 `REQUEST: execution`，契约/依赖变化返回 `ESCALATE`/`planning_resolution` -> `parent:sol`。

契约不变的 A 类修复由 Terra 返回 `REQUEST: implementation`，携带原 `PLAN_ID`/`DISPATCH_ID`、预注册 `AUDITOR_INSTANCE_ID`、`CONTRACT_EFFECT: unchanged`、范围内 `AFFECTED_PATHS`、原 `ACCEPTANCE`、下一 `REPAIR_CYCLE`、新 `REVISION` 和新 `EVIDENCE_FINGERPRINT`。父代理验证身份、证据、审计登记、路径和预算，再机械交回原 Luna。新 revision 必须重审。任何 scope/plan/acceptance/constraint/公开接口/架构/安全/数据/资源变化、歧义或预算耗尽都返回 Sol；该修复路由独立于初始执行。

## 集成与完成

两个及以上写入 batch 声明共享契约、依赖顺序、`integration_worktree`、`integration_owner`、`integration_baseline`、`integration_paths_allow` 和 `integration_acceptance`。allow-list 初始值是已接受 batch 的精确并集。一名获授权 Luna 按序集成已接受提交；冲突需要新授权。整项 `PASS` 要求干净组合状态、最终 scope、完整验收和全部已声明最终审计；组件成功不能自动推出整体成功。

并行 Luna writer 使用隔离 worktree；只读 Terra 可共享 checkout。池上限为 token-first 3、balanced 6、latency-first 10。Sol 无法嵌套 spawn 时，返回带 literal manifest 的 `BLOCKED/dependency/REQUEST execution`；父代理只转发，不重新规划。

Sol 只决定固定契约内可逆的技术取舍。目标、范围、验收、政策或实质性的兼容性/安全/隐私/许可/迁移/成本/产品承诺必须使用 `BLOCKED/major-decision/REQUEST human_authority`；Sol 至多给三个选项、一个建议和一个问题。所有 manifest、scope、revision、audit、repair、integration 和 final gate 终止后停止。全部声明 gate 通过时，父代理直接总结，无须再调用 Sol。不要默认调用每个角色、重复无变化阶段，或让 Luna/Terra 调度同级代理。
