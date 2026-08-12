# Lean Dev Router 中文使用说明

> 本文档仅供人类阅读。可执行运行时以英文的 `.agents/skills/lean-dev-router/SKILL.md` 与 `agents/*.toml` 为唯一准则；本文档不会参与 Skill 或 Agent 的装配，也不定义机器可读取的行为。

[返回英文 README](../../README.md)

## 项目定位

Lean Dev Router 用四个职责不同的角色处理仓库内的软件工程任务：

- `terra_planner`：只读的实验性确定性规划者；仅对满足固定谓词的 L1/L2 任务直接替代例行 Sol 规划。
- `sol_planner`：工程方案与授权者，负责拆分、契约、预注册审计和例外决策，但不持续调度运行时事件。
- `luna_worker`：仅在收到完整的标准 `DISPATCH` 后，按其中的任务摘要、基线、允许写入路径、验收和约束实施改动。
- `terra_auditor`：沿因果影响面进行只读审计、诊断和验证，并给出不带写授权的最小修复建议。

父会话是机械状态机：按授权 planner（`terra_planner` 或 `sol_planner`）已声明的 manifest 启动、排队和转交，不在没有用户指令时自行作工程决策。规划采用有界波次：每次只输出全局不变量、当前可执行的 `DISPATCH_WAVE` 与下一次 `EXPANSION_GATE`；父会话只在该门或例外发生时请求 Sol，避免一次性计划过长带来的偏差。

目标不是每次都调用全部角色，而是用满足任务需要的最小组合完成工作。符合确定性谓词的 L1/L2 写入由 `terra_planner` 直接规划并签发一个有界 `DISPATCH`；L3、风险、歧义、范围外路径、契约扩展、多个写入批次或用户决策直接回到 Sol，不经过例行 Terra→Sol 复核。其他任务仍由 Sol 规划；审计和诊断可从 Terra 开始。

每个会产生改动的任务先进行一次只读 `terra_planner` 分类。它依据用户目标和仓库状态生成规范 eligibility 证据；父会话不负责给任务定级。符合条件的任务留在 Terra 快路径，任何无法只读确认、缺失或矛盾的证据都直接升级到 Sol。

### terra_planner 实验路径

只有以下条件全部满足时才允许快路径：`LEVEL` 为 L1/L2，
`OBJECTIVE_FIXED` 为 true，`BASELINE`、`SCOPE_ROOTS`、`ACCEPTANCE` 非空，
`OPEN_MAJOR_DECISIONS` 为 false，`RISK_FLAGS` 与 `EXTERNAL_ACTIONS` 为 none，
`MAX_DISPATCHES` 等于 1，`COMPONENT_COUNT` 不超过 2，
`DEPENDENCY_DEPTH` 不超过 1。必需路径在 `SCOPE_ROOTS` 外、歧义、契约扩展或超过一个写入批次都会直接路由 Sol。
`REQUIRED_PATHS`、`WRITE_BATCH_COUNT`、`CONTRACT_EXPANDED`、`AMBIGUITY` 必须显式给出；不得依靠缺省值放行。
`SCOPE_ROOTS`、`PATHS_ALLOW`、`REQUIRED_PATHS` 必须是仓库相对路径列表，且允许或必需路径不得越出 `SCOPE_ROOTS`；畸形字段直接升级 Sol，不得抛错或放行。

风险旗标包括 security、privacy、public-contract、data-schema-or-migration、
destructive、production、external-commitment、license、
material-compatibility、concurrency、irreversible 与 material-cost changes。
`terra_planner` 可以只读检查、分析、发出一个有界 Luna `DISPATCH`、预注册独立只读 Terra 审计并输出有限 manifest；不能调度/等待、实施、审计、执行后修改或请求 `human_authority`。
每个计划必须携带 `PLAN_ID`、`PLANNER_ROLE`、`PLANNER_INSTANCE_ID` 与不同的
`AUDITOR_INSTANCE_ID`。同一 `AGENT_INSTANCE_ID` 在同一计划中只能拥有不可变角色租约，且审计者不能规划或实施该计划；Luna 会在写入前验证这些身份。

## 交接协议怎么读

协议把“入站执行授权”和“出站结果”分开。Luna 开始任何实现工具或写入前，必须收到 `PROTOCOL: lean-dev-router/v2`、`STATUS: DISPATCH`、`TARGET: implementation`，以及非空且稳定唯一的 `DISPATCH_ID`、`PLAN_ID`、`PLANNER_ROLE`、`PLANNER_INSTANCE_ID`、`AUDITOR_INSTANCE_ID`、任务摘要、基线、相对仓库的允许路径、客观验收和固定约束。该 ID 贯穿 Luna 证据、预注册 Terra 审计和契约内返工核验。Sol 签发或修改例外契约；符合谓词的 `terra_planner` 可发出一个有界契约，父会话只能原样转发，Luna 会验证规划者权限和身份；缺失或非法时，Luna 不实施并返回 `BLOCKED / missing_dispatch / NEXT parent`。

Agent 返回的出站交接包含状态、失败类型、能力请求、证据、固定的 `NEXT: parent` 和一句摘要。重点检查三件事：

1. 状态为成功时，失败类型必须为空。
2. 仓库结论必须绑定真实文件路径或明确的仓库级检查结果。
3. `REQUEST` 只描述下一步需要的能力，不点名其他 worker；父会话按“当前角色 + 能力请求”的固定表转发，不能根据证据自由推断路由。

`PASS`、`BLOCKED`、`ESCALATE` 都只是结果，不能作为写入授权；`PLAN_READY` 也不是执行状态。

升档仍由固定状态机执行，但不再让所有结果先绕回 Sol。Luna `PASS` 后，父会话机械核验范围、稳定 revision、依赖与 replay；若 planner 已预注册审计，则在 gates 通过后直接启动 Terra。Terra 发现不改变原契约且仍在 `PATHS_ALLOW` 内的缺陷时，父会话可在返工预算内直接交回原 Luna；涉及范围、方案、验收、公共接口、架构、安全边界、数据格式、资源限制或歧义时才回 Sol。只有 Sol 可以请求用户决策。

`lean-dev-router/v2` 与 v1 不兼容：v2 强制要求 `REQUEST`，并禁止在 `NEXT` 中点名具体 Agent。协调者必须拒绝混用版本的交接，不能自动猜测或静默转换。

从 v1 迁移时，应一次性替换 Skill 和四个 Agent TOML，把保存的协议模板改为 v2，为每个出站结果增加合法的 `REQUEST`，并把具名的出站 `NEXT` 改为 `NEXT: parent`。不要把进行中的 v1 交接链直接续接为 v2；结束或停止旧链后，从新的 v2 协调会话开始。

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

组件审计与复审使用稳定的 `<component>:<revision>:<stage>` 任务键，并记录 `queued`、`running`、`complete` 或 `failed`。批量创建 Agent 部分失败时逐项核对，只重试缺失或失败项，不能重放已经运行或完成的任务。Sol 保留为方案与例外决策端，不作为常驻运行时协调者。

Terra 的读取范围必须宽于改动范围：沿调用关系、数据/错误/资源流、配置、平台兼容、并发、安全、性能与测试调查。范围外发现分为 A（改动导致的验收缺陷）、B（完成目标所需但遗漏的路径）、C（无关既存问题，通常仅跟进）、D（严重安全/数据丢失/兼容风险）。A 可在原契约内返 Luna；B 与契约变化回 Sol；D 阻断或升级。

对于昂贵、并发、易抖动、环境敏感或不确定的门禁，默认熔断器是三次“实质不同”的尝试与二十分钟模型主动处理时间；外部编译、CI、网络等待不计入主动时间，但命令必须有 timeout。没有代码、配置、输入、环境、依赖或可检验假设变化时，不得原样重跑命令。

宿主能提供时间戳时，记录组件就绪与下一阶段启动时间。有空闲容量时应在 60 秒内启动；否则记录排队状态与原因，并在第一个符合条件的槽位释放时启动。把编译、CI、网络等外部等待与可控 handoff 延迟分开报告，parent 执行长命令时仍应及时消费完成事件。Terra 接收普通只读任务指令；`STATUS: DISPATCH` 只用于 Luna 写授权，不能套用为 Terra 的出站式封装。

## 安装

Codex 用户必须把以下英文运行时作为同一版本整体安装：

1. `.agents/skills/lean-dev-router/` 到 Codex 的 Skill 目录；
2. `agents/` 下的四个 TOML 文件到 Codex 的 Agent 配置目录。

不得混用不同版本的 Skill 与 Agent TOML。安装后启动新的 Codex 任务；不得把仍在进行的 v1 handoff 直接恢复为 v2。

### 可选范围检查工具

`scripts/check_scope.py` 是仓库级便利工具，不是 Skill 或 Agent 的必需运行时文件。真正必须满足的是：接受 Luna 的 `PASS` 前取得范围证据。如果目标仓库没有该脚本，使用本文[路径范围检查](#路径范围检查)中的 Git fallback。安装 Skill 不会自动把 `scripts/check_scope.py` 添加到其他目标仓库。

### 升级与验证

1. 先结束或停止正在进行的 handoff 链；
2. 使用同一个 release 同时替换 Skill 目录和四个 Agent TOML；
3. 启动新的 Codex 任务，在依赖或写入 handoff 前确认实际 Agent、模型、reasoning effort、sandbox 与首个 `lean-dev-router/v2` 结果；
4. 在该 release 的干净 checkout 中运行 `python scripts/validate_repo.py` 和 `python -m unittest discover -s tests -v`。

### 卸载与回滚

卸载时只删除已安装的 `lean-dev-router` Skill 目录和四个具名 Agent TOML，然后启动新的 Codex 任务；这不会修改目标仓库。回滚时必须用某一个旧 release 的完整文件同时替换两组运行时，不得混合版本，也不得跨版本继续尚未结束的 handoff。

## 维护边界

- 运行行为只修改英文 Skill、manifest 和 Agent TOML。
- 中文材料只解释如何使用和理解项目，不复制整套机器指令。
- CI 会阻止非 ASCII 字符重新进入 `.agents/` 与 `agents/`。
- 修改运行行为后，应运行 `python scripts/validate_repo.py` 与 `python -m unittest discover -s tests -v`。
