# R1 Duplication Map

每个契约概念在各文件中的出现次数（粗略 grep 计数，用于定位重复承载点，不等同于 token 成本）。

| 概念 | Skill E0 (root) | Skill E1 | sol.toml | luna.toml | terra.toml | runtime_guard.py | validate_repo.py |
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
| envelope PROTOCOL|AGENT|STATUS | 0 | 0 | 1 | 1 | 1 | 0 | 0 |
| fuse 3 attempts/20 min | 0 | 0 | 2 | 2 | 0 | 0 | 1 |
| replay cwd/env/exit | 3 | 1 | 3 | 3 | 3 | 0 | 0 |
| spinning/stagnant | 3 | 3 | 0 | 1 | 0 | 5 | 5 |
| AUDIT_SCOPE/IMPACT_CONE | 2 | 2 | 2 | 0 | 2 | 1 | 3 |
| PLAN_MANIFEST | 1 | 1 | 1 | 0 | 0 | 0 | 3 |
| DISPATCH_WAVE | 1 | 1 | 1 | 0 | 0 | 0 | 3 |
| EXPANSION_GATE | 1 | 1 | 1 | 0 | 0 | 0 | 3 |

文件规模：

| 文件 | 字符数 | 行数 |
|---|---:|---:|
| Skill E0 (root) | 11,907 | 240 |
| Skill E1 | 10,713 | 128 |
| sol.toml | 5,315 | 25 |
| luna.toml | 4,247 | 23 |
| terra.toml | 4,383 | 25 |
| runtime_guard.py | 34,247 | 778 |
| validate_repo.py | 30,144 | 789 |

## R1-info 结果（瘦身后）

角色文件只保留禁区与差分规则；完整 DISPATCH/BUDGET/revision/repair schema 由根 Skill（单一事实源）+ `runtime_guard.py` 承载，`validate_repo.py` 现在要求根 Skill 含全部 `DISPATCH_FIELDS` 与预算字段名，不再要求 toml 重复整表。

| 文件 | 改前字符 | 改后字符 | 变化 |
|---|---:|---:|---:|
| sol-planner.toml | 5,315 | 2,576 | −51.5% |
| luna-worker.toml | 4,247 | 2,330 | −45.1% |
| terra-auditor.toml | 4,383 | 3,114 | −28.9% |
| 合计 | 13,945 | 8,020 | −42.5% |

校验要求：65 tests（1 skip Windows）通过；`validate_repo.py` 通过；所有角色禁区锚点、结果信封、LANGUAGE_RULE 保持不变。
