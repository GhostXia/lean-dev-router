# Lean Dev Router 中文使用说明

> 本文档仅供人类阅读。可执行运行时以英文的 `.agents/skills/lean-dev-router/SKILL.md` 与 `agents/*.toml` 为唯一准则；本文档不会参与 Skill 或 Agent 的装配，也不定义机器可读取的行为。

[返回英文 README](../../README.md)

## 项目定位

Lean Dev Router 用三个职责不同的角色处理仓库内的软件工程任务：

- `sol_planner`（`gpt-5.6-sol`，medium）：例外与复杂任务的工程方案、普通 DISPATCH 授权、契约和用户决策门。
- `luna_worker`（`gpt-5.6-luna`，max）：唯一写入者；仅在收到完整标准 `DISPATCH` 后实施与验证改动。
- `terra_auditor`（`gpt-5.6-terra`，high，只读）：独立因果审计、诊断和不带写授权的最小修复建议。

Terra High 父会话默认负责调度、排队、转交和面向用户的控制，不自行扩大工程决策。它不是第四个 Agent/profile；只有满足下述严格条件时，才拥有一次有界 L1/L2 dispatch 能力。Sol 的规划采用有界波次：每次只输出全局不变量、当前可执行的 `DISPATCH_WAVE` 与下一次 `EXPANSION_GATE`。

目标不是每次都调用全部角色，而是用满足任务需要的最小组合完成工作。严格单批 L1/L2 可走 parent 快速路径；证据缺失、条件不合格、模糊、跨模块、风险或需要分批集成的任务，在 Luna 前回 Sol。

## parent 模型建议

启用有界 parent 快速路径时，建议使用性能和成本居中的模型，例如 `gpt-5.6-terra`，并将推理强度设置为 **high**。这里的“中档模型”和“high 推理强度”是两个不同维度：模型家族决定总体能力与计费档位，reasoning effort 决定该模型在当前调用上投入多少推断。推荐的折中配置因此是 **Terra High**，而不是依靠超长提示词补偿弱模型，也不是让 Sol 作为常驻 parent。

Terra High 的意义在于让 parent 有足够能力理解和规范化用户意图、发现证据缺失或互相矛盾、避免错误转述、选择已经定义好的正确路径，并让合格的低风险任务无需先支付一次 Sol 规划调用就能闭环。架构、范围扩张、风险接受、兼容性、多批集成和其他例外仍由 Sol 处理。如果直接让 Sol 充当 parent，等待、排队、telemetry 记录和普通转发也会持续消耗 Sol 档位 token；如果让能力更弱的模型启用快速路径，则更容易误判 eligibility 或生成不合格 DISPATCH。

建议按以下边界配置：

| parent 配置 | 可以承担的职责 | 有界 DISPATCH 权限 |
|:---|:---|:---|
| 更弱或更低成本模型 | 原样转发已固定契约、等待、排队、展示结果、执行确定性 destination 表 | **关闭**；凡是需要语义判断的任务都回 Sol |
| `gpt-5.6-terra` + high reasoning | 机械调度，加上语义资格判断、忠实整理既定契约，以及一个严格 L1/L2 批次 | 只有全部快速路径谓词和缩减预算通过时才**开启** |
| `gpt-5.6-sol` 作为 parent | 能力足够，但不推荐作为常驻配置 | 默认避免；仅在声明的规划门或例外门把 Sol 作为子代理调用 |

Terra High parent 的自主权仍然很窄：它可以在协议已经定义的路径之间做判断，也可以签发下文规定的一个有界 packet；但不能凭空制定验收、扩大路径、决定架构或政策取舍、忽略风险标志、把失败条件解释成“差不多可以”、亲自写代码，或承担自己的最终审计。只要资格事实存在不确定性，正确结果就是 `parent:sol`，不能尝试性调用 Luna。

模型身份和 reasoning effort 属于宿主配置。仓库 validator 和 runtime guard 能检查 packet、预算、身份隔离和路由证据，却无法证明宿主实际上给 parent 分配了哪个模型；使用者必须在仓库外把 parent 配置为 Terra High。若替换成其他模型家族，应保持相同权限边界，并用受控 A/B 测试比较错误路由率、不合格或被拒绝的 dispatch、非必要 Sol 调用、修复轮次、模型主动时间和未缓存总 token，而不能只看 token 数量。

## parent 快速路径

快速路径必须同时使用 `PLANNER_ROLE: parent` 与 `PLANNER_CAPABILITY: bounded_l1_l2_dispatch`；宿主调用 `preflight` 或 `start` 时还必须在 packet 外传入 `--trusted-parent-instance-id <id> --trusted-parent-model gpt-5.6-terra --trusted-parent-reasoning-effort high`，runtime guard 将身份与 `PLANNER_INSTANCE_ID` 及 Terra High 配置绑定。缺失或不匹配会 fail-closed；这是协调层身份绑定，不是密码学证明。之后所有资格证据还必须显式且固定：

- `LEVEL` 只能是 L1/L2；`OBJECTIVE_FIXED` 为 true；`OPEN_MAJOR_DECISIONS` 与全部 change flag 都是精确布尔值。
- `BASELINE`、仓库相对的 `SCOPE_ROOTS`、`PATHS_ALLOW`、`ACCEPTANCE`、`CONSTRAINTS` 非空且固定；`REQUIRED_PATHS` 可为空，但 allowed/required 路径必须都在 `SCOPE_ROOTS` 内。
- `RISK_FLAGS` 与 `EXTERNAL_ACTIONS` 为 none；架构、安全、兼容、契约、范围、验收和约束变化全部为 false。
- `MAX_DISPATCHES`、`COMPONENT_COUNT`、`WRITE_BATCH_COUNT` 都是 1，`DEPENDENCY_DEPTH` 是 0；`INTEGRATION`、`CONFLICT`、`CONTRACT_EXPANDED`、`AMBIGUITY` 显式为 false/none。
- 硬上限依次为 **4 次模型调用、2 个假设、600 秒模型主动时间、1 轮修复、1 次停滞调用**。

runtime guard 在启动 Luna 前拒绝缺失或不合格证据，并路由 `parent:sol`。L3、风险、冲突/集成、多组件、多 dispatch、多写批、歧义、契约扩张或其他 change flag，以及预算耗尽都回 Sol。B/D 是 **Terra 审计后的 finding 分类**，不是 Luna 前的 eligibility 输入；审计发现 B 或 D 时回 Sol，绝不能直接进入 Luna 修复。

## 交接协议怎么读

协议把“入站执行授权”和“出站结果”分开。Luna 写入前必须收到父会话原样转发的完整契约：

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

普通 Sol packet 不含 `PLANNER_CAPABILITY`，继续兼容 v2。parent packet 还必须携带上一节的 eligibility 字段；这些字段只表达资格，不能自行证明授权。宿主还必须在 packet 外向 runtime guard 传入上述 trusted instance/model/reasoning 上下文，并与 `PLANNER_INSTANCE_ID` 和 Terra High 匹配。字段缺失、绑定缺失或不匹配、以及其他非法情况都会在 Luna 启动前路由 `parent:sol`。若 Luna 在防御场景下仍被误调用，它不得检查或写入，并返回 `BLOCKED/none` 到 `parent:pause`。

三个角色统一返回独立的出站结果契约：

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

Agent 返回的出站交接包含状态、失败类型、能力请求、证据、固定的 `NEXT: parent` 和一句摘要。重点检查三件事：

1. 状态为成功时，失败类型必须为空。
2. 仓库结论必须绑定真实文件路径或明确的仓库级检查结果。
3. `REQUEST` 只描述下一步需要的能力，不点名其他 worker；父会话按“当前角色 + 能力请求”的固定表转发，不能根据证据自由推断路由。

`PASS`、`BLOCKED`、`ESCALATE` 都只是结果，不能作为写入授权；`PLAN_READY` 也不是执行状态。

封闭 handoff 表是唯一合法路由：

| `AGENT` | `STATUS` | `REQUEST` | 机械目的地 |
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

升档仍由固定状态机执行，但不再让所有结果先绕回 Sol。Luna `PASS` 后，父会话机械核验范围、稳定 revision、依赖与 replay；若签发方已预注册审计，则直接启动独立 Terra。只有满足同一 dispatch、契约/验收不变、路径在范围内且修复预算尚存的 A finding 可交回原 Luna；B/D、范围、方案、验收、公共接口、架构、安全边界、数据格式、资源限制、歧义或耗尽都回 Sol。只有 Sol 可以请求用户决策。

`lean-dev-router/v2` 与 v1 不兼容：v2 强制要求 `REQUEST`，并禁止在 `NEXT` 中点名具体 Agent。协调者必须拒绝混用版本的交接，不能自动猜测或静默转换。

从 v1 迁移时，应一次性替换 Skill 和三个 Agent TOML，把保存的协议模板改为 v2，为每个出站结果增加合法的 `REQUEST`，并把具名的出站 `NEXT` 改为 `NEXT: parent`。不要把进行中的 v1 交接链直接续接为 v2；结束或停止旧链后，从新的 v2 协调会话开始。

协议的精确定义只维护在英文 Skill 中，避免中英文副本漂移。

## 路径范围检查

`scripts/check_scope.py` 用来检查一个写入批次是否只修改了允许的路径。它会同时收集：

- 从基线开始的 tracked 改动；
- 未被忽略的 untracked 文件；
- 被忽略的 untracked 文件。

工作树模式示例：

```bash
python scripts/check_scope.py \
  --baseline <baseline-commit> \
  --allow src \
  --allow tests \
  --revision
```

组合提交模式示例：

```bash
python scripts/check_scope.py \
  --baseline <integration-baseline> \
  --end <combined-commit> \
  --allow src \
  --allow tests
```

输出与退出码保持稳定：

- `SCOPE: PASS`，退出码 `0`：所有发现的路径都在允许范围内。
- `SCOPE: FAIL`，退出码 `1`：存在范围外路径。
- `SCOPE: BLOCKED`，退出码 `2`：Git、提交或其他依赖不可用。

范围通过后，干净提交输出精确 commit SHA；脏工作树输出 `worktree-sha256:<64位小写十六进制>`，覆盖基线、授权 tracked diff 以及授权的普通/ignored untracked 路径与内容。相同状态必须得到相同 revision，任何返工必须改变 revision。禁止用 `<luna-revision>` 或基线 SHA 冒充脏状态标识。

`PATHS_ALLOW` 只授权持久产物。构建输出应放在仓库外；必须留在仓库中的一次性 artifact 要预先声明、开工前为空，并在范围检查前清除。保留或未声明的普通/ignored untracked 文件都会失败，artifact 不参与 revision。

脚本使用 Git 的 NUL 分隔输出读取路径，因此不会把中文、空格、换行或其他特殊字符误当成显示层转义文本。

脚本不可用时，协调者仍必须执行等价的 Git fallback 检查。工作树批次分别枚举 tracked、普通 untracked 和 ignored untracked 路径：

```bash
git diff --name-only --no-renames <baseline> --
git ls-files --others --exclude-standard
git ls-files --others --ignored --exclude-standard
```

组合提交把第一条命令改为 `git diff --name-only --no-renames <integration-baseline> <combined-commit> --`，并在干净的 integration worktree 中继续检查两类 untracked 路径。所有发现的路径都必须与完整 allow-list 比对并记录等价范围证据；脚本与 fallback 的验收语义相同。

## 流式组件调度

多个互不依赖的组件并行时，父会话在每个结果到达时立即执行 manifest 中已声明的下一步，不等待无依赖的同批 worker，也不例行回 Sol。只有组合集成与最终组合态审计允许设置全组件屏障。`token-first` 可以复用同一名未参与实现的 Terra，但不能因此等待其他组件。

组件审计使用稳定的 `<component>:<revision>:<stage>` 任务键；相同 revision 只能注册一次。revision 改变后只增量审计差异、未关闭发现与受影响因果面，首次审计覆盖完整声明范围。批量创建部分失败时只重试缺失或失败项。Sol 保留为方案与例外决策端，不作为常驻协调者。

Terra 的读取范围必须宽于改动范围：沿调用关系、数据/错误/资源流、配置、平台兼容、并发、安全、性能与测试调查。审计发现分为 A（改动导致的验收缺陷）、B（完成目标所需但遗漏的路径）、C（无关既存问题，通常仅跟进）、D（严重安全/数据丢失/兼容风险）。只有 dispatch 身份相同、契约/验收不变、affected paths 在范围内且仍有修复预算的 A 可返原 Luna；B、D 与任何契约变化都回 Sol。最终审计是条件式门禁，不要求每个任务都执行：PLAN_MANIFEST、任一风险标记或 integration gate 声明需要时，签发方必须在 Luna 前预注册审计合同；Luna `PASS` 且机械门禁通过后，parent 才运行 runtime `audit begin` 并启动身份独立的 `terra_auditor`。每个 audit begin/complete/abandon 包都携带 `AUDITOR_ROLE: terra_auditor`、预注册的 `AUDITOR_INSTANCE_ID` 和匹配的实际执行 `AGENT_INSTANCE_ID`；大小写无关身份或角色租约不一致均 fail-closed。这些字段是协调约束，不是密码学认证。已声明的最终审计不得由 parent 或 planner 自审。

父会话在首次 Luna 调用前只执行一次 Skill 内置的 `scripts/runtime_guard.py start`；`start` 原子完成确定性预检、状态初始化并登记第 1 次执行，正常执行不得再增加一次独立 preflight。无状态 `preflight` 子命令只用于验证模板与已安装运行时。后续零产物重试、返工和审计在同一状态文件上使用相应子命令，不能重建状态。普通 Sol dispatch 的上限依次为 8 次模型调用、4 个不同假设、1200 秒模型主动时间、2 轮返工和 2 次停滞调用；parent 快速路径为更严格的 4/2/600/1/1，签发方只能收紧。每次调用记录角色/阶段、wall/主动时间、上游尝试、各类 token、假设、命令/错误及进展/证据。同一失败没有进展立即停止；达到适用的停滞上限触发 `spinning`。只有 revision、契约版本或证据改变才能解锁；任何耗尽都回 Sol，父会话不得代写。

每次 Luna 终止后，宿主必须提交一条来自宿主的 runtime `event`，其中显式包含 `PRODUCT_COUNT` 和精确的调用次数、模型主动/墙钟时间、上游尝试及全部 token/cache telemetry。缺少产物字段表示未知，绝不能当作零；缺少完成 telemetry 时暂停，不能静默重试。最终审计必须核对已登记执行、有产物且匹配的 Luna PASS、具体 revision、scope/replay/依赖证据，以及完整 telemetry 的精确一致性。仓库单元测试使用合成事件，只证明 guard 逻辑，不证明 Codex 宿主或其他 harness 已安装这些生命周期 hook。

依赖准备只能由 Luna 执行，而且必须由 DISPATCH 明确声明。缺失或契约外依赖由 Luna 以 `ESCALATE/technical_resolution` 交给只读 Terra；`parent:pause` 不授权安装、修改环境、清除 latch 或恢复 Luna。Terra 可以返回契约不变的有界建议；依赖声明或其他契约变化必须回 Sol。初始执行和一次同 DISPATCH 的零产物重试使用结构化 `execution` 能力，不能用返工黑话代替。

宿主能提供时间戳时，记录组件就绪与下一阶段启动时间。有空闲容量时应在 60 秒内启动；否则记录排队状态与原因，并在第一个符合条件的槽位释放时启动。把编译、CI、网络等外部等待与可控 handoff 延迟分开报告，parent 执行长命令时仍应及时消费完成事件。Terra 接收普通只读任务指令；`STATUS: DISPATCH` 只用于 Luna 写授权，不能套用为 Terra 的出站式封装。

## 集成收敛与最终门

组件成功不具传递性。两个或更多写批次形成一个交付物时，Sol 必须定义共享契约、依赖顺序、`integration_worktree`、`integration_owner`、`integration_baseline`、`integration_paths_allow` 与 `integration_acceptance`。授权的 Luna integration owner 按依赖顺序组合已接受的提交；冲突或兼容性编辑必须回 Sol 取得新的 Luna 写批授权。整体 PASS 前必须在干净 integration worktree 上核验组合提交、三类路径范围和完整验收，并分别记录 `N/A (scope-check)` 与 `N/A (integration-check)` 证据，最后由独立 Terra 审计组合态。

## 安全、执行与用户决策边界

`DISPATCH` 是协议授权，不是密码学签名；`PATHS_ALLOW`、scope helper 和 runtime guard 是协调与漂移检测机制，不是操作系统 sandbox。Terra 的只读性依赖宿主 sandbox，文件权限和隔离 worktree 才是最终执行边界。本路由不授权生产部署、破坏性操作、外部承诺或业务/产品政策变化。

Sol 可决定不改变固定目标、范围、验收与用户政策的可逆技术权衡。目标、方向、产品优先级、明确用户意图或不可逆/重大承诺必须返回：

```text
STATUS: BLOCKED
FAILURE: major-decision
REQUEST: human_authority
NEXT: parent
```

Sol 最多给三个可行选项、关键权衡、受影响路径、一个建议和一个问题；路径始终是 `sol_planner → parent → user`，协议不定义 `NEXT: user`。

## 安装

Codex 用户必须把以下英文运行时作为同一版本整体安装：

1. `.agents/skills/lean-dev-router/` 到 Codex 的 Skill 目录；
2. `agents/` 下的三个 TOML 文件到 Codex 的 Agent 配置目录。

不得混用不同版本的 Skill 与 Agent TOML。安装后启动新的 Codex 任务；不得把仍在进行的 v1 handoff 直接恢复为 v2。
`runtime_guard.py` 随 Skill 安装；可变状态必须放在仓库外的临时目录。
根目录的 `SKILL.md` 与 `skill-variants/en/SKILL.md` 完全相同，始终是发布用的英文主版本。`skill-variants/zhcn/SKILL.md` 仅用于本机中文测试。可用以下命令覆盖已安装的根 Skill，并随时恢复英文：

启用中文测试版：

```powershell
Copy-Item skill-variants/zhcn/SKILL.md "$env:USERPROFILE/.codex/skills/lean-dev-router/SKILL.md" -Force
```

恢复英文发布版：

```powershell
Copy-Item skill-variants/en/SKILL.md "$env:USERPROFILE/.codex/skills/lean-dev-router/SKILL.md" -Force
```

从真实安装路径验证确定性入口，不创建 guard 状态：

```powershell
$guard = "$env:USERPROFILE/.codex/skills/lean-dev-router/scripts/runtime_guard.py"
python $guard schema
Get-Content dispatch.json -Raw | python $guard preflight
```

parent 快速路径 packet 的 `preflight` 与 `start` 还要追加 `--trusted-parent-instance-id <host-parent-id> --trusted-parent-model gpt-5.6-terra --trusted-parent-reasoning-effort high`；普通 Sol packet 不使用这些参数。完整契约和可信 Terra High 绑定返回 exit 0 与 `allowed: true`；非法契约返回 exit 2 和稳定 JSON 错误。生产调度仍只调用一次 `start --state ...`，由它执行相同验证并初始化状态。
该命令验证协议字段、ID、仓库相对 allow 路径、预算上限、baseline 哈希和可选具体 revision 语法；它不检查目标 worktree、不替代独立 scope 枚举，也不执行操作系统 sandbox。

`skill-variants/en-optimized/SKILL.md`（E1）和 `skill-variants/zhcn-optimized/SKILL.md`（C1）是结构对齐的去重实验版本，不是发布默认。只在新的基准任务中替换已安装根 Skill，测试后恢复英文默认。

每次替换后都启动新的 Codex 任务。

### 可选范围检查工具

`scripts/check_scope.py` 是仓库级便利工具，不是 Skill 或 Agent 的必需运行时文件。真正必须满足的是：接受 Luna 的 `PASS` 前取得范围证据。如果目标仓库没有该脚本，使用本文[路径范围检查](#路径范围检查)中的 Git fallback。安装 Skill 不会自动把 `scripts/check_scope.py` 添加到其他目标仓库。

### 升级与验证

1. 先结束或停止正在进行的 handoff 链；
2. 使用同一个 release 同时替换 Skill 目录和三个 Agent TOML；
3. 启动新的 Codex 任务，在依赖或写入 handoff 前确认实际 Agent、模型、reasoning effort、sandbox 与首个 `lean-dev-router/v2` 结果；
4. 在该 release 的干净 checkout 中运行 `python scripts/validate_repo.py` 和 `python -m unittest discover -s tests -v`。

### 卸载与回滚

卸载时只删除已安装的 `lean-dev-router` Skill 目录和三个具名 Agent TOML，然后启动新的 Codex 任务；这不会修改目标仓库。回滚时必须用某一个旧 release 的完整文件同时替换两组运行时，不得混合版本，也不得跨版本继续尚未结束的 handoff。

## 维护边界

- 英文根 Skill 是发布主版本；修改契约时同步维护 `skill-variants/en/SKILL.md` 与测试用的 `skill-variants/zhcn/SKILL.md`。
- `docs/zh-CN/` 只供人类阅读；可替换测试用的完整中文指令仅位于 `skill-variants/zhcn/SKILL.md`。
- 除根 `.agents/skills/lean-dev-router/SKILL.md` 外，CI 会阻止非 ASCII 字符进入 `.agents/` 与 `agents/` 的运行时文件。
- 修改运行行为后，应运行 `python scripts/validate_repo.py` 与 `python -m unittest discover -s tests -v`。
