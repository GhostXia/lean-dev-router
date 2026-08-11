# Lean Dev Router 中文使用说明

> 本文档仅供人类阅读。可执行运行时以英文的 `.agents/skills/lean-dev-router/SKILL.md` 与 `agents/*.toml` 为唯一准则；本文档不会参与 Skill 或 Agent 的装配，也不定义机器可读取的行为。

[返回英文 README](../../README.md)

## 项目定位

Lean Dev Router 用三个职责不同的角色处理仓库内的软件工程任务：

- `sol_planner`：复杂任务的规划与调度者，负责拆分、排序、归并证据，并把属于用户的重大选择交还用户。
- `luna_worker`：仅在收到完整的标准 `DISPATCH` 后，按其中的任务摘要、基线、允许写入路径、验收和约束实施改动。
- `terra_auditor`：进行只读审计、诊断和验证，并为 Luna 无法解决的技术问题提供最小修复建议。

目标不是每次都调用全部角色，而是用满足任务需要的最小组合完成工作。所有写入任务先由 Sol 签发开工契约：边界清楚的 L1 改动只需最小单步 `DISPATCH`，模糊、跨模块或需要分批集成的任务则由 Sol 完整规划；审计和诊断仍可从 Terra 开始。

## 交接协议怎么读

协议把“入站执行授权”和“出站结果”分开。Luna 开始任何实现工具或写入前，必须收到 `PROTOCOL: lean-dev-router/v2`、`STATUS: DISPATCH`、`TARGET: implementation`，以及非空的任务摘要、基线、相对仓库的允许路径、客观验收和固定约束。只有 Sol 可以签发或修改，父会话只能原样转发；缺失或非法时，Luna 不实施并返回 `BLOCKED / missing_dispatch / NEXT parent`，也不会点名规划角色。

Agent 返回的出站交接包含状态、失败类型、能力请求、证据、固定的 `NEXT: parent` 和一句摘要。重点检查三件事：

1. 状态为成功时，失败类型必须为空。
2. 仓库结论必须绑定真实文件路径或明确的仓库级检查结果。
3. `REQUEST` 只描述下一步需要的能力，不点名其他 worker；父会话按“当前角色 + 能力请求”的固定表转发，不能根据证据自由推断路由。

`PASS`、`BLOCKED`、`ESCALATE` 都只是结果，不能作为写入授权；`PLAN_READY` 也不是执行状态。

升档顺序保持不变：Luna 请求技术解决能力，Terra 请求实施或规划能力，只有 Sol 可以请求用户决策。只有 Sol 和父会话知道具体拓扑。`REQUEST` 本身不授权写入；任何实施仍须由 Sol 签发完整 `DISPATCH`。`PASS/none` 表示当前阶段完成，`BLOCKED/none` 表示停在当前协调者处等待信息或依赖变化，不派发新能力。

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
  --allow tests
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

脚本使用 Git 的 NUL 分隔输出读取路径，因此不会把中文、空格、换行或其他特殊字符误当成显示层转义文本。

脚本不可用时，协调者仍必须执行等价的 Git fallback 检查。工作树批次分别枚举 tracked、普通 untracked 和 ignored untracked 路径：

```bash
git diff --name-only --no-renames <baseline> --
git ls-files --others --exclude-standard
git ls-files --others --ignored --exclude-standard
```

组合提交把第一条命令改为 `git diff --name-only --no-renames <integration-baseline> <combined-commit> --`，并在干净的 integration worktree 中继续检查两类 untracked 路径。所有发现的路径都必须与完整 allow-list 比对并记录等价范围证据；脚本与 fallback 的验收语义相同。

## 安装

Codex 用户必须把以下英文运行时作为同一版本整体安装：

1. `.agents/skills/lean-dev-router/` 到 Codex 的 Skill 目录；
2. `agents/` 下的三个 TOML 文件到 Codex 的 Agent 配置目录。

不得混用不同版本的 Skill 与 Agent TOML。安装后启动新的 Codex 任务；不得把仍在进行的 v1 handoff 直接恢复为 v2。

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

- 运行行为只修改英文 Skill、manifest 和 Agent TOML。
- 中文材料只解释如何使用和理解项目，不复制整套机器指令。
- CI 会阻止非 ASCII 字符重新进入 `.agents/` 与 `agents/`。
- 修改运行行为后，应运行 `python scripts/validate_repo.py` 与 `python -m unittest discover -s tests -v`。
