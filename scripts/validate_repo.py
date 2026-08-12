#!/usr/bin/env python3
"""Validate the repository's directly executable English runtime."""

from __future__ import annotations

import ast
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
    "PROTOCOL: lean-dev-router/v2",
    "STATUS: DISPATCH",
    "TARGET: implementation",
    "DISPATCH_ID",
    "PLAN_ID",
    "PLANNER_ROLE",
    "PLANNER_INSTANCE_ID",
    "AUDITOR_INSTANCE_ID",
    "TASK_SUMMARY",
    "BASELINE",
    "PATHS_ALLOW",
    "ACCEPTANCE",
    "CONSTRAINTS",
    "NEXT: parent",
)
OUTBOUND_FIELDS = (
    "PROTOCOL",
    "AGENT",
    "STATUS",
    "FAILURE",
    "REQUEST",
    "EVIDENCE",
    "NEXT",
    "SUMMARY",
)
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
    ("sol_planner", "BLOCKED", "implementation"): "parent:luna",
    ("sol_planner", "BLOCKED", "human_authority"): "parent:user",
    ("terra_planner", "PASS", "none"): "parent:manifest_gate",
    ("terra_planner", "BLOCKED", "none"): "parent:pause",
    ("terra_planner", "BLOCKED", "implementation"): "parent:luna",
    ("terra_planner", "ESCALATE", "planning_resolution"): "parent:sol",
}
LEGAL_HANDOFFS = set(HANDOFF_ROUTES)

# Terra planning is intentionally a small, deterministic fast path. Keep the
# predicate data in one place so the executable validator, tests, and runtime
# documentation cannot silently drift apart.
TERRA_ELIGIBLE_LEVELS = frozenset({"L1", "L2"})
TERRA_RISK_FLAGS = frozenset(
    {
        "security",
        "privacy",
        "public-contract",
        "data-schema-or-migration",
        "destructive",
        "production",
        "external-commitment",
        "license",
        "material-compatibility",
        "concurrency",
        "irreversible",
        "material-cost",
    }
)
TERRA_REQUIRED_FIELDS = (
    "LEVEL",
    "OBJECTIVE_FIXED",
    "BASELINE",
    "SCOPE_ROOTS",
    "ACCEPTANCE",
    "OPEN_MAJOR_DECISIONS",
    "RISK_FLAGS",
    "EXTERNAL_ACTIONS",
    "MAX_DISPATCHES",
    "COMPONENT_COUNT",
    "DEPENDENCY_DEPTH",
    "PATHS_ALLOW",
    "REQUIRED_PATHS",
    "WRITE_BATCH_COUNT",
    "CONTRACT_EXPANDED",
    "AMBIGUITY",
)


def _contract_value(contract: Mapping[str, object], key: str, default: object = None) -> object:
    """Read a contract field case-insensitively without mutating caller data."""
    if key in contract:
        return contract[key]
    folded = key.casefold()
    for candidate, value in contract.items():
        if str(candidate).casefold() == folded:
            return value
    return default


def _has_field(contract: Mapping[str, object], key: str) -> bool:
    folded = key.casefold()
    return any(str(candidate).casefold() == folded for candidate in contract)


def _conflicting_fields(contract: Mapping[str, object]) -> list[str]:
    """Return case-insensitive field names that occur more than once."""
    seen: dict[str, str] = {}
    conflicts: list[str] = []
    for candidate in contract:
        name = str(candidate)
        folded = name.casefold()
        if folded in seen and folded not in conflicts:
            conflicts.append(folded)
        else:
            seen[folded] = name
    return conflicts


def _non_empty(value: object) -> bool:
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (Mapping, Sequence, set, frozenset)):
        return bool(value)
    return bool(value)


def _items(value: object) -> set[str]:
    """Normalize list-like risk/action fields for the eligibility predicate."""
    if value is None:
        return set()
    if isinstance(value, str):
        values = re.split(r"[,\s]+", value.strip()) if value.strip() else []
    elif isinstance(value, Mapping):
        values = list(value)
    elif isinstance(value, Sequence) or isinstance(value, (set, frozenset)):
        values = list(value)
    else:
        values = [value]
    return {str(item).strip().casefold() for item in values if str(item).strip()}


def _strict_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value.strip()):
        return int(value.strip())
    return None


def _path_inside(path: str, roots: set[str]) -> bool:
    normalized = path.replace("\\", "/").strip("/")
    if not normalized:
        return True
    for root in roots:
        candidate = root.replace("\\", "/").strip("/")
        if candidate in {"", "."} or normalized == candidate or normalized.startswith(candidate + "/"):
            return True
    return False


def _repository_paths(value: object, *, allow_empty: bool) -> list[str] | None:
    """Return canonical repository-relative paths or None for malformed evidence."""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return None
    paths: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            return None
        normalized = item.replace("\\", "/").strip()
        parts = normalized.split("/")
        if (
            normalized.startswith("/")
            or re.match(r"^[A-Za-z]:", normalized)
            or any(part in {"", ".."} for part in parts)
        ):
            return None
        paths.append(normalized)
    return paths if paths or allow_empty else None


def terra_planner_ineligibility_reasons(contract: Mapping[str, object]) -> list[str]:
    """Return stable, ordered reasons a contract must go directly to Sol."""
    reasons = [f"conflicting case-insensitive field {name}" for name in _conflicting_fields(contract)]
    level = str(_contract_value(contract, "LEVEL", "")).strip().upper()
    if level not in TERRA_ELIGIBLE_LEVELS:
        reasons.append("LEVEL must be L1 or L2")
    if _contract_value(contract, "OBJECTIVE_FIXED") is not True:
        reasons.append("OBJECTIVE_FIXED must be true")
    for field in ("BASELINE", "SCOPE_ROOTS", "ACCEPTANCE"):
        if not _non_empty(_contract_value(contract, field)):
            reasons.append(f"{field} must be non-empty")
    if _contract_value(contract, "OPEN_MAJOR_DECISIONS") is not False:
        reasons.append("OPEN_MAJOR_DECISIONS must be false")

    if not _has_field(contract, "RISK_FLAGS"):
        reasons.append("RISK_FLAGS must be none")
    risk_flags = _items(_contract_value(contract, "RISK_FLAGS"))
    risk_flags.discard("none")
    if risk_flags:
        reasons.append("RISK_FLAGS must be none")
    if not _has_field(contract, "EXTERNAL_ACTIONS"):
        reasons.append("EXTERNAL_ACTIONS must be none")
    actions = _items(_contract_value(contract, "EXTERNAL_ACTIONS"))
    actions.discard("none")
    if actions:
        reasons.append("EXTERNAL_ACTIONS must be none")

    max_dispatches = _strict_int(_contract_value(contract, "MAX_DISPATCHES"))
    if max_dispatches != 1:
        reasons.append("MAX_DISPATCHES must equal 1")
    components = _strict_int(_contract_value(contract, "COMPONENT_COUNT"))
    if components is None or components < 1 or components > 2:
        reasons.append("COMPONENT_COUNT must be between 1 and 2")
    depth = _strict_int(_contract_value(contract, "DEPENDENCY_DEPTH"))
    if depth is None or depth < 0 or depth > 1:
        reasons.append("DEPENDENCY_DEPTH must be at most 1")

    if not _has_field(contract, "WRITE_BATCH_COUNT"):
        reasons.append("WRITE_BATCH_COUNT must be explicitly 1")
    batch_value = _contract_value(contract, "WRITE_BATCH_COUNT")
    if not isinstance(batch_value, int) or isinstance(batch_value, bool) or batch_value != 1:
        reasons.append("more than one write batch")

    roots_list = _repository_paths(_contract_value(contract, "SCOPE_ROOTS"), allow_empty=False)
    if roots_list is None:
        reasons.append("SCOPE_ROOTS must be repository-relative path list")
        roots: set[str] = set()
    else:
        roots = set(roots_list)

    if not _has_field(contract, "REQUIRED_PATHS"):
        reasons.append("REQUIRED_PATHS must be explicitly present")
    required_paths = _repository_paths(
        _contract_value(contract, "REQUIRED_PATHS"), allow_empty=True
    )
    if required_paths is None:
        reasons.append("REQUIRED_PATHS must be a repository-relative path list")
    elif roots:
        outside = [path for path in required_paths if not _path_inside(path, roots)]
        if outside:
            reasons.append("required path outside SCOPE_ROOTS")

    if not _has_field(contract, "PATHS_ALLOW"):
        reasons.append("PATHS_ALLOW must be explicitly present")
    paths_allow = _repository_paths(
        _contract_value(contract, "PATHS_ALLOW"), allow_empty=False
    )
    if paths_allow is None:
        reasons.append("PATHS_ALLOW must be a non-empty repository-relative path list")
    elif roots:
        outside = [path for path in paths_allow if not _path_inside(path, roots)]
        if outside:
            reasons.append("PATHS_ALLOW outside SCOPE_ROOTS")

    if not _has_field(contract, "CONTRACT_EXPANDED"):
        reasons.append("CONTRACT_EXPANDED must be explicitly false")
    expansion = _contract_value(contract, "CONTRACT_EXPANDED")
    if expansion is not False:
        reasons.append("contract expansion")
    if not _has_field(contract, "AMBIGUITY"):
        reasons.append("AMBIGUITY must be explicitly false")
    ambiguity = _contract_value(contract, "AMBIGUITY")
    if ambiguity is not False:
        reasons.append("ambiguity")
    return reasons


def is_terra_planner_eligible(contract: Mapping[str, object]) -> bool:
    """Return whether Terra may replace routine Sol planning for this contract."""
    return not terra_planner_ineligibility_reasons(contract)


# Friendly aliases used by integrations and regression tests.
terra_planner_eligible = is_terra_planner_eligible
terra_planner_eligibility = is_terra_planner_eligible
eligibility_reasons = terra_planner_ineligibility_reasons


def route_planner(contract: Mapping[str, object]) -> str:
    """Select Terra's fast path or direct Sol fallback without an audit hop."""
    return "terra_planner" if is_terra_planner_eligible(contract) else "sol_planner"


route_contract = route_planner
select_planner = route_planner


def validate_plan_identity(
    plan: Mapping[str, object], *, expected_role: str | None = None
) -> list[str]:
    """Validate the immutable identity fields every planner manifest carries."""
    errors = [f"conflicting case-insensitive field {name}" for name in _conflicting_fields(plan)]
    for field in (
        "PLAN_ID",
        "PLANNER_ROLE",
        "PLANNER_INSTANCE_ID",
        "AUDITOR_INSTANCE_ID",
    ):
        if not _non_empty(_contract_value(plan, field)):
            errors.append(f"{field} must be non-empty")
    planner_role = _contract_value(plan, "PLANNER_ROLE")
    if expected_role is not None and planner_role != expected_role:
        errors.append(f"PLANNER_ROLE must be {expected_role}")
    elif expected_role is None and planner_role not in {"terra_planner", "sol_planner"}:
        errors.append("PLANNER_ROLE must identify an authorized planner")
    planner = _contract_value(plan, "PLANNER_INSTANCE_ID")
    auditor = _contract_value(plan, "AUDITOR_INSTANCE_ID")
    if _non_empty(auditor) and auditor == planner:
        errors.append("AUDITOR_INSTANCE_ID must differ from PLANNER_INSTANCE_ID")
    return errors


def validate_role_independence(
    plan: Mapping[str, object],
    *,
    lease_registry: "RoleLeaseRegistry | None" = None,
    planned_plan_ids: Mapping[str, object] | None = None,
    implemented_plan_ids: Mapping[str, object] | None = None,
) -> list[str]:
    """Reject self-implementation and cross-role identity reuse.

    Planner self-registration in ``planned_plan_ids`` is valid. The planner
    must not appear in implementation records, while the auditor must appear in
    neither planned nor implemented records. When a ``RoleLeaseRegistry`` is
    supplied, its concrete ``(PLAN_ID, AGENT_INSTANCE_ID)`` leases are the
    authoritative source.
    """
    errors = validate_plan_identity(plan)
    if lease_registry is None and isinstance(planned_plan_ids, RoleLeaseRegistry):
        lease_registry = planned_plan_ids
        planned_plan_ids = None
    if lease_registry is not None:
        errors.extend(lease_registry.validate_plan(plan))
        return list(dict.fromkeys(errors))
    planner = str(_contract_value(plan, "PLANNER_INSTANCE_ID", ""))
    plan_id = str(_contract_value(plan, "PLAN_ID", ""))
    auditor = _contract_value(plan, "AUDITOR_INSTANCE_ID")
    implemented = implemented_plan_ids.get(planner, ()) if isinstance(implemented_plan_ids, Mapping) else ()
    if isinstance(implemented, str):
        implemented = (implemented,)
    if plan_id in implemented:
        errors.append("planner instance cannot implement PLAN_ID")
    for label, registry in (("planned", planned_plan_ids), ("implemented", implemented_plan_ids)):
        if not auditor or not isinstance(registry, Mapping):
            continue
        auditor_values = registry.get(str(auditor), ())
        if isinstance(auditor_values, str):
            auditor_values = (auditor_values,)
        if plan_id in auditor_values:
            errors.append(f"auditor instance cannot have {label} PLAN_ID")
    return list(dict.fromkeys(errors))


class RoleLeaseRegistry:
    """Small in-memory guard for immutable per-plan agent role leases."""

    def __init__(self) -> None:
        self._leases: dict[tuple[str, str], str] = {}
        self._planned: dict[str, set[str]] = {}
        self._implemented: dict[str, set[str]] = {}

    def lease(self, plan_id: str, agent_instance_id: str, role: str) -> bool:
        if not str(plan_id).strip() or not str(agent_instance_id).strip() or not str(role).strip():
            return False
        key = (str(plan_id), str(agent_instance_id))
        previous = self._leases.get(key)
        if previous is not None and previous != role:
            return False
        self._leases[key] = str(role)
        return True

    def _record(self, bucket: dict[str, set[str]], plan_id: str, agent_instance_id: str, role: str) -> bool:
        if not self.lease(plan_id, agent_instance_id, role):
            return False
        bucket.setdefault(str(agent_instance_id), set()).add(str(plan_id))
        return True

    def record_planned(self, plan_id: str, agent_instance_id: str, role: str) -> bool:
        if role not in {"terra_planner", "sol_planner"}:
            return False
        return self._record(self._planned, plan_id, agent_instance_id, role)

    def record_implemented(self, plan_id: str, agent_instance_id: str, role: str) -> bool:
        if role != "luna_worker":
            return False
        return self._record(self._implemented, plan_id, agent_instance_id, role)

    def record_audited(self, plan_id: str, agent_instance_id: str, role: str = "terra_auditor") -> bool:
        if role != "terra_auditor":
            return False
        return self.lease(plan_id, agent_instance_id, role)

    def lease_role(self, plan_id: str, agent_instance_id: str) -> str | None:
        """Return the concrete role lease for one plan/agent pair."""
        return self._leases.get((str(plan_id), str(agent_instance_id)))

    def validate_plan(self, plan: Mapping[str, object]) -> list[str]:
        """Validate planner, auditor, and implementation identity against leases."""
        errors = validate_plan_identity(plan)
        plan_id = str(_contract_value(plan, "PLAN_ID", ""))
        planner_id = str(_contract_value(plan, "PLANNER_INSTANCE_ID", ""))
        planner_role = str(_contract_value(plan, "PLANNER_ROLE", ""))
        auditor_id = str(_contract_value(plan, "AUDITOR_INSTANCE_ID", ""))
        planner_lease = self.lease_role(plan_id, planner_id)
        if planner_lease != planner_role:
            errors.append("planner instance has no matching role lease")
        if plan_id not in self._planned.get(planner_id, set()):
            errors.append("planner instance must be recorded as planned")
        if plan_id in self._implemented.get(planner_id, set()):
            errors.append("planner instance cannot implement PLAN_ID")
        auditor_lease = self.lease_role(plan_id, auditor_id)
        if auditor_lease in {"terra_planner", "sol_planner", "luna_worker"}:
            errors.append("auditor instance cannot reuse planner or luna role lease")
        if plan_id in self._planned.get(auditor_id, set()):
            errors.append("auditor instance cannot have planned PLAN_ID")
        if plan_id in self._implemented.get(auditor_id, set()):
            errors.append("auditor instance cannot have implemented PLAN_ID")
        return list(dict.fromkeys(errors))

    def validate_audit(self, plan_id: str, planner_instance_id: str, auditor_instance_id: str) -> bool:
        if not auditor_instance_id or auditor_instance_id == planner_instance_id:
            return False
        plan = str(plan_id)
        planner_role = self.lease_role(plan, str(planner_instance_id))
        if planner_role not in {"terra_planner", "sol_planner"}:
            return False
        if plan not in self._planned.get(str(planner_instance_id), set()):
            return False
        auditor_role = self.lease_role(plan, str(auditor_instance_id))
        if auditor_role in {"terra_planner", "sol_planner", "luna_worker"}:
            return False
        return plan not in self._planned.get(str(auditor_instance_id), set()) and plan not in self._implemented.get(str(auditor_instance_id), set())


def validate_dispatch_identity(
    dispatch: Mapping[str, object], *, lease_registry: RoleLeaseRegistry | None = None
) -> list[str]:
    """Validate planner fields Luna must check before accepting a DISPATCH."""
    role = str(_contract_value(dispatch, "PLANNER_ROLE", "")).strip()
    if role not in {"sol_planner", "terra_planner"}:
        return ["PLANNER_ROLE must identify an authorized planner"]
    errors = validate_plan_identity(dispatch, expected_role=role)
    if not _non_empty(_contract_value(dispatch, "DISPATCH_ID")):
        errors.append("DISPATCH_ID must be non-empty")
    if role == "terra_planner" and not is_terra_planner_eligible(dispatch):
        errors.append("terra_planner DISPATCH is not eligible")
    if lease_registry is not None:
        errors.extend(lease_registry.validate_plan(dispatch))
    return list(dict.fromkeys(errors))


# Compatibility names for callers that use the validator as a tiny runtime API.
validate_dispatch_planner = validate_dispatch_identity


def error(message: str) -> None:
    ERRORS.append(message)


def read(relative: str | Path) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def resolve_handoff_route(agent: str, status: str, request: str) -> str:
    """Resolve one v2 handoff using the authoritative finite transition table."""
    handoff = (agent, status, request)
    try:
        return HANDOFF_ROUTES[handoff]
    except KeyError as exc:
        raise ValueError(
            f"illegal handoff combination: {agent}/{status}/{request}"
        ) from exc


def require_instruction_line(
    relative: str,
    instructions: str,
    anchor: str,
    required_terms: tuple[str, ...],
) -> None:
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
        "agents/terra-auditor.toml": (
            "terra_auditor",
            "gpt-5.6-terra",
            "high",
            "read-only",
        ),
        "agents/terra-planner.toml": (
            "terra_planner",
            "gpt-5.6-terra",
            "high",
            "read-only",
        ),
    }
    for relative, (name, model, effort, sandbox) in expected.items():
        try:
            data = tomllib.loads(read(relative))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            error(f"{relative}: TOML parse failed: {exc}")
            continue
        for key, value in {
            "name": name,
            "model": model,
            "model_reasoning_effort": effort,
        }.items():
            if data.get(key) != value:
                error(f"{relative}: expected {key}={value!r}")
        if sandbox is not None and data.get("sandbox_mode") != sandbox:
            error(f"{relative}: expected sandbox_mode={sandbox!r}")
        if not str(data.get("description", "")).strip():
            error(f"{relative}: description is empty")
        description = str(data.get("description", ""))
        instructions = str(data.get("developer_instructions", ""))
        language_lines = [
            line.strip()
            for line in instructions.splitlines()
            if line.strip().startswith("Language:")
        ]
        if language_lines != [LANGUAGE_RULE]:
            error(f"{relative}: English language rule is missing or incorrect")
        envelope = next(
            (
                line.strip()
                for line in instructions.splitlines()
                if "outbound result envelope:" in line
            ),
            None,
        )
        if envelope is None:
            error(f"{relative}: missing outbound result envelope")
        else:
            next_field = re.search(r"\bNEXT:\s*([a-z_]+)", envelope)
            if next_field is None or next_field.group(1) != "parent":
                error(f"{relative}: outbound result envelope NEXT must equal parent")
        common = OUTBOUND_FIELDS
        role_terms = {
            "luna_worker": DISPATCH_FIELDS + (
                "PLAN_READY", "missing_dispatch", "scripts/check_scope.py",
                "worktree-sha256:<64 lowercase hex>", "repair budget",
                "Never plan the task, authorize writes, schedule peers, or request human authority.",
                "pre-PASS route", "current diff/paths", "exact failure/replay",
            ),
            "sol_planner": DISPATCH_FIELDS + (
                "PLAN_MANIFEST", "DISPATCH_WAVE", "EXPANSION_GATE",
                "not continuously schedule", "Preregister Terra",
                "IMPACT_CONE", "worktree-sha256:<64 lowercase hex>",
                "three materially distinct attempts", "human_authority",
                "externally measurable latency", "sleep is only polling",
                "terra_planner", "eligible L1/L2", "PLANNER_INSTANCE_ID",
            ),
            "terra_auditor": (
                "Never edit, authorize a write, schedule peers, or request human authority.",
                "AUDIT_SCOPE/IMPACT_CONE", "callers/callees", "A =", "B =",
                "C =", "D =", "DISPATCH_ID", "CONTRACT_EFFECT: unchanged",
                "AFFECTED_PATHS", "ESCALATE/implementation",
                "ESCALATE/planning_resolution",
                "sleep alone is not synchronization proof",
                "pre-PASS technical-resolution", "does not require final scope or revision",
                "never BLOCKED/none",
                "remains independent and read-only", "AUDITOR_INSTANCE_ID",
                "cannot have planned or implemented", "immutable role lease",
            ),
            "terra_planner": (
                "Never write, schedule, wait, amend after execution, audit, or request human_authority.",
                "read-only",
                "gpt-5.6-terra",
                "high",
                "terra_planner",
                "L1/L2",
                "OBJECTIVE_FIXED",
                "SCOPE_ROOTS",
                "RISK_FLAGS",
                "EXTERNAL_ACTIONS",
                "MAX_DISPATCHES",
                "COMPONENT_COUNT",
                "DEPENDENCY_DEPTH",
                "REQUIRED_PATHS",
                "WRITE_BATCH_COUNT",
                "CONTRACT_EXPANDED",
                "AMBIGUITY",
                "directly replaces routine Sol planning",
                "parent to start after its gates",
                "one bounded Luna DISPATCH",
                "finite manifest",
                "PLAN_ID",
                "PLANNER_ROLE",
                "PLANNER_INSTANCE_ID",
                "AUDITOR_INSTANCE_ID",
                "CONTRACT_EXPANDED",
                "required path outside SCOPE_ROOTS",
                "routine Terra-to-Sol review",
                "cannot request human_authority",
            ),
        }
        for term in common + role_terms[name]:
            if term not in instructions:
                error(f"{relative}: missing required instruction {term!r}")
        if name == "terra_planner":
            forbidden = (
                "may schedule",
                "can schedule",
                "may amend",
                "can amend",
                "may audit",
                "can audit",
                "REQUEST: human_authority",
            )
            for term in forbidden:
                if term in instructions:
                    error(f"{relative}: terra_planner contains forbidden authority {term!r}")


def markdown_lines(text: str) -> list[tuple[int, str]]:
    outside: list[tuple[int, str]] = []
    fence: tuple[str, int] | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        marker = re.match(r"^\s*(```+|~~~+)", line)
        if marker:
            opener = marker.group(1)
            token = opener[0]
            length = len(opener)
            if fence is None:
                fence = (token, length)
            elif fence[0] == token and length >= fence[1]:
                fence = None
        elif fence is None:
            outside.append((number, line))
    return outside


def fenced_blocks(text: str) -> list[str]:
    """Return Markdown fenced code block bodies without interpreting their prose."""
    blocks: list[str] = []
    fence: tuple[str, int] | None = None
    body: list[str] = []
    for line in text.splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})(.*)$", line)
        if fence is None:
            if marker:
                opener = marker.group(1)
                fence = (opener[0], len(opener))
                body = []
            continue
        if marker:
            closer = marker.group(1)
            if (
                closer[0] == fence[0]
                and len(closer) >= fence[1]
                and not marker.group(2).strip()
            ):
                blocks.append("\n".join(body))
                fence = None
                body = []
                continue
        body.append(line)
    return blocks


def protocol_fields(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in block.splitlines():
        match = re.match(r"^([A-Z][A-Z_]*):\s*(.*)$", line)
        if not match:
            continue
        name, value = match.groups()
        if name in fields:
            raise ValueError(f"duplicate protocol field {name}")
        fields[name] = value.strip()
    return fields


def validate_protocol_schema(relative: str, skill: str) -> None:
    parsed: list[dict[str, str]] = []
    for block in fenced_blocks(skill):
        try:
            fields = protocol_fields(block)
        except ValueError as exc:
            error(f"{relative}: {exc}")
            continue
        if fields:
            parsed.append(fields)

    dispatch = next(
        (fields for fields in parsed if fields.get("STATUS") == "DISPATCH"), None
    )
    outbound = next((fields for fields in parsed if "AGENT" in fields), None)
    schemas = (
        (
            "inbound DISPATCH protocol",
            dispatch,
            {
                "PROTOCOL": "lean-dev-router/v2",
                "STATUS": "DISPATCH",
                "TARGET": "implementation",
                "DISPATCH_ID": None,
                "PLAN_ID": None,
                "PLANNER_ROLE": None,
                "PLANNER_INSTANCE_ID": None,
                "AUDITOR_INSTANCE_ID": None,
                "TASK_SUMMARY": None,
                "BASELINE": None,
                "PATHS_ALLOW": None,
                "ACCEPTANCE": None,
                "CONSTRAINTS": None,
                "NEXT": "parent",
            },
        ),
        (
            "outbound protocol",
            outbound,
            {
                "PROTOCOL": "lean-dev-router/v2",
                "AGENT": "luna_worker | terra_auditor | terra_planner | sol_planner",
                "STATUS": "PASS | BLOCKED | ESCALATE",
                "FAILURE": "none | missing_dispatch | scope | verification | dependency | ambiguity | major-decision",
                "REQUEST": "none | implementation | technical_resolution | planning_resolution | human_authority",
                "EVIDENCE": None,
                "NEXT": "parent",
                "SUMMARY": None,
            },
        ),
    )
    for label, fields, expected in schemas:
        if fields is None:
            error(f"{relative}: missing {label}")
            continue
        missing = set(expected) - set(fields)
        unexpected = set(fields) - set(expected)
        if missing:
            error(f"{relative}: {label} missing fields: {', '.join(sorted(missing))}")
        if unexpected:
            error(
                f"{relative}: {label} has unexpected fields: "
                f"{', '.join(sorted(unexpected))}"
            )
        if label == "inbound DISPATCH protocol":
            for name in (
                "DISPATCH_ID",
                "PLAN_ID",
                "PLANNER_ROLE",
                "PLANNER_INSTANCE_ID",
                "AUDITOR_INSTANCE_ID",
            ):
                if not fields.get(name):
                    error(f"{relative}: inbound DISPATCH protocol {name} must be non-empty")
        for name, value in expected.items():
            if value is not None and fields.get(name) != value:
                error(
                    f"{relative}: {label} field {name} must be {value!r}"
                )


def validate_handoff_table(relative: str, skill: str) -> None:
    rows: dict[tuple[str, str, str], str] = {}
    row_pattern = re.compile(
        r"^\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*"
        r"\|\s*(.*?)\s*\|\s*$"
    )
    for number, line in markdown_lines(skill):
        match = row_pattern.match(line)
        if not match:
            continue
        agent, status, request, destination_cell = match.groups()
        handoff = (agent, status, request)
        if handoff in rows:
            error(
                f"{relative}:{number}: duplicate handoff route "
                f"{agent}/{status}/{request}"
            )
            continue
        if not destination_cell:
            rows[handoff] = ""
            error(
                f"{relative}:{number}: missing destination for handoff "
                f"{agent}/{status}/{request}"
            )
            continue
        destination_match = re.fullmatch(r"`([^`]+)`[^|]*", destination_cell)
        if destination_match is None:
            continue
        destination = destination_match.group(1)
        rows[handoff] = destination
        try:
            expected_destination = resolve_handoff_route(*handoff)
        except ValueError as exc:
            error(f"{relative}:{number}: {exc}")
            continue
        if destination != expected_destination:
            error(
                f"{relative}:{number}: handoff {agent}/{status}/{request} must route "
                f"to {expected_destination!r}, not {destination!r}"
            )
    for handoff in sorted(LEGAL_HANDOFFS - set(rows)):
        error(f"{relative}: missing handoff route {'/'.join(handoff)}")


def validate_skill() -> None:
    relative = ".agents/skills/lean-dev-router/SKILL.md"
    skill = read(relative)
    if not skill.startswith("---\n") or "\n---\n" not in skill[4:]:
        error(f"{relative}: missing YAML-style frontmatter")
    for required in (
        "name: lean-dev-router",
        "N/A (batch coverage)",
        "integration_owner",
        "integration_baseline",
        "integration_paths_allow",
        "integration_acceptance",
        "python scripts/check_scope.py",
        "FAILURE: missing_dispatch",
        "PLAN_MANIFEST",
        "DISPATCH_WAVE",
        "EXPANSION_GATE",
        "does not continuously schedule",
        "Streaming and preregistered audit",
        "<component>:<revision>:<stage>",
        "all-component barrier",
        "reuse one uninvolved Terra",
        "long parent commands",
        "within 60 seconds",
        "first eligible slot release",
        "not an outbound result envelope",
        "worktree-sha256:<64 lowercase hex>",
        "CONTRACT_EFFECT: unchanged",
        "parent:repair_or_sol",
        "terra_planner",
        "directly replaces routine Sol planning",
        "LEVEL",
        "OBJECTIVE_FIXED",
        "SCOPE_ROOTS",
        "RISK_FLAGS",
        "EXTERNAL_ACTIONS",
        "MAX_DISPATCHES",
        "COMPONENT_COUNT",
        "DEPENDENCY_DEPTH",
        "required path outside",
        "more than one",
        "no routine Terra-to-Sol review",
        "PLAN_ID",
        "PLANNER_ROLE",
        "PLANNER_INSTANCE_ID",
        "AUDITOR_INSTANCE_ID",
        "immutable role lease",
        "planner authority and identity",
        "independent and read-only",
    ):
        if required not in skill:
            error(f"{relative}: missing required text {required!r}")

    validate_protocol_schema(relative, skill)
    validate_handoff_table(relative, skill)

    headings: list[tuple[int, str]] = []
    for number, line in markdown_lines(skill):
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading:
            headings.append((len(heading.group(1)), heading.group(2)))
        if re.match(r"^\s*(?:[-+*]|\d+\.)\s*$", line):
            error(f"{relative}:{number}: empty list item")
        if re.search(r"\s/\s*$", line):
            error(f"{relative}:{number}: unconsumed language separator")
    for previous, current in zip(headings, headings[1:]):
        if current[0] > previous[0] + 1:
            error(f"{relative}: heading level jumps from H{previous[0]} to H{current[0]}")
    expected_titles = {
        "Lean Dev Router",
        "Language",
        "Authority and entry",
        "Bounded planning waves",
        "Protocol",
        "Scope, artifacts, and revision",
        "Risk fuse and replay",
        "Streaming and preregistered audit",
        "Terra causal audit and repair",
        "Integration",
        "Execution and human gate",
    }
    actual_titles = {title for _, title in headings}
    for title in sorted(expected_titles - actual_titles):
        error(f"{relative}: missing heading {title!r}")
    for number, line in markdown_lines(skill):
        if line.strip() in expected_titles and not line.startswith("#"):
            error(f"{relative}:{number}: bare heading {line.strip()!r}")


def parse_manifest(text: str) -> dict[str, dict[str, str]]:
    """Parse the repository's intentionally small mapping-only YAML manifest."""
    result: dict[str, dict[str, str]] = {}
    section: str | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if "\t" in line:
            raise ValueError(f"line {number}: tabs are not allowed")
        top = re.fullmatch(r"([A-Za-z_][\w-]*):", line)
        if top:
            section = top.group(1)
            if section in result:
                raise ValueError(f"line {number}: duplicate section {section!r}")
            result[section] = {}
            continue
        item = re.fullmatch(r"  ([A-Za-z_][\w-]*):\s*(.+)", line)
        if item is None or section is None:
            raise ValueError(f"line {number}: unsupported YAML structure")
        key, raw_value = item.groups()
        if key in result[section]:
            raise ValueError(f"line {number}: duplicate key {key!r}")
        try:
            value = ast.literal_eval(raw_value)
        except (SyntaxError, ValueError) as exc:
            raise ValueError(f"line {number}: invalid quoted scalar") from exc
        if not isinstance(value, str):
            raise ValueError(f"line {number}: expected a string scalar")
        result[section][key] = value
    return result


def validate_manifest() -> None:
    relative = ".agents/skills/lean-dev-router/agents/openai.yaml"
    try:
        manifest = parse_manifest(read(relative))
    except (OSError, ValueError) as exc:
        error(f"{relative}: YAML parse failed: {exc}")
        return
    interface = manifest.get("interface", {})
    for key in ("display_name", "short_description", "default_prompt"):
        if not interface.get(key, "").strip():
            error(f"{relative}: interface.{key} is missing")
    if "$lean-dev-router" not in interface.get("default_prompt", ""):
        error(f"{relative}: default_prompt disagrees with the Skill name")


def validate_runtime_language() -> None:
    for root in (ROOT / ".agents", ROOT / "agents"):
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT).as_posix()
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if not line.isascii():
                    error(f"{relative}:{number}: non-ASCII text is not allowed in runtime files")


def validate_markdown() -> None:
    link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for path in ROOT.rglob("*.md"):
        if ".git" in path.parts or ".workbuddy" in path.parts:
            continue
        relative = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        fence: tuple[str, int, int, str, list[str]] | None = None
        for number, line in enumerate(text.splitlines(), start=1):
            marker = re.match(r"^\s*(```+|~~~+)(.*)$", line)
            if marker:
                opener = marker.group(1)
                token = opener[0]
                length = len(opener)
                if fence is None:
                    fence = (token, length, number, marker.group(2).strip().lower(), [])
                elif fence[0] == token and length >= fence[1]:
                    if fence[3] == "python":
                        try:
                            ast.parse("\n".join(fence[4]))
                        except SyntaxError as exc:
                            error(f"{relative}:{fence[2]}: invalid Python fence: {exc.msg}")
                    fence = None
                else:
                    fence[4].append(line)
            elif fence is not None:
                fence[4].append(line)
        if fence is not None:
            error(f"{relative}:{fence[2]}: unclosed Markdown code fence")
        for match in link_pattern.finditer(text):
            target = match.group(1).split(maxsplit=1)[0].strip("<>")
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            local = target.split("#", 1)[0]
            if local and not (path.parent / local).exists():
                error(f"{relative}: missing local link target {local!r}")


def validate_repository_contract() -> None:
    for path in LEGACY_PATHS:
        if (ROOT / path).exists():
            error(f"legacy runtime path still exists: {path.as_posix()}")
    legacy_tokens = tuple(path.as_posix() for path in LEGACY_PATHS)
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or ".workbuddy" in path.parts:
            continue
        if path.suffix.lower() not in {".md", ".py", ".toml", ".yaml", ".yml"}:
            continue
        text = path.read_text(encoding="utf-8")
        for token in legacy_tokens:
            if token in text:
                error(f"{path.relative_to(ROOT).as_posix()}: legacy reference {token!r}")
    required_text = {
        "README.md": ("docs/zh-CN/README.md", "scripts/check_scope.py"),
        "docs/zh-CN/README.md": (
            "仅供人类阅读",
            ".agents/skills/lean-dev-router/SKILL.md",
            "scripts/check_scope.py",
        ),
        "lean-dev-router-self-test-guide.md": (
            "integration_owner",
            "tracked/untracked scope evidence",
        ),
        "lean-dev-router-l3-idempotent-orders-task.md": (
            "threading.Barrier(3)",
            "join(timeout=5)",
        ),
    }
    for relative, snippets in required_text.items():
        try:
            text = read(relative)
        except OSError as exc:
            error(f"{relative}: cannot read required file: {exc}")
            continue
        for snippet in snippets:
            if snippet not in text:
                error(f"{relative}: missing contract text {snippet!r}")
    validate_license()


def validate_license() -> None:
    relative = "LICENSE"
    try:
        text = read(relative)
    except (OSError, UnicodeError) as exc:
        error(f"{relative}: cannot read required file: {exc}")
        return
    if not text.startswith("MIT License\n"):
        error(f"{relative}: expected MIT license text")


def main() -> int:
    validate_agents()
    validate_skill()
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
