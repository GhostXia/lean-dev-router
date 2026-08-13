# Lean Dev Router（中文说明）

本文档仅供人类阅读。直接执行的英文 Skill 位于 [`.agents/skills/lean-dev-router/SKILL.md`](../../.agents/skills/lean-dev-router/SKILL.md)，根 Skill 与 `skill-variants/en/SKILL.md` 必须完全相同。

## 角色

Sol 负责例外规划、DISPATCH 授权和用户决策；parent 只做机械调度；Luna 是唯一写入者；`terra_auditor` 是独立只读审计者。仓库只发布三个子配置：`luna_worker`、`sol_planner`、`terra_auditor`。parent 快速路径是 Terra High 主模型的条件能力，不是第四个子 Agent，也不是第二个 Sol。

## parent 快速路径

快速路径使用 `PLANNER_ROLE: parent` 和 `PLANNER_CAPABILITY: bounded_l1_l2_dispatch`。runtime guard 只有在以下证据全部明确且固定时才会放行：L1/L2；目标、验收、约束固定且非空；没有重大决策、风险、外部操作、集成、冲突、歧义或契约扩展；没有契约/范围/验收/约束/架构/安全/兼容性变化；一个组件、一个 dispatch、一个写批次；依赖深度为 0；允许与必需路径均位于固定 `SCOPE_ROOTS`。

parent 上限是 4 次调用、2 个假设、600 秒主动时间、1 次修复、1 次停滞。证据缺失、L3、风险、多批次、B/D 发现或耗尽在 Luna 前路由 `parent:sol`；B 不得进入 Luna 修复。普通 Sol DISPATCH 仍兼容 v2，预算为 8/4/1200/2/2。

## 协议和范围

Luna 只有收到父会话原样转发的完整 `PROTOCOL: lean-dev-router/v2` `STATUS: DISPATCH` 才能执行工具或写入。`PATHS_ALLOW` 只授权持久写入，相关路径仅是可读上下文。接受 PASS 前运行：

```powershell
python scripts/check_scope.py --baseline <baseline> --allow <entry> ... --revision
```

脚本不可用时，记录 tracked、普通 untracked 和 ignored untracked 三类 Git 枚举。干净状态使用提交 SHA；授权脏状态使用 `worktree-sha256:<64 lowercase hex>`。构建产物必须放在仓库外 scratch，或在范围检查前删除的临时目录。

## Terra 审计与集成

最终审计必须预注册，且只能由独立 `terra_auditor` 执行；parent 不得自审。Terra 将发现分为 A（改动造成的验收缺陷）、B（必要但遗漏的范围）、C（无关既有问题）和 D（严重安全/数据丢失/兼容风险）。只有契约不变、路径在范围内的 A 修复可返回 Luna；B、D 和契约变化返回 Sol。

两个或更多写批次需要 `integration_owner`、依赖顺序、`integration_baseline`、`integration_paths_allow`、`integration_acceptance` 和干净 integration worktree。组件 PASS 不等于整体 PASS。

## 安装和验证

请把 Skill 目录和 `agents/` 下三个 TOML 作为同一版本安装，并在替换后启动新任务。验证：

```powershell
python scripts/validate_repo.py
python -m unittest discover -s tests -v
```

验证器会检查三个子配置、严格 parent 能力和 Sol 例外路由、封闭 handoff、审计身份独立、主 Skill 与英文变体相等、优化变体结构和大小，以及不再注册旧规划角色。
