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

协议把“入站执行授权”和“出站结果”分开。Luna 开始任何实现工具或写入前，必须收到 `PROTOCOL: lean-dev-router/v1`、`STATUS: DISPATCH`、`TARGET: implementation`，以及非空的任务摘要、基线、相对仓库的允许路径、客观验收和固定约束。只有 Sol 可以签发或修改，父会话只能原样转发；缺失或非法时，Luna 不实施并返回 `BLOCKED / missing_dispatch / NEXT parent`，也不会点名规划角色。

Agent 返回的出站交接包含状态、失败类型、证据、下一角色和一句摘要。重点检查三件事：

1. 状态为成功时，失败类型必须为空。
2. 仓库结论必须绑定真实文件路径或明确的仓库级检查结果。
3. 下一角色表示当前协调者接下来应派发谁，不代表结果会绕过父会话直接发送。

`PASS`、`BLOCKED`、`ESCALATE` 都只是结果，不能作为写入授权；`PLAN_READY` 也不是执行状态。

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

## 安装

Codex 用户复制两组英文运行时文件：

1. `.agents/skills/lean-dev-router/` 到 Codex 的 Skill 目录；
2. `agents/` 下的三个 TOML 文件到 Codex 的 Agent 配置目录。

范围检查脚本当前位于仓库的 `scripts/check_scope.py`。如果未来提供独立分发包，必须把 helper 放在可稳定解析的位置并随运行时一起分发，不能假定目标仓库已经包含本项目的 `scripts/` 目录。

## 维护边界

- 运行行为只修改英文 Skill、manifest 和 Agent TOML。
- 中文材料只解释如何使用和理解项目，不复制整套机器指令。
- CI 会阻止非 ASCII 字符重新进入 `.agents/` 与 `agents/`。
- 修改运行行为后，应运行 `python scripts/validate_repo.py` 与 `python -m unittest discover -s tests -v`。
