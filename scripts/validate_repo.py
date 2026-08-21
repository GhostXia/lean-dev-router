#!/usr/bin/env python3
"""Validate the directly executable lean-dev-router runtime contract."""

from __future__ import annotations

import ast
import json
import re
import sys
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ERRORS: list[str] = []
LANGUAGE_RULE = (
    "Language: Follow the parent task's primary language; when unspecified, use its "
    "dominant language. Keep code, commands, paths, model IDs, and agent names unchanged."
)
LEGACY_PATHS = (
    Path("runtime").joinpath("source"),
    Path("profiles").joinpath("codex"),
    Path("scripts").joinpath("build_" + "runtime.py"),
)
DISPATCH_FIELDS = (
    "PROTOCOL: lean-dev-router/v2", "STATUS: DISPATCH", "TARGET: implementation",
    "DISPATCH_ID", "PLAN_ID", "PLANNER_ROLE", "PLANNER_INSTANCE_ID",
    "AUDITOR_INSTANCE_ID", "TASK_SUMMARY", "BASELINE", "PATHS_ALLOW", "ACCEPTANCE",
    "CONSTRAINTS", "BUDGET", "NEXT: parent",
)
BUDGET_FIELDS = (
    "MODEL_CALL_LIMIT", "HYPOTHESIS_LIMIT", "MODEL_ACTIVE_SECONDS_LIMIT",
    "REPAIR_CYCLE_LIMIT", "STAGNANT_CALL_LIMIT",
)
SOL_PRODUCTION_SCHEMA = DISPATCH_FIELDS + BUDGET_FIELDS
PARENT_FAST_PATH_CAPABILITY = "bounded_l1_l2_dispatch"
PARENT_FAST_PATH_FIELDS = (
    "PLANNER_ROLE", "PLANNER_CAPABILITY", "LEVEL", "OBJECTIVE_FIXED", "BASELINE", "SCOPE_ROOTS",
    "ACCEPTANCE", "CONSTRAINTS", "OPEN_MAJOR_DECISIONS", "RISK_FLAGS",
    "EXTERNAL_ACTIONS", "MAX_DISPATCHES", "COMPONENT_COUNT", "DEPENDENCY_DEPTH",
    "PATHS_ALLOW", "REQUIRED_PATHS", "WRITE_BATCH_COUNT", "INTEGRATION", "CONFLICT",
    "CONTRACT_EXPANDED", "AMBIGUITY", "CONTRACT_CHANGE", "SCOPE_CHANGE",
    "ACCEPTANCE_CHANGE", "CONSTRAINT_CHANGE", "ARCHITECTURE_CHANGE", "SECURITY_CHANGE",
    "COMPATIBILITY_CHANGE", "BUDGET",
)
PARENT_CHANGE_FIELDS = (
    "CONTRACT_CHANGE", "SCOPE_CHANGE", "ACCEPTANCE_CHANGE",
    "CONSTRAINT_CHANGE", "ARCHITECTURE_CHANGE", "SECURITY_CHANGE",
    "COMPATIBILITY_CHANGE",
)
PARENT_FAST_PATH_BUDGET = {
    "MODEL_CALL_LIMIT": 4,
    "HYPOTHESIS_LIMIT": 2,
    "MODEL_ACTIVE_SECONDS_LIMIT": 600,
    "REPAIR_CYCLE_LIMIT": 1,
    "STAGNANT_CALL_LIMIT": 1,
}
OUTBOUND_FIELDS = (
    "PROTOCOL", "AGENT", "STATUS", "FAILURE", "REQUEST", "EVIDENCE", "NEXT", "SUMMARY",
)
AUDIT_IDENTITY_FIELDS = ("AUDITOR_ROLE", "AUDITOR_INSTANCE_ID", "AGENT_INSTANCE_ID")
HANDOFF_ROUTES = {
    ("luna_worker", "PASS", "none"): "parent:manifest_gate",
    ("luna_worker", "BLOCKED", "none"): "parent:pause",
    ("luna_worker", "ESCALATE", "technical_resolution"): "parent:terra",
    ("terra_auditor", "PASS", "none"): "parent:manifest_gate",
    ("terra_auditor", "BLOCKED", "none"): "parent:pause",
    ("terra_auditor", "ESCALATE", "implementation"): "parent:repair_or_sol",
    ("terra_auditor", "ESCALATE", "planning_resolution"): "parent:sol",
    ("sol_planner", "PASS", "none"): "parent:manifest_gate",
    ("sol_planner", "BLOCKED", "none"): "parent:pause",
    ("sol_planner", "BLOCKED", "execution"): "parent:luna",
    ("sol_planner", "BLOCKED", "human_authority"): "parent:user",
}
LEGAL_HANDOFFS = set(HANDOFF_ROUTES)
PARENT_RISK_FLAGS = frozenset({
    "security", "privacy", "public-contract", "data-schema-or-migration", "destructive",
    "production", "external-commitment", "license", "material-compatibility",
    "concurrency", "irreversible", "material-cost", "architecture", "compatibility",
})


def _contract_value(contract: Mapping[str, object], key: str, default: object = None) -> object:
    folded = key.casefold()
    for candidate, value in contract.items():
        if str(candidate).casefold() == folded:
            return value
    return default


def _has_field(contract: Mapping[str, object], key: str) -> bool:
    folded = key.casefold()
    return any(str(candidate).casefold() == folded for candidate in contract)


def _conflicting_fields(contract: Mapping[str, object]) -> list[str]:
    seen: set[str] = set()
    conflicts: list[str] = []
    for candidate in contract:
        folded = str(candidate).casefold()
        if folded in seen and folded not in conflicts:
            conflicts.append(folded)
        seen.add(folded)
    return conflicts


def _non_empty(value: object) -> bool:
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (Mapping, Sequence, set, frozenset)):
        return bool(value)
    return bool(value)


def _none_items(value: object) -> bool:
    if value is None or value == [] or value == "none":
        return True
    return isinstance(value, list) and all(
        isinstance(item, str) and item.strip().casefold() == "none" for item in value
    )


def _false_or_none(value: object) -> bool:
    if value is False or value is None or value == "none":
        return True
    return isinstance(value, list) and all(
        isinstance(item, str) and item.strip().casefold() == "none" for item in value
    )


def _strict_int(value: object) -> int | None:
    return None if isinstance(value, bool) or not isinstance(value, int) else value


def _lower_git_hex(value: object) -> bool:
    return isinstance(value, str) and len(value) in {40, 64} and re.fullmatch(r"[0-9a-f]+", value) is not None


def _parent_budget_reasons(value: object) -> list[str]:
    """Mirror runtime_guard.validate_budget for the parent ceiling."""
    if not isinstance(value, Mapping):
        return ["BUDGET must be an object"]
    reasons: list[str] = []
    for field, ceiling in PARENT_FAST_PATH_BUDGET.items():
        actual = _strict_int(_contract_value(value, field))
        if actual is None or actual <= 0:
            reasons.append(f"BUDGET.{field} must be a positive integer")
        elif actual > ceiling:
            reasons.append(f"BUDGET.{field} exceeds the parent runtime ceiling")
    return reasons


def _path_inside(path: str, roots: set[str]) -> bool:
    return any(root == "." or path == root or path.startswith(root.rstrip("/") + "/") for root in roots)


def _repository_paths(value: object, *, allow_empty: bool) -> list[str] | None:
    if not isinstance(value, list):
        return None
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            return None
        normalized = item.replace("\\", "/").strip()
        if normalized == ".":
            result.append(normalized)
            continue
        parts = normalized.split("/")
        if normalized.startswith("/") or (len(normalized) > 1 and normalized[1] == ":"):
            return None
        if any(part in {"", ".", ".."} for part in parts):
            return None
        result.append(normalized)
    return result if result or allow_empty else None


def parent_fast_path_ineligibility_reasons(contract: Mapping[str, object]) -> list[str]:
    """Return deterministic reasons a parent capability must route to Sol."""
    reasons = [f"conflicting case-insensitive field {name}" for name in _conflicting_fields(contract)]
    if _contract_value(contract, "PLANNER_ROLE") != "parent":
        reasons.append("PLANNER_ROLE must equal parent")
    if _contract_value(contract, "PLANNER_CAPABILITY") != PARENT_FAST_PATH_CAPABILITY:
        reasons.append("PLANNER_CAPABILITY must equal bounded_l1_l2_dispatch")
    if str(_contract_value(contract, "LEVEL", "")).strip().upper() not in {"L1", "L2"}:
        reasons.append("LEVEL must be L1 or L2")
    if _contract_value(contract, "OBJECTIVE_FIXED") is not True:
        reasons.append("OBJECTIVE_FIXED must be true")
    for field in ("BASELINE", "SCOPE_ROOTS", "ACCEPTANCE", "CONSTRAINTS"):
        if not _non_empty(_contract_value(contract, field)):
            reasons.append(f"{field} must be non-empty")
    if not _lower_git_hex(_contract_value(contract, "BASELINE")):
        reasons.append("BASELINE must be a 40 or 64 character lowercase Git hex")
    reasons.extend(_parent_budget_reasons(_contract_value(contract, "BUDGET")))
    if _contract_value(contract, "OPEN_MAJOR_DECISIONS") is not False:
        reasons.append("OPEN_MAJOR_DECISIONS must be false")
    for field in ("RISK_FLAGS", "EXTERNAL_ACTIONS"):
        if not _has_field(contract, field) or not _none_items(_contract_value(contract, field)):
            reasons.append(f"{field} must be none")
    exact = {"MAX_DISPATCHES": 1, "COMPONENT_COUNT": 1, "DEPENDENCY_DEPTH": 0, "WRITE_BATCH_COUNT": 1}
    for field, expected in exact.items():
        if _strict_int(_contract_value(contract, field)) != expected:
            reasons.append(f"{field} must equal {expected}")
    for field in PARENT_CHANGE_FIELDS:
        if _contract_value(contract, field) is not False:
            reasons.append(f"{field} must be false")
    for field in ("INTEGRATION", "CONFLICT", "CONTRACT_EXPANDED", "AMBIGUITY"):
        if not _has_field(contract, field) or not _false_or_none(_contract_value(contract, field)):
            reasons.append(f"{field} must be false/none")
    roots_list = _repository_paths(_contract_value(contract, "SCOPE_ROOTS"), allow_empty=False)
    roots = set(roots_list or [])
    if roots_list is None:
        reasons.append("SCOPE_ROOTS must be repository-relative path list")
    for field, allow_empty in (("PATHS_ALLOW", False), ("REQUIRED_PATHS", True)):
        if not _has_field(contract, field):
            reasons.append(f"{field} must be explicitly present")
            continue
        paths = _repository_paths(_contract_value(contract, field), allow_empty=allow_empty)
        if paths is None:
            reasons.append(f"{field} must be repository-relative path list")
        elif roots and any(not _path_inside(path, roots) for path in paths):
            reasons.append(f"{field} must stay inside SCOPE_ROOTS")
    return list(dict.fromkeys(reasons))


def is_parent_fast_path_eligible(contract: Mapping[str, object]) -> bool:
    return not parent_fast_path_ineligibility_reasons(contract)


def route_planner(contract: Mapping[str, object]) -> str:
    return "parent" if is_parent_fast_path_eligible(contract) else "sol_planner"


def validate_plan_identity(plan: Mapping[str, object], *, expected_role: str | None = None) -> list[str]:
    errors = [f"conflicting case-insensitive field {name}" for name in _conflicting_fields(plan)]
    for field in ("PLAN_ID", "PLANNER_ROLE", "PLANNER_INSTANCE_ID", "AUDITOR_INSTANCE_ID"):
        if not _non_empty(_contract_value(plan, field)):
            errors.append(f"{field} must be non-empty")
    role = _contract_value(plan, "PLANNER_ROLE")
    if expected_role is not None and role != expected_role:
        errors.append(f"PLANNER_ROLE must be {expected_role}")
    elif expected_role is None and role not in {"sol_planner", "parent"}:
        errors.append("PLANNER_ROLE must identify an authorized planner")
    planner = str(_contract_value(plan, "PLANNER_INSTANCE_ID", "")).strip().casefold()
    auditor = str(_contract_value(plan, "AUDITOR_INSTANCE_ID", "")).strip().casefold()
    if auditor and auditor == planner:
        errors.append("AUDITOR_INSTANCE_ID must differ from PLANNER_INSTANCE_ID")
    if auditor.casefold() in {"parent", "parent-agent"}:
        errors.append("AUDITOR_INSTANCE_ID must identify an independent terra_auditor")
    return list(dict.fromkeys(errors))


class RoleLeaseRegistry:
    """Immutable per-plan role leases used to reject planner/auditor reuse."""

    def __init__(self) -> None:
        self._leases: dict[tuple[str, str], str] = {}
        self._planned: dict[str, set[str]] = {}
        self._implemented: dict[str, set[str]] = {}

    def lease(self, plan_id: str, agent_instance_id: str, role: str) -> bool:
        if not all(str(value).strip() for value in (plan_id, agent_instance_id, role)):
            return False
        key = (str(plan_id), str(agent_instance_id).strip().casefold())
        if key in self._leases and self._leases[key] != role:
            return False
        self._leases[key] = role
        return True

    def _record(self, bucket: dict[str, set[str]], plan_id: str, agent: str, role: str) -> bool:
        if not self.lease(plan_id, agent, role):
            return False
        bucket.setdefault(str(agent).strip().casefold(), set()).add(str(plan_id))
        return True

    def record_planned(self, plan_id: str, agent: str, role: str) -> bool:
        return role in {"sol_planner", "parent"} and self._record(self._planned, plan_id, agent, role)

    def record_implemented(self, plan_id: str, agent: str, role: str) -> bool:
        return role == "luna_worker" and self._record(self._implemented, plan_id, agent, role)

    def record_audited(self, plan_id: str, agent: str, role: str = "terra_auditor") -> bool:
        return role == "terra_auditor" and self.lease(plan_id, agent, role)

    def lease_role(self, plan_id: str, agent: str) -> str | None:
        return self._leases.get((str(plan_id), str(agent).strip().casefold()))

    def validate_plan(self, plan: Mapping[str, object]) -> list[str]:
        errors = validate_plan_identity(plan)
        plan_id = str(_contract_value(plan, "PLAN_ID", ""))
        planner = str(_contract_value(plan, "PLANNER_INSTANCE_ID", "")).strip().casefold()
        role = str(_contract_value(plan, "PLANNER_ROLE", ""))
        auditor = str(_contract_value(plan, "AUDITOR_INSTANCE_ID", "")).strip().casefold()
        if self.lease_role(plan_id, planner) != role:
            errors.append("planner instance has no matching role lease")
        if plan_id not in self._planned.get(planner, set()):
            errors.append("planner instance must be recorded as planned")
        if plan_id in self._implemented.get(planner, set()):
            errors.append("planner instance cannot implement PLAN_ID")
        if self.lease_role(plan_id, auditor) in {"sol_planner", "parent", "luna_worker"}:
            errors.append("auditor instance cannot reuse planner or luna role lease")
        if plan_id in self._planned.get(auditor, set()) or plan_id in self._implemented.get(auditor, set()):
            errors.append("auditor instance cannot have planned or implemented PLAN_ID")
        return list(dict.fromkeys(errors))

    def validate_audit(self, plan_id: str, planner_instance_id: str, auditor_instance_id: str) -> bool:
        planner_instance_id = str(planner_instance_id).strip().casefold()
        auditor_instance_id = str(auditor_instance_id).strip().casefold()
        if not auditor_instance_id or auditor_instance_id == planner_instance_id:
            return False
        if self.lease_role(plan_id, planner_instance_id) not in {"sol_planner", "parent"}:
            return False
        if str(plan_id) not in self._planned.get(str(planner_instance_id), set()):
            return False
        if self.lease_role(plan_id, auditor_instance_id) in {"sol_planner", "parent", "luna_worker"}:
            return False
        return str(plan_id) not in self._planned.get(str(auditor_instance_id), set()) and str(plan_id) not in self._implemented.get(str(auditor_instance_id), set())


def validate_role_independence(
    plan: Mapping[str, object], *, lease_registry: RoleLeaseRegistry | None = None,
    planned_plan_ids: Mapping[str, object] | None = None,
    implemented_plan_ids: Mapping[str, object] | None = None,
) -> list[str]:
    errors = validate_plan_identity(plan)
    if lease_registry is None and isinstance(planned_plan_ids, RoleLeaseRegistry):
        lease_registry, planned_plan_ids = planned_plan_ids, None
    if lease_registry is not None:
        errors.extend(lease_registry.validate_plan(plan))
        return list(dict.fromkeys(errors))
    plan_id = str(_contract_value(plan, "PLAN_ID", ""))
    planner = str(_contract_value(plan, "PLANNER_INSTANCE_ID", ""))
    auditor = str(_contract_value(plan, "AUDITOR_INSTANCE_ID", ""))
    if isinstance(implemented_plan_ids, Mapping) and plan_id in implemented_plan_ids.get(planner, ()):
        errors.append("planner instance cannot implement PLAN_ID")
    for label, registry in (("planned", planned_plan_ids), ("implemented", implemented_plan_ids)):
        values = registry.get(auditor, ()) if isinstance(registry, Mapping) else ()
        if isinstance(values, str):
            values = (values,)
        if plan_id in values:
            errors.append(f"auditor instance cannot have {label} PLAN_ID")
    return list(dict.fromkeys(errors))


def validate_dispatch_identity(dispatch: Mapping[str, object], *, lease_registry: RoleLeaseRegistry | None = None) -> list[str]:
    role = str(_contract_value(dispatch, "PLANNER_ROLE", "")).strip()
    if role not in {"sol_planner", "parent"}:
        return ["PLANNER_ROLE must identify an authorized planner"]
    errors = validate_plan_identity(dispatch, expected_role=role)
    if not _non_empty(_contract_value(dispatch, "DISPATCH_ID")):
        errors.append("DISPATCH_ID must be non-empty")
    if role == "parent" and not is_parent_fast_path_eligible(dispatch):
        errors.append("parent DISPATCH is not eligible")
    if lease_registry is not None:
        errors.extend(lease_registry.validate_plan(dispatch))
    return list(dict.fromkeys(errors))


validate_dispatch_planner = validate_dispatch_identity


def error(message: str) -> None:
    ERRORS.append(message)


def read(relative: str | Path) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def resolve_handoff_route(agent: str, status: str, request: str) -> str:
    try:
        return HANDOFF_ROUTES[(agent, status, request)]
    except KeyError as exc:
        raise ValueError(f"illegal handoff combination: {agent}/{status}/{request}") from exc


def require_instruction_line(relative: str, instructions: str, anchor: str, required_terms: tuple[str, ...]) -> None:
    line = next((line for line in instructions.splitlines() if anchor in line), None)
    if line is None:
        error(f"{relative}: missing instruction anchored by {anchor!r}")
        return
    for term in required_terms:
        if term not in line:
            error(f"{relative}: {anchor!r} instruction is missing {term!r}")


def validate_agents() -> None:
    expected = {
        "agents/luna-worker.toml": ("luna_worker", "gpt-5.6-luna", "max", None),
        "agents/sol-planner.toml": ("sol_planner", "gpt-5.6-sol", "medium", None),
        "agents/terra-auditor.toml": ("terra_auditor", "gpt-5.6-terra", "high", "read-only"),
    }
    agents_root = ROOT / "agents"
    if agents_root.exists():
        for candidate in agents_root.glob("*.toml"):
            if candidate.name not in {Path(path).name for path in expected}:
                error(f"agents/{candidate.name}: unexpected child profile")
    for relative, (name, model, effort, sandbox) in expected.items():
        try:
            data = tomllib.loads(read(relative))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            error(f"{relative}: TOML parse failed: {exc}")
            continue
        if data.get("name") != name:
            error(f"{relative}: expected name={name!r}")
        if data.get("model") != model:
            error(f"{relative}: expected model={model!r}")
        if data.get("model_reasoning_effort") != effort:
            error(f"{relative}: expected model_reasoning_effort={effort!r}")
        if sandbox is not None and data.get("sandbox_mode") != sandbox:
            error(f"{relative}: expected sandbox_mode={sandbox!r}")
        instructions = str(data.get("developer_instructions", ""))
        if [line.strip() for line in instructions.splitlines() if line.strip().startswith("Language:")] != [LANGUAGE_RULE]:
            error(f"{relative}: English language rule is missing or incorrect")
        if "outbound result envelope:" not in instructions:
            error(f"{relative}: missing outbound result envelope")
        elif not re.search(r"NEXT:\s*parent", instructions):
            error(f"{relative}: outbound result envelope NEXT must equal parent")
        for term in ("PROTOCOL", "AGENT", "STATUS", "FAILURE", "REQUEST", "EVIDENCE", "SUMMARY"):
            if term not in instructions:
                error(f"{relative}: missing envelope field {term}")
        if name == "luna_worker":
            required = (
                "valid inbound DISPATCH", "BLOCKED/none", "parent:pause",
                "PATHS_ALLOW", "runtime guard", "check_scope.py",
                "dependency preparation only when the DISPATCH explicitly declares",
                "must not install tools", "ESCALATE/dependency/technical_resolution",
            )
        elif name == "sol_planner":
            required = (
                "PLAN_MANIFEST", "DISPATCH_WAVE", "EXPANSION_GATE",
                "PLANNER_CAPABILITY", "bounded_l1_l2_dispatch", "human_authority",
                "Declare every dependency-preparation command", "BLOCKED/execution",
                "parent must not install tools", "routing-memory output", "ELIGIBLE_ACTIONS",
            )
        else:
            required = (
                "read-only", "AUDIT_SCOPE/IMPACT_CONE", "A =", "B =", "C =", "D =",
                "independent", *AUDIT_IDENTITY_FIELDS,
                "Stay read-only during pre-PASS technical resolution",
                "never install", "ESCALATE/planning_resolution",
            )
        for term in required:
            if term not in instructions:
                error(f"{relative}: missing role contract text {term!r}")
        if ("terra_" + "planner") in instructions:
            error(f"{relative}: retired planner role is registered")


def _fenced_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    active: list[str] | None = None
    for line in text.splitlines():
        if re.match(r"^\s*(```+|~~~+)", line):
            if active is None:
                active = []
            else:
                blocks.append("\n".join(active))
                active = None
        elif active is not None:
            active.append(line)
    return blocks


def validate_fenced_schema(relative: str, text: str, required: Sequence[str], label: str) -> None:
    blocks = _fenced_blocks(text)
    target = "\n".join(blocks)
    for term in required:
        if term not in target:
            error(f"{relative}: {label} missing {term!r}")


def validate_protocol_schema(relative: str, skill: str) -> None:
    validate_fenced_schema(relative, skill, DISPATCH_FIELDS + BUDGET_FIELDS, "inbound DISPATCH packet")
    validate_fenced_schema(relative, skill, OUTBOUND_FIELDS, "outbound result envelope")
    for term in ("PLANNER_CAPABILITY", PARENT_FAST_PATH_CAPABILITY, "parent:sol", "independent terra_auditor"):
        if term not in skill:
            error(f"{relative}: missing fast-path contract text {term!r}")


def markdown_lines(text: str) -> list[tuple[int, str]]:
    return list(enumerate(text.splitlines(), start=1))


def validate_handoff_table(relative: str, skill: str) -> None:
    rows: dict[tuple[str, str, str], str] = {}
    pattern = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|\s*`([^`]+)`")
    for number, line in markdown_lines(skill):
        match = pattern.match(line)
        if not match:
            continue
        agent, status, request, destination = match.groups()
        key = (agent, status, request)
        if key in rows:
            error(f"{relative}:{number}: duplicate handoff route {agent}/{status}/{request}")
        rows[key] = destination
        try:
            expected = resolve_handoff_route(*key)
        except ValueError as exc:
            error(f"{relative}:{number}: {exc}")
            continue
        if expected != destination:
            error(f"{relative}:{number}: handoff route must be {expected!r}")
    for key in sorted(LEGAL_HANDOFFS - set(rows)):
        error(f"{relative}: missing handoff route {'/'.join(key)}")
    for key in rows:
        if key not in LEGAL_HANDOFFS:
            error(f"{relative}: closed route contains retired/illegal role {'/'.join(key)}")


def validate_skill_document(relative: str, required_text: tuple[str, ...], expected_titles: set[str]) -> None:
    skill = read(relative)
    if not skill.startswith("---\n") or "\n---\n" not in skill[4:]:
        error(f"{relative}: missing YAML-style frontmatter")
    for required in required_text:
        if required not in skill:
            error(f"{relative}: missing required text {required!r}")
    validate_protocol_schema(relative, skill)
    validate_handoff_table(relative, skill)
    headings = [(len(m.group(1)), m.group(2)) for _, line in markdown_lines(skill) if (m := re.match(r"^(#{1,6})\s+(.+?)\s*$", line))]
    for previous, current in zip(headings, headings[1:]):
        if current[0] > previous[0] + 1:
            error(f"{relative}: heading level jumps from H{previous[0]} to H{current[0]}")
    actual_titles = {title for _, title in headings}
    for title in sorted(expected_titles - actual_titles):
        error(f"{relative}: missing heading {title!r}")


def markdown_structure(text: str) -> list[str]:
    result: list[str] = []
    in_fence = False
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^(```+|~~~+)", stripped):
            result.append("fence-close" if in_fence else "fence-open")
            in_fence = not in_fence
        elif in_fence:
            result.append("fence-body")
        elif not stripped:
            result.append("blank")
        elif re.match(r"^#{1,6}\s", stripped):
            result.append(f"heading:{len(stripped) - len(stripped.lstrip('#'))}")
        elif stripped.startswith("|"):
            result.append("table-row")
        elif re.match(r"^(?:[-+*]|\d+\.)\s", stripped):
            result.append("list-item")
        else:
            result.append("prose")
    return result


def validate_skill() -> None:
    root = ".agents/skills/lean-dev-router/SKILL.md"
    english = "skill-variants/en/SKILL.md"
    chinese = "skill-variants/zhcn/SKILL.md"
    optimized_english = "skill-variants/en-optimized/SKILL.md"
    optimized_chinese = "skill-variants/zhcn-optimized/SKILL.md"
    root_text = read(root)
    english_text = read(english)
    if root_text != english_text:
        error(f"{root}: must exactly match {english}")
    common = (
        "name: lean-dev-router", "PROTOCOL: lean-dev-router/v2", "PLANNER_CAPABILITY",
        PARENT_FAST_PATH_CAPABILITY, "PLAN_MANIFEST", "DISPATCH_WAVE", "EXPANSION_GATE",
        "N/A (batch coverage)", "integration_owner", "integration_baseline", "integration_paths_allow",
        "integration_acceptance", "python scripts/check_scope.py", "worktree-sha256:<64 lowercase hex>",
        "runtime_guard.py start", "runtime_guard.py audit", "CONTRACT_EFFECT: unchanged",
        "PRODUCT_COUNT", "parent:pause", "REQUEST: execution", "technical_resolution",
        "routing_memory.py decide", "ELIGIBLE_ACTIONS",
    )
    titles = {"Lean Dev Router", "Authority and entry", "Protocol", "Fast path eligibility", "Scope, artifacts, and revision", "Risk fuse and replay", "Terra causal audit and repair", "Integration", "Execution and human gate"}
    for relative in (root, english):
        validate_skill_document(relative, common, titles)
    chinese_titles = {"Lean Dev Router", "权限与入口", "协议", "快速路径资格", "范围、产物与版本", "风险熔断与复现", "Terra 因果审计与修复", "集成", "执行与用户门禁"}
    validate_skill_document(chinese, common, chinese_titles)
    optimized_common = (
        "name: lean-dev-router", "PROTOCOL: lean-dev-router/v2",
        PARENT_FAST_PATH_CAPABILITY, "PLAN_MANIFEST", "DISPATCH_WAVE",
        "EXPANSION_GATE", "PRODUCT_COUNT", "parent:pause",
        "REQUEST: execution", "technical_resolution", "runtime_guard.py start",
        "routing_memory.py decide", "ELIGIBLE_ACTIONS",
    )
    for relative in (optimized_english, optimized_chinese):
        validate_skill_document(relative, optimized_common, {"Lean Dev Router", "Protocol", "Fast path eligibility", "Integration"} if "en-optimized" in relative else {"Lean Dev Router", "协议", "快速路径资格", "集成"})
    if len(english_text) > 12000 or len(re.findall(r"\b[\w-]+\b", english_text)) > 1500:
        error(f"{english}: exceeds context budget")
    if len(read(chinese)) > 12000 or len(re.findall(r"\b[\w-]+\b", read(chinese))) > 1500:
        error(f"{chinese}: exceeds context budget")
    if len(read(optimized_english)) >= len(english_text) or len(read(optimized_chinese)) >= len(read(chinese)):
        error("optimized Skill variants must remain smaller than canonical variants")
    if markdown_structure(read(optimized_english)) != markdown_structure(read(optimized_chinese)):
        error("optimized Skill variants must have aligned Markdown structure")


def validate_runtime_guard() -> None:
    relative = ".agents/skills/lean-dev-router/scripts/runtime_guard.py"
    try:
        source = read(relative)
        tree = ast.parse(source)
    except OSError as exc:
        error(f"{relative}: cannot read runtime guard: {exc}")
        return
    except SyntaxError as exc:
        error(f"{relative}: invalid Python: {exc.msg}")
        return
    allowed = {"__future__", "argparse", "hashlib", "json", "math", "sys", "dataclasses", "pathlib", "typing"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = {alias.name.split(".", 1)[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            names = {str(node.module).split(".", 1)[0]}
        else:
            continue
        for name in names - allowed:
            error(f"{relative}: non-standard or undeclared import {name!r}")
    for term in (
        "validate_dispatch", "validate_parent_dispatch", "preflight_dispatch",
        "validate_revision", "validate_execution", "register_initial_execution",
        "validate_audit_prerequisites", "validate_repair", "abandon_audit",
    ):
        if term not in source:
            error(f"{relative}: missing runtime gate {term!r}")
    for term in (
        "PLANNER_CAPABILITY", PARENT_FAST_PATH_CAPABILITY, "MODEL_CALL_LIMIT",
        "HYPOTHESIS_LIMIT", "REPAIR_CYCLE_LIMIT", "STAGNANT_CALL_LIMIT",
        "finding_requires_sol", "parent_cannot_self_audit",
        "--trusted-parent-instance-id", "--trusted-parent-model",
        "--trusted-parent-reasoning-effort", "TRUSTED_PARENT_MODEL",
        "product_telemetry_missing", "execution_telemetry_missing",
        "execution_registration_missing", "terminal_event_fields",
    ):
        if term not in source:
            error(f"{relative}: missing runtime gate {term!r}")
    assignments: dict[str, object] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                assignments[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue
    for schema in ("AUDIT_BEGIN_FIELDS", "AUDIT_COMPLETE_FIELDS", "AUDIT_ABANDON_FIELDS"):
        fields = assignments.get(schema, ())
        for field in AUDIT_IDENTITY_FIELDS:
            if field not in fields:
                error(f"{relative}: {schema} missing required audit identity field {field!r}")
    for command in ("preflight", "start", "event", "repair", "audit", "schema"):
        if f'add_parser("{command}"' not in source:
            error(f"{relative}: missing runtime gate subcommand {command!r}")


def validate_routing_memory() -> None:
    relative = ".agents/skills/lean-dev-router/scripts/routing_memory.py"
    try:
        source = read(relative)
        tree = ast.parse(source)
    except OSError as exc:
        error(f"{relative}: cannot read routing memory: {exc}")
        return
    except SyntaxError as exc:
        error(f"{relative}: invalid Python: {exc.msg}")
        return
    allowed = {"__future__", "argparse", "hashlib", "json", "math", "sys", "pathlib", "typing"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = {alias.name.split(".", 1)[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            names = {str(node.module).split(".", 1)[0]}
        else:
            continue
        for name in names - allowed:
            error(f"{relative}: non-standard or undeclared import {name!r}")
    for term in (
        "lean-dev-router/routing-memory/v1", "ELIGIBLE_ACTIONS", "DEFAULT_ACTION",
        "POLICY_VERSION", "VERIFIED", "EVIDENCE_FINGERPRINT", "memory_capacity_pending",
        "eligible_actions_only", "insufficient_default_evidence", ".tmp", "replace(path)",
        "MAX_CAPACITY", "MAX_PACKET_BYTES", "must not repeat completed feedback",
    ):
        if term not in source:
            error(f"{relative}: missing adaptive-routing contract {term!r}")
    for command in ("decide", "feedback", "snapshot", "schema"):
        if f'add_parser("{command}"' not in source:
            error(f"{relative}: missing adaptive-routing subcommand {command!r}")


def parse_manifest(text: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    section: str | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        top = re.fullmatch(r"([A-Za-z_][\w-]*):", line)
        if top:
            section = top.group(1)
            if section in result:
                raise ValueError(f"line {number}: duplicate section")
            result[section] = {}
            continue
        item = re.fullmatch(r"  ([A-Za-z_][\w-]*):\s*(.+)", line)
        if item is None or section is None:
            raise ValueError(f"line {number}: unsupported YAML structure")
        key, raw = item.groups()
        if key in result[section]:
            raise ValueError(f"line {number}: duplicate key")
        value = ast.literal_eval(raw)
        if not isinstance(value, str):
            raise ValueError(f"line {number}: expected scalar")
        result[section][key] = value
    return result


def validate_manifest() -> None:
    relative = ".agents/skills/lean-dev-router/agents/openai.yaml"
    try:
        manifest = parse_manifest(read(relative))
    except (OSError, ValueError, SyntaxError) as exc:
        error(f"{relative}: YAML parse failed: {exc}")
        return
    interface = manifest.get("interface", {})
    for key in ("display_name", "short_description", "default_prompt"):
        if not interface.get(key, "").strip():
            error(f"{relative}: interface.{key} is missing")
    if "$lean-dev-router" not in interface.get("default_prompt", ""):
        error(f"{relative}: default_prompt disagrees with Skill name")


def validate_runtime_language() -> None:
    for base in (ROOT / ".agents", ROOT / "agents"):
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            relative = path.relative_to(ROOT).as_posix()
            if relative == ".agents/skills/lean-dev-router/SKILL.md":
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if not line.isascii():
                    error(f"{relative}:{number}: non-ASCII text is not allowed in runtime files")


def validate_markdown() -> None:
    for path in ROOT.rglob("*.md"):
        if ".git" in path.parts or ".workbuddy" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        fence: str | None = None
        fence_line = 0
        for number, line in enumerate(text.splitlines(), start=1):
            if re.match(r"^\s*(```+|~~~+)", line):
                if fence:
                    fence = None
                    fence_line = 0
                else:
                    fence = line.strip()[0]
                    fence_line = number
        if fence:
            error(f"{path.relative_to(ROOT).as_posix()}:{fence_line}: unclosed Markdown code fence")
        for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text):
            target = match.group(1).split(maxsplit=1)[0].strip("<>")
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            local = target.split("#", 1)[0]
            if local and not (path.parent / local).exists():
                error(f"{path.relative_to(ROOT).as_posix()}: missing local link target {local!r}")


def validate_repository_contract() -> None:
    for path in LEGACY_PATHS:
        if (ROOT / path).exists():
            error(f"legacy runtime path still exists: {path.as_posix()}")
    retired_role = "terra_" + "planner"
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if path.suffix.lower() not in {".md", ".py", ".toml", ".yaml", ".yml"}:
            continue
        text = path.read_text(encoding="utf-8")
        if retired_role in text:
            error(f"{path.relative_to(ROOT).as_posix()}: retired planner role remains")
    required = {
        "README.md": ("docs/zh-CN/README.md", "scripts/check_scope.py", PARENT_FAST_PATH_CAPABILITY),
        "docs/zh-CN/README.md": ("仅供人类阅读", ".agents/skills/lean-dev-router/SKILL.md", "scripts/check_scope.py"),
        "lean-dev-router-self-test-guide.md": ("integration_owner", "tracked/untracked scope evidence", PARENT_FAST_PATH_CAPABILITY),
    }
    for relative, snippets in required.items():
        try:
            text = read(relative)
        except OSError as exc:
            error(f"{relative}: cannot read required file: {exc}")
            continue
        for snippet in snippets:
            if snippet not in text:
                error(f"{relative}: missing contract text {snippet!r}")
    validate_license()
    validate_issue40_assets()


def validate_issue40_assets() -> None:
    relative = "experiments/issue-40-cli/manifest.json"
    try:
        manifest = json.loads(read(relative))
        samples = json.loads(read("experiments/issue-40-cli/results.json"))["samples"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        error(f"{relative}: cannot load experiment evidence: {exc}")
        return
    results = manifest.get("results") if isinstance(manifest, dict) else None
    if not isinstance(results, list) or len(results) != 24:
        error(f"{relative}: expected 24 reconciled results")
        return
    sample_ids = {
        (sample.get("variant"), sample.get("language"), sample.get("run")): sample.get("session_id")
        for sample in samples if isinstance(sample, dict)
    }
    cells = []
    for result in results:
        if not isinstance(result, dict) or not isinstance(result.get("cell"), list):
            error(f"{relative}: malformed result row")
            continue
        cell = tuple(result["cell"])
        cells.append(cell)
        if result.get("ok") is not True or not result.get("session_file"):
            error(f"{relative}: cell {cell!r} lacks successful session evidence")
        if len(result.get("token_events") or []) < 2:
            error(f"{relative}: cell {cell!r} lacks required token-count evidence")
        if sample_ids.get(cell) != result.get("session_id"):
            error(f"{relative}: cell {cell!r} disagrees with results.json")
    if cells != sorted(cells) or len(set(cells)) != 24:
        error(f"{relative}: result cells must be unique and deterministically sorted")

    prompts = sorted((ROOT / "experiments/issue-40-cli").glob("prompt_*.txt"))
    if len(prompts) != 24:
        error("experiments/issue-40-cli: expected 24 captured prompts")
    for path in prompts:
        examples = [line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith('{"variant"')]
        try:
            example = json.loads(examples[-1])
        except (IndexError, json.JSONDecodeError) as exc:
            error(f"{path.relative_to(ROOT).as_posix()}: invalid JSON output example: {exc}")
            continue
        if len(example.get("cases", [])) != 8:
            error(f"{path.relative_to(ROOT).as_posix()}: output example must contain 8 cases")

    runner = read("experiments/run_issue40_short_test_cli.py")
    for marker in (
        "--workdir", "--codex-cli", "--sessions-dir",
        'model_reasoning_effort="max"', "REQUIRED_TOKEN_EVENTS",
        "results.sort", "return 0 if ok == len(cells) else 1",
    ):
        if marker not in runner:
            error(f"experiments/run_issue40_short_test_cli.py: missing evidence control {marker!r}")


def validate_license() -> None:
    try:
        if not read("LICENSE").startswith("MIT License\n"):
            error("LICENSE: expected MIT license text")
    except (OSError, UnicodeError) as exc:
        error(f"LICENSE: cannot read required file: {exc}")


def main() -> int:
    validate_agents()
    validate_skill()
    validate_runtime_guard()
    validate_routing_memory()
    validate_manifest()
    validate_runtime_language()
    validate_markdown()
    validate_repository_contract()
    if ERRORS:
        for message in ERRORS:
            print(f"ERROR: {message}", file=sys.stderr)
        print(f"Validation failed with {len(ERRORS)} error(s).", file=sys.stderr)
        return 1
    print("Repository validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
