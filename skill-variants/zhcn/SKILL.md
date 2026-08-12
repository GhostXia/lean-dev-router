---
name: lean-dev-router
description: 由 Sol 规划、父代理调度、Luna 实现、Terra 因果审计，以紧凑且可审计的交接处理仓库工程任务。
---

# Lean Dev Router

始终使用足够完成任务的最小代理池。Sol 规划并授权，父代理机械调度，Luna 写入，Terra 审计并提供因果证据和有界修复建议。

## 语言

跟随父任务的主要语言；未明确时使用任务中占主导的自然语言，没有自然语言信号时使用英文。代码、命令、路径、模型 ID、代理名和协议字段保持原样。

## 权限与入口

- 一切会产生改动的任务都先交给 `sol_planner`。Sol 确定目标、范围、验收、依赖、预算、写入契约、审计与路由。只有 Sol 能创建或修改 `DISPATCH`，也只有 Sol 能请求用户决策。
- Sol 不持续调度、不等待 worker，也不汇总常规事件。父代理不作工程判断，只执行已声明的状态机。未定义、不完整或改变契约的状态回到 Sol。
- Sol 按需确定可外部测量的延迟、尝试次数、规模和资源上限，以及已证明可重试的状态与公开接口、数据、安全不变量。私有 helper、命名和等价控制流由 Luna 决定。
- `luna_worker` 只执行有效契约，只作不改变契约的局部选择。只读的 `terra_auditor` 提供因果证据、审计发现和有界修复建议，不能授权写入。
- 明确的审计、诊断或证据优先调查从 Terra 开始；需要规划、授权或重大决策时加入 Sol。
- 部署、破坏性操作、外部承诺和产品政策不在本路由权限内，除非用户明确授权。

## 有界规划波次

Sol 输出紧凑的 `PLAN_MANIFEST`，其中只有全局不变量与当前就绪的 `DISPATCH_WAVE`。条目声明 id、角色、worktree、依赖、revision、复现证据、审计、状态转换、路由和下一个 `EXPANSION_GATE`。父代理只在扩展门或异常时再次请求 Sol。不要预先展开远期工作，也不要输出实现代码。Sol 不持续调度常规事件。

## 协议

Luna 只有收到以下完整入站契约后才能写入。

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

父代理原样转发。每个字段都非空；`DISPATCH_ID` 在该写入生命周期内唯一且稳定；planner 与 auditor 身份不同；路径必须相对仓库；不得遗留重大决策。Terra 指派是普通只读指令。它不使用出站结果信封或 `STATUS: DISPATCH`。该状态只属于 Luna 写入授权。授权缺失时 Luna 不进行实现或写入，返回 `FAILURE: missing_dispatch`。

各角色统一返回以下紧凑 schema，不得另加协议。

```text
PROTOCOL: lean-dev-router/v2
AGENT: luna_worker | terra_auditor | sol_planner
STATUS: PASS | BLOCKED | ESCALATE
FAILURE: none | missing_dispatch | scope | verification | dependency | ambiguity | major-decision
REQUEST: none | implementation | technical_resolution | planning_resolution | human_authority
EVIDENCE:
- path: relative/path/to/file
  proof: short diff summary or `command` -> PASS/FAIL
NEXT: parent
SUMMARY: one concise sentence
```

`PASS`、`BLOCKED`、`ESCALATE` 都不能授权写入。证据可用 `N/A (planning-only)`、`N/A (batch coverage)`、`N/A (scope-check)` 或 `N/A (integration-check)`。字段或证据缺失时，由原角色以 `FAILURE: verification` 修正结果。

父代理严格执行下表，任何自然语言都不能覆盖机械路由。

| AGENT | STATUS | REQUEST | 机械目的地 |
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

## 范围、产物与版本

`PATHS_ALLOW` 只授权持久写入。构建输出放在仓库外的临时目录。一次性产物根目录须预先声明，preflight 时不存在或为空，并在范围检查通过前删除。保留或未声明的普通、ignored、untracked 路径都会失败；产物绝不进入 revision 标识。

将每个 allow 条目一起传入。

```text
python scripts/check_scope.py --baseline <baseline> --allow <entry> ... --revision
```

每个条目各用一次 `--allow <paths_allow_entry>`。helper 检查 tracked、普通 untracked 和 ignored untracked 路径。helper 不可用时执行文档规定的三项 Git 枚举，不得编造 dirty revision。范围证据缺失或失败时拒绝 `PASS`。

范围通过后才能确定可审计状态。干净提交使用精确 commit SHA。dirty 状态使用 `worktree-sha256:<64 lowercase hex>`，输入为已解析 baseline、以 Git 二进制安全格式编码的全部授权 tracked 文本与二进制 diff，以及用安全 framing 编码的授权 untracked 路径与内容。相同状态必须复现相同 revision，任何修复都会改变 revision。拒绝 `<luna-revision>` 等占位符及只含 baseline 的 dirty key。

## 风险熔断与复现

首次调用 Luna 前，父代理仅一次执行 `<skill-dir>/scripts/runtime_guard.py start --state <external-scratch-state>` 并传入 `DISPATCH`。后续 `repair` 与 `audit` 共用该状态，禁止重启；Exit 2 表示目标调用数为零。`BUDGET` 是每个角色/阶段的硬预算，上限为 8 次调用、4 个假设、1200 秒模型主动时间、2 轮修复和 2 次停滞调用，Sol 只能收紧。外部等待不计主动时间，但命令必须设置 timeout。

每个 `event` 记录身份、revision/stage、调用、wall/active time、上游尝试、全部 token/cache families、假设、命令/错误、进展/证据与终止原因；guard 推导 uncached 与总 token。无新进展的重复失败必须停止；两次停滞构成确定性的 `spinning` 信号。停止状态锁存到 revision、契约或证据变化。Luna 预算耗尽转 Terra，Terra 预算耗尽转 Sol。父代理在 Luna 失败或中断后绝不修复或写入。

预算内每个失败 gate 最多三次实质不同的尝试。代码、配置、输入、环境、依赖、证据或可检验假设未变时，禁止原样重跑命令。技术不确定性请求 `technical_resolution`；缺工具、权限或网络请求依赖处理；越权写入属于 scope failure；baseline 漂移属于 verification failure。复现证据严格包含 cwd、环境差异、完整命令、退出码和紧凑结果，Terra 原样继承；缺一项则审计不完整。

`PASS` 前的技术诊断须携带 `DISPATCH_ID`、baseline、当前 diff/paths、失败假设与尝试、完整失败/复现证据、契约边界和剩余预算，不要求最终 scope 或 revision。技术证据不足时请求 `technical_resolution`，由父代理交给 Terra 处理。并发测试必须证明目标失败或竞争分支确实发生；sleep 只能用于轮询或兜底 timeout，不能单独作为同步证据。baseline 漂移立即停止写入并产生 verification blocker。

## 流式处理与预注册审计

独立组件的结果到达即处理，不等待无关 sibling；只有组合集成使用 all-component barrier。job key 固定为 `<component>:<revision>:<stage>`，状态为 `queued`、`running`、`complete` 或 `failed`，只重试缺失或失败的 key。`token-first` 可复用一名未参与实现的 Terra，但不得制造 sibling wait。有时间戳且有容量时须在 60 秒内启动，否则记录排队原因，并在第一个可用 slot 释放时启动。父代理执行长命令时仍须及时消费事件，并单独报告外部等待。

Sol 为每次审计预注册相同 `DISPATCH_ID`、组件、依赖、revision/job-key 规则、`TASK_OBJECTIVE`、`CHANGE_SCOPE`、更宽的 `AUDIT_SCOPE/IMPACT_CONE`、验收、复现证据和越界策略。Luna `PASS` 后，父代理验证 scope、具体 revision、依赖、复现证据和审计契约，随后直接启动 Terra，不经过常规 Luna-to-Sol-to-Terra 跳转。前置条件不完整或未定义时回到 Sol。

用 `runtime_guard.py audit` 登记；相同 revision 不得重复审计。首次完整审计，后续 revision 只审 delta 与既有发现。提前终止时父代理记录 `ACTION: abandon` 及原因，路由至 Sol，且绝不更新增量审计基线。

## Terra 因果审计与修复

Terra 沿因果影响锥读取 `PATHS_ALLOW` 之外的 caller/callee、数据/错误/资源流、配置、平台、兼容性、并发、安全、性能和测试。这只扩大读取范围，不授予写权限，也不允许无界扫描仓库。越界发现须给出路径、证据、因果关系、严重性、阻塞决定和责任归属。

- **A** 改动引起的验收缺陷，阻塞并修复。
- **B** 必要路径遗漏在 scope 外，返回 Sol。
- **C** 无关的既有缺陷，通常作为不阻塞的 follow-up。
- **D** 严重安全、数据丢失或兼容性风险，阻塞或升级。

契约不变的修复由 Terra 返回 `REQUEST: implementation`，并携带原 `PLAN_ID`、`DISPATCH_ID`、预注册的 `AUDITOR_INSTANCE_ID`、`CONTRACT_EFFECT: unchanged`、位于 `PATHS_ALLOW` 内的 `AFFECTED_PATHS`、原 `ACCEPTANCE`、顺序递增的 `REPAIR_CYCLE`、新 `REVISION` 和新的 `EVIDENCE_FINGERPRINT`。父代理核对 ID、Luna 证据、预注册审计和默认两轮修复预算，再机械地交回原 Luna。新状态取得新 revision 并重新审计。

任何 scope、plan、acceptance、constraint、公开接口、架构、安全边界、数据格式或资源限制变化，以及歧义或预算耗尽，都回到 Sol。Terra 自身绝不写修复。

## 集成

两个及以上写入 batch 必须声明共享契约、依赖顺序、`integration_worktree`、`integration_owner`、`integration_baseline`、`integration_paths_allow` 与 `integration_acceptance`。allow-list 初始值是已接受 batch 的精确并集。一名 Luna 按顺序合并已接受提交；冲突解决需要新的写入授权。整项任务 `PASS` 要求干净的组合状态、最终 scope、完整验收和所有已声明的最终审计。组件成功不能自动推出整体成功。

## 执行与用户门禁

并行 Luna writer 使用隔离 worktree；只读 Terra 可共享 checkout。默认代理池上限为 token-first 3、balanced 6、latency-first 10。Sol 无法嵌套 spawn 时，以 `BLOCKED/dependency/REQUEST implementation` 返回 literal manifest，父代理只负责机械转发，不能重新规划。

Sol 只决定固定契约内可逆的技术取舍。目标、范围、验收、政策，以及实质性的兼容性、安全、隐私、许可、迁移、成本或产品承诺，必须使用 `BLOCKED/major-decision/REQUEST human_authority`。Sol 至多给出三个选项、一个建议和一个问题；父代理原样交给用户，不得自行把回答转换成契约。

所有 manifest state、scope、revision、audit、repair、integration 和 final gate 都进入终态后停止。全部已声明终态 gate 通过时，父代理可直接总结，无须再次调用 Sol。不要默认调用每个角色，不要在证据未变时重复阶段，也不要让 Luna 或 Terra 调度同级代理。
