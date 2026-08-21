# R1 Duplication Map

每个契约概念在各文件中的出现次数（粗略 grep 计数，用于定位重复承载点，不等同于 token 成本）。

| 概念 | Skill E0 (`.agents/.../SKILL.md` + `skill-variants/en/SKILL.md`) | Skill E1 | `agents/sol-planner.toml` | `agents/luna-worker.toml` | `agents/terra-auditor.toml` | runtime_guard.py | validate_repo.py |
|---|---|---|---|---|---|---|---|
| DISPATCH_ID | 4 | 4 | 2 | 4 | 4 | 25 | 4 |
| PLAN_ID | 1 | 2 | 1 | 1 | 1 | 26 | 3 |
| PLANNER_INSTANCE_ID | 1 | 1 | 1 | 1 | 0 | 4 | 3 |
| AUDITOR_INSTANCE_ID | 2 | 2 | 1 | 2 | 1 | 20 | 4 |
| TASK_SUMMARY | 1 | 1 | 1 | 1 | 0 | 1 | 2 |
| PATHS_ALLOW | 4 | 3 | 3 | 3 | 3 | 5 | 2 |
| ACCEPTANCE | 1 | 2 | 1 | 1 | 0 | 3 | 2 |
| CONSTRAINTS | 1 | 1 | 1 | 1 | 0 | 1 | 2 |
| BUDGET | 2 | 2 | 4 | 3 | 0 | 13 | 2 |
| NEXT: parent | 2 | 2 | 2 | 3 | 1 | 0 | 1 |
| PROTOCOL: lean-dev-router/v2 | 2 | 2 | 1 | 1 | 0 | 0 | 1 |
| STATUS: DISPATCH | 2 | 2 | 1 | 1 | 0 | 0 | 1 |
| TARGET: implementation | 1 | 1 | 1 | 1 | 0 | 0 | 1 |
| MODEL_CALL_LIMIT | 1 | 1 | 1 | 1 | 0 | 3 | 3 |
| HYPOTHESIS_LIMIT | 1 | 1 | 1 | 1 | 0 | 3 | 1 |
| MODEL_ACTIVE_SECONDS_LIMIT | 1 | 1 | 1 | 1 | 0 | 3 | 1 |
| REPAIR_CYCLE_LIMIT | 1 | 1 | 1 | 1 | 0 | 3 | 1 |
| STAGNANT_CALL_LIMIT | 1 | 1 | 1 | 1 | 0 | 3 | 3 |
| worktree-sha256 | 1 | 1 | 1 | 1 | 1 | 2 | 4 |
| baseline-only dirty | 1 | 1 | 1 | 0 | 1 | 0 | 0 |
| CONTRACT_EFFECT: unchanged | 1 | 1 | 1 | 1 | 1 | 0 | 3 |
| AFFECTED_PATHS | 1 | 1 | 1 | 0 | 1 | 3 | 1 |
| REPAIR_CYCLE | 1 | 2 | 1 | 1 | 0 | 7 | 1 |
| parent:terra | 1 | 1 | 0 | 0 | 0 | 2 | 1 |
| parent:sol | 1 | 1 | 0 | 0 | 0 | 6 | 1 |
| parent:repair_or_sol | 1 | 1 | 0 | 0 | 0 | 0 | 3 |
| human_authority | 3 | 3 | 2 | 0 | 0 | 0 | 3 |
| finding classes A-D | 0 | 0 | 0 | 0 | 4 | 0 | 0 |
| envelope PROTOCOL\|AGENT\|STATUS | 0 | 0 | 1 | 1 | 1 | 0 | 0 |
| fuse 3 attempts/20 min | 0 | 0 | 2 | 2 | 0 | 0 | 1 |
| replay cwd/env/exit | 3 | 1 | 3 | 3 | 3 | 0 | 0 |
| spinning/stagnant | 3 | 3 | 0 | 1 | 0 | 5 | 5 |
| AUDIT_SCOPE/IMPACT_CONE | 2 | 2 | 2 | 0 | 2 | 1 | 3 |
| PLAN_MANIFEST | 1 | 1 | 1 | 0 | 0 | 0 | 3 |
| DISPATCH_WAVE | 1 | 1 | 1 | 0 | 0 | 0 | 3 |
| EXPANSION_GATE | 1 | 1 | 1 | 0 | 0 | 0 | 3 |

文件规模（改前基线数据）：

| 文件 | 字符数 | 行数 |
|---|---:|---:|
| Skill E0 (`.agents/.../SKILL.md` and byte-identical `skill-variants/en/SKILL.md`) | 11,907 | 240 |
| Skill E1 | 10,713 | 128 |
| `agents/sol-planner.toml` | 5,315 | 25 |
| `agents/luna-worker.toml` | 4,247 | 23 |
| `agents/terra-auditor.toml` | 4,383 | 25 |
| runtime_guard.py | 34,247 | 778 |
| validate_repo.py | 30,144 | 789 |

## R1-info 结果（瘦身后）

这些承载点有不同职责，不能互相替代：

- 协议文档：根 Skill 及其 English/Chinese 变体记录 v2 的公共语义、字段和路由。
- Sol packet production：`agents/sol-planner.toml` 保留一份紧凑的完整 DISPATCH/BUDGET 生产模板，并固定 `AGENT: sol_planner`；它不继承或声称接收完整 Skill。
- Runtime enforcement：`.agents/skills/lean-dev-router/scripts/runtime_guard.py` 对实际任务包、预算、revision、重试和审计状态作确定性检查。
- Concrete task packets：实际 `DISPATCH` 的 ID、baseline、路径、验收和预算值由 Sol/父代理在任务运行时填入，不应伪装成静态文档字段。
- Static regression checks：`scripts/validate_repo.py` 检查公共 Skill 文档和各角色应承担的静态契约；Luna/Terra 不需要复制 Sol 的生产模板。

| 文件 | 改前字符 | 改后字符 | 变化 |
|---|---:|---:|---:|
| sol-planner.toml | 5,315 | 3,541 | −33.4% |
| luna-worker.toml | 4,247 | 2,330 | −45.1% |
| terra-auditor.toml | 4,383 | 3,114 | −28.9% |
| 合计 | 13,945 | 8,985 | −35.6% |

校验要求：`python -m unittest discover -s tests -v` 与 `python scripts/validate_repo.py` 通过；所有角色禁区锚点、结果信封、LANGUAGE_RULE 保持不变。
