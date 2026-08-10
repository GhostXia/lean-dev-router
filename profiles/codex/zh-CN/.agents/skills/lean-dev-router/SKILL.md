---
name: lean-dev-router
description: Route repository-bound software engineering lifecycle work through one sol_planner coordinator by default and complexity-scaled pools of luna_worker and terra_auditor agents. Use for planning, implementation, fixes, refactors, audits, reviews, investigations, incident diagnosis, migrations, upgrades, testing, documentation, configuration, or release-readiness checks when token- or latency-efficient coordination is desired.
---

Lean Dev Router

在满足 token 与耗时优先级的前提下使用最少的 Agent。复杂路由任务默认使用一个 `sol_planner`，按任务复杂度和数量协调足够的 `luna_worker` 与 `terra_auditor`；只有用户明确要求时才使用多个 Sol 协调者。

语言

分析、交接和最终回复跟随父任务的主要语言。
如果父任务是双语，按当前输出要求选择语言；未指定时使用占主导地位的语言。
代码、命令、文件路径、模型 ID、Agent 名称及其他技术标识保持不变。

交接协议

每次委派结果都必须使用以下紧凑协议，不得继续使用角色专属的输出格式。

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

`PASS` 表示当前角色阶段完成；`BLOCKED` 表示缺少必要信息、权限或依赖；`ESCALATE` 表示需要其他角色继续处理。
`PASS` 时 `FAILURE` 必须为 `none`；其他状态只选择一个主要失败类别。
每个仓库结论都必须绑定具体相对路径，并附简短 diff 摘要或命令结果。只有纯规划且没有仓库文件时可使用 `path: N/A (planning-only)`，分配与处理项目标识的覆盖结果使用 `path: N/A (batch coverage)`，仓库级 allow-list 结果使用 `path: N/A (scope-check)`，针对组合后集成提交运行的命令使用 `path: N/A (integration-check)`；不得伪造路径。
`NEXT` 必须填写，表示当前协调者下一步应派发的角色。委派结果始终返回启动它的会话；存在 Sol 时由 Sol 执行该路由，否则由父会话执行。交接缺字段或证据时不得自行推断成功，应返回一次紧凑的修正请求，并使用 `STATUS: BLOCKED`、`FAILURE: verification`。

写入范围门

对产生改动的任务，尤其在没有 CI 时，将 Sol 的 Todo/`DISPATCH` 计划作为主要范围控制。Luna 写入批次应具备单一且边界清晰的目标、明确依赖、可控路径集合和独立验收；不要拆得比这些属性所需更细。精确委托与 Luna 守约负责预防大多数漂移。
将 `relevant paths` 视为读取上下文而非写入授权。任何 Luna 写任务开始前，其协调者都必须记录 baseline commit 和明确的仓库相对 `paths_allow`，条目可指向文件或目录子树；路由批次由 Sol 提供，直接 Luna 快路径由父会话提供。测试、格式化工具、包管理器或其他工具生成的文件也必须事先授权。
接受 Luna 的 `PASS` 前，优先使用仓库 helper：`python scripts/check_scope.py --baseline <baseline> --allow <paths_allow_entry>`，对每个授权路径重复传入 `--allow`。它会机械收集 tracked 改动、普通 untracked 文件和 ignored untracked 文件，完成 allow-list 比对并输出一条紧凑结果。将该输出记录为 `path: N/A (scope-check)` 证据；helper 不存在时才 fallback 到 `git diff --name-only --no-renames <baseline> --`、`git ls-files --others --exclude-standard` 和 `git ls-files --others --ignored --exclude-standard`。失败时列出每个额外路径，不得静默忽略任何路径类别。
如存在额外路径，保留 Luna 的原始交接，但不得将其作为最终成功接受；将额外路径记录为范围检查证据并使用 `FAILURE: scope`。已有 Sol 可将明显无关的改动直接退回 Luna 裁剪；只有技术必要性不明确时才使用 Terra。Sol 仅可在既定目标和验收标准内修订或拆分批次，否则进入用户决策门。独立父会话执行同一范围门。
将该检查保留为低频辅路保险丝，而非主调度器。范围内的 `PASS` 不要求 Terra 审查；范围门很少触发说明拆分良好，不代表应移除它。

集成收敛门

当两个或更多写入批次共同组成一个交付物时，组件级 `PASS` 只关闭对应批次，绝不代表整体任务成功。派发前，Sol 必须定义共享契约、依赖顺序、`integration_worktree`、`integration_owner`、`integration_baseline`、`integration_paths_allow` 和 `integration_acceptance`。`integration_paths_allow` 初始值是已接受批次 allow-list 的精确并集，只有获得授权的 Luna 集成修复批次才能修改它。
Sol 只负责协调，不修改集成树。指定一个 Luna 作为 `integration_owner`，按依赖顺序组合提交；父会话 fallback 只能执行无冲突的机械合入。任何冲突解决或兼容性改动都是新的、有边界的 Luna 写入批次，必须拥有自己的 baseline 和 allow-list。优先增量收敛：每个依赖批次或独立波次后运行最小必要的跨批检查，最后针对确切的组合提交完成验收。
返回整体任务最终 `PASS` 前，协调者必须确认集成 worktree 干净，并优先使用 `python scripts/check_scope.py --baseline <integration_baseline> --end <combined_commit> --allow <integration_paths_allow_entry>`，对每个授权路径重复传入 `--allow`。将其紧凑输出记录为 `path: N/A (scope-check)`，再以 `path: N/A (integration-check)` 记录组合提交、合入顺序和验收命令。helper 不存在时才使用 `git diff --name-only --no-renames <integration_baseline> <combined_commit> --`、`git ls-files --others --exclude-standard` 和 `git ls-files --others --ignored --exclude-standard`。
用户要求独立验证、两个或更多组件批次接受了 Terra 验证，或集成跨越重大安全、数据、并发、兼容性、迁移或公共契约边界时，必须进行最终 Terra 集成审计；其他情况可仅使用组合状态的命令证据。需要集成审计时，各组件分别通过审计不能替代它。
集成失败时不得宣布最终成功，并定位最早失败的合入或波次。未授权路径使用 `FAILURE: scope`，验收失败使用 `verification`，提交或工具不可用使用 `dependency`，原因无法确定使用 `ambiguity`。明确且边界清晰的兼容修复交给 Luna，跨组件原因不明确时交给 Terra，需要在范围内调整契约或拆分时交给 Sol；涉及用户专属目标、兼容性或产品取舍时进入用户决策门。

Codex 执行方式

默认使用 Codex 原生 subagent 和已配置的 Agent TOML 文件。明确且边界清晰的任务直接调用一个 `luna_worker`；复杂、模糊或可拆分任务默认调用一个 `sol_planner`，由其分解、委派、等待和归并。
当任务相互独立时，由默认的 Sol 协调者并行运行多个 Luna 和 Terra。每个并行写入的 Luna 必须使用独立 worktree 或独立 checkout，并绑定各自分支；只有分支不构成写入隔离。只读 Terra 可以共享 checkout。
在有依赖或写入的交接前，确认目标 Agent 已加载、模型和思考强度生效，且首次结果遵循 `lean-dev-router/v1`。
条件允许时，在依赖原生路由前检查 `codex --version`；CLI 中使用 `/agent` 检查 Agent 线程。
如果 Sol 会话不能嵌套启动 worker，应返回 `BLOCKED/dependency/NEXT parent`，并在 `EVIDENCE` 中提供紧凑的 `DISPATCH` 清单；每个 worker 条目必须包含 `id`、`role`、`scope`、`worktree`（共享只读任务使用 `N/A`）、`depends_on` 和 `acceptance`，Luna 写入条目还必须包含 `baseline` 和 `paths_allow`。多批次交付还必须声明共享契约、`integration_worktree`、`integration_owner`、`integration_order`、`integration_baseline`、`integration_paths_allow`、`integration_acceptance`，以及是否需要最终 Terra 审查。父会话机械执行清单，再将紧凑结果送回同一个 Sol 归并。原生调用完全不可用时，使用相同清单启动独立 Codex session。
Codex 原生后台 Agent 界面仍属于原生 subagent 流程；其他后台进程或独立 session 只能作为 fallback，不能视为等价的父子路由。

Worker 扩缩与分发

每个路由任务默认使用一个 `sol_planner`。Sol 根据任务规模、数量、独立性、依赖深度和风险决定 worker 数量、角色组合、顺序及并发。只有用户明确指令才可启用多个 Sol；由父会话创建它们并分配互不重叠的调度范围，任何 Sol 都不得启动同级 Sol。
用户未强调耗时时默认 `token-first`。并发 worker 请求上限为：`token-first` 3 个、`balanced` 6 个、`latency-first` 10 个；上限包含 Luna 与 Terra 总数，属于调度启发式，不是运行时保证。
30))`, then adjust for complexity and risk. Keep dependent stages sequential; use disjoint waves when fewer workers start. / 对相互独立的读取、实现、测试或审查批次进行并行。对相对均匀的项目集合，先使用 `min(模式上限, ceil(项目数 / 30))`，再按复杂度和风险调整。有依赖的阶段保持串行；可用 worker 较少时使用互不重叠的波次。
为每个 worker 提供精确且互不重叠的任务、固定约束、验收标准、相关路径、批次标识和统一输出结构。项目批次的首条 `EVIDENCE` 必须使用 `path: N/A (batch coverage)` 并记录已分配与已处理标识。
Sol 等待所有必要 worker，检查覆盖完整且互不重叠，归并去重结果并决定后续路由。高风险或冲突发现交给不同的 Terra 复核，不得自审。

工程任务入口

仓库范围内的实现、修复、重构、审计与审查、调查与事件诊断、迁移与升级、测试与 QA、文档与配置，以及发布就绪检查都属于适用范围。
对产生改动的任务，边界明确时直接交给 Luna；任务模糊、可拆分、跨模块或决策较多时先由 Sol 规划；只有需要诊断或独立验证时才加入 Terra。
对审计、审查、合规检查和发布就绪任务，先使用一个或多个 Terra；只有需要拆分、归并、冲突裁定或重大决策时才使用 Sol；修复获得授权后才调用 Luna。
对调查、事件、性能分析和调试任务，由 Terra 建立证据和可能原因，并在适合时并行验证独立假设；Sol 裁定范围内的技术取舍，属于用户的选择则进入用户决策门；获得授权的修复交给 Luna。
对迁移、依赖或平台升级，由 Sol 在已授权范围内规划并确定实施顺序，Terra 盘点兼容性与风险，Luna 隔离实施，最后由 Terra 验证。
此范围不授予生产部署、破坏性操作、外部承诺或业务及产品策略变更的权限；这些操作必须获得用户明确批准。

路由

只有父会话记录 baseline commit 和仓库相对 `paths_allow` 后，才能将明确且边界清晰的实现任务直接交给 `luna_worker`。
初始模糊、可拆分、跨任务，或涉及重大架构、范围、接口、数据模型、兼容性、安全边界、依赖或验收决策的请求，交给一个 `sol_planner`；由 Sol 协调 Luna 与 Terra 直至完成。
当 `luna_worker` 无法解决实现、调试、测试或局部技术取舍问题时，向 Sol 协调者返回紧凑的 Terra 升级；不得自行裁定重大决策。
Sol 将 `terra_auditor` 可执行的技术结论交给对应的 `luna_worker` 实施并验证。
在独立 Luna 快路径中，仅当 Terra 无法建立有证据支持的解法或发现重大决策时才调用一个 Sol。在 Sol 协调的任务中，Terra 将升级返回现有 Sol，不得创建另一个 Sol。Sol 将范围内的技术决策交回对应 Luna；属于用户的决策使用下方用户决策门。
明确的审计、审查、调查、诊断、合规或发布就绪请求，以 `terra_auditor` 为入口。实现完成后，仅在明确要求审查或存在重大正确性、安全、迁移、兼容性或回归风险时调用 Terra。

用户决策门

`sol_planner` 可以裁定不改变既定目标、范围、验收标准和用户授权策略的可逆技术取舍。
修改目标、范围、验收标准、方向、理念或产品优先级，违背用户明确意图，以及不可逆或重大的兼容性、安全、隐私、许可、迁移或成本承诺，必须交由用户决定。
对属于用户的决策，返回 `STATUS: BLOCKED`、`FAILURE: major-decision`、`NEXT: parent`；在 `EVIDENCE` 中列出最多三个可行方案、关键取舍、受影响路径和一个推荐，并让 `SUMMARY` 成为需要询问用户的唯一问题。不要增加 `NEXT: user`；正确路径是 `sol_planner → parent → user`。
用户答复前暂停实施；已有 Sol 协调者时由同一个 Sol 恢复调度；否则在答复已完整确定约束时直接交给 `luna_worker`，只有需要重整方案时才调用一个 Sol。

交接

只传递：

目标和固定约束；
验收标准；
相关路径或 diff；
紧凑证据和测试结果；
已尝试的修复（如有）；
下一步唯一需要的决策或行动。

不要转发完整对话、重复上下文、完整日志或大范围仓库转储。只有由父会话创建的 `sol_planner` 可以编排 Luna 和 Terra worker。

停止

请求结果和必要验证完成后停止。
不要默认调用全部三个 Agent。
没有新证据或决策变化时不要重复调用 Agent。
只总结一次最终结果；省略内部交接重复内容。
