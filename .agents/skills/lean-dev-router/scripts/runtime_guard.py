#!/usr/bin/env python3
"""Fail-closed runtime guard for lean-dev-router parent scheduling.

The guard is standard-library only so it travels with the installed Skill. It
validates child-spawn packets before a model is called, tracks finite stage
budgets, latches exhausted stages, and emits compact per-stage telemetry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping


DISPATCH_FIELDS = (
    "PROTOCOL",
    "STATUS",
    "TARGET",
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
    "BUDGET",
    "NEXT",
)
BUDGET_FIELDS = (
    "MODEL_CALL_LIMIT",
    "HYPOTHESIS_LIMIT",
    "MODEL_ACTIVE_SECONDS_LIMIT",
    "REPAIR_CYCLE_LIMIT",
    "STAGNANT_CALL_LIMIT",
)
REPAIR_FIELDS = (
    "PLAN_ID",
    "DISPATCH_ID",
    "AUDITOR_INSTANCE_ID",
    "CONTRACT_EFFECT",
    "AFFECTED_PATHS",
    "ACCEPTANCE",
    "REPAIR_CYCLE",
    "REVISION",
    "EVIDENCE_FINGERPRINT",
)
TOKEN_FIELDS = (
    "INPUT_TOKENS",
    "CACHED_INPUT_TOKENS",
    "CACHE_CREATION_INPUT_TOKENS",
    "OUTPUT_TOKENS",
    "REASONING_OUTPUT_TOKENS",
)
EVENT_FIELDS = (
    "PLAN_ID", "DISPATCH_ID", "REVISION", "ROLE", "AGENT_INSTANCE_ID", "STAGE",
    "CONTRACT_VERSION", "EVIDENCE_FINGERPRINT", "MODEL_CALLS",
    "MODEL_ACTIVE_SECONDS", "WALL_SECONDS", "UPSTREAM_ATTEMPTS", *TOKEN_FIELDS,
    "OUTCOME",
)
DEFAULT_BUDGET = {
    "MODEL_CALL_LIMIT": 8,
    "HYPOTHESIS_LIMIT": 4,
    "MODEL_ACTIVE_SECONDS_LIMIT": 1200,
    "REPAIR_CYCLE_LIMIT": 2,
    "STAGNANT_CALL_LIMIT": 2,
}
AUDIT_BEGIN_FIELDS = (
    "ACTION", "PLAN_ID", "DISPATCH_ID", "REVISION", "AUDITOR_INSTANCE_ID",
    "AUDIT_SCOPE", "AUDIT_MODE",
)
AUDIT_INCREMENTAL_FIELDS = ("PREVIOUS_REVISION", "UNRESOLVED_FINDINGS")
AUDIT_COMPLETE_FIELDS = (
    "ACTION", "PLAN_ID", "DISPATCH_ID", "REVISION", "AUDITOR_INSTANCE_ID",
    "TERMINATION_REASON", "VERIFIED", "UNVERIFIED",
)
WRITER_ROLE = "luna_worker"
ROLES = {"sol_planner", "luna_worker", "terra_auditor", "parent"}


def _value(data: Mapping[str, Any], key: str, default: Any = None) -> Any:
    folded = key.casefold()
    for candidate, value in data.items():
        if str(candidate).casefold() == folded:
            return value
    return default


def _present(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)
    return True


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    return None


def _nonnegative_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if number >= 0 and math.isfinite(number) else None


def _paths(value: Any, *, allow_empty: bool = False) -> list[str] | None:
    if not isinstance(value, list) or (not value and not allow_empty):
        return None
    result: list[str] = []
    for raw in value:
        if not isinstance(raw, str) or not raw.strip():
            return None
        path = raw.replace("\\", "/").strip()
        if path == ".":
            result.append(path)
            continue
        parts = path.split("/")
        if path.startswith("/") or (len(path) > 1 and path[1] == ":"):
            return None
        if any(part in {"", ".", ".."} for part in parts):
            return None
        result.append(path)
    return result


def _inside(path: str, roots: list[str]) -> bool:
    return any(
        root == "." or path == root or path.startswith(root.rstrip("/") + "/")
        for root in roots
    )


def fingerprint(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_budget(value: Any) -> list[str]:
    if not isinstance(value, Mapping):
        return ["BUDGET must be an object"]
    errors: list[str] = []
    for field_name in BUDGET_FIELDS:
        actual = _positive_int(_value(value, field_name))
        if actual is None:
            errors.append(f"BUDGET.{field_name} must be a positive integer")
        elif actual > DEFAULT_BUDGET[field_name]:
            errors.append(f"BUDGET.{field_name} exceeds the runtime ceiling")
    return errors


def validate_dispatch(packet: Mapping[str, Any]) -> list[str]:
    """Validate a complete packet before parent spawns Luna."""
    errors = [f"{name} must be non-empty" for name in DISPATCH_FIELDS if not _present(_value(packet, name))]
    expected = {
        "PROTOCOL": "lean-dev-router/v2",
        "STATUS": "DISPATCH",
        "TARGET": "implementation",
        "NEXT": "parent",
    }
    for name, value in expected.items():
        if _value(packet, name) != value:
            errors.append(f"{name} must equal {value}")
    if _value(packet, "PLANNER_ROLE") != "sol_planner":
        errors.append("PLANNER_ROLE must equal sol_planner")
    if _value(packet, "PLANNER_INSTANCE_ID") == _value(packet, "AUDITOR_INSTANCE_ID"):
        errors.append("AUDITOR_INSTANCE_ID must differ from PLANNER_INSTANCE_ID")
    if _paths(_value(packet, "PATHS_ALLOW")) is None:
        errors.append("PATHS_ALLOW must be non-empty repository-relative paths")
    errors.extend(validate_budget(_value(packet, "BUDGET")))
    return list(dict.fromkeys(errors))


def validate_repair(packet: Mapping[str, Any], dispatch: Mapping[str, Any]) -> list[str]:
    """Validate a contract-preserving repair before Luna is resumed."""
    errors = [f"{name} must be non-empty" for name in REPAIR_FIELDS if not _present(_value(packet, name))]
    for name in ("PLAN_ID", "DISPATCH_ID", "ACCEPTANCE"):
        if _value(packet, name) != _value(dispatch, name):
            errors.append(f"{name} must match the original dispatch")
    if _value(packet, "AUDITOR_INSTANCE_ID") != _value(dispatch, "AUDITOR_INSTANCE_ID"):
        errors.append("AUDITOR_INSTANCE_ID must match the preregistered auditor")
    if _value(packet, "CONTRACT_EFFECT") != "unchanged":
        errors.append("CONTRACT_EFFECT must equal unchanged")
    allowed = _paths(_value(dispatch, "PATHS_ALLOW")) or []
    affected = _paths(_value(packet, "AFFECTED_PATHS"))
    if affected is None or any(not _inside(path, allowed) for path in affected):
        errors.append("AFFECTED_PATHS must stay inside PATHS_ALLOW")
    cycle = _positive_int(_value(packet, "REPAIR_CYCLE"))
    limit = _positive_int(_value(_value(dispatch, "BUDGET", {}), "REPAIR_CYCLE_LIMIT"))
    if cycle is None or limit is None or cycle > limit:
        errors.append("REPAIR_CYCLE exceeds the dispatch budget")
    return list(dict.fromkeys(errors))


@dataclass
class StageTelemetry:
    plan_id: str
    dispatch_id: str
    revision: str
    role: str
    agent_instance_id: str
    stage: str
    contract_version: str = ""
    evidence_fingerprint: str = ""
    model_calls: int = 0
    model_active_seconds: float = 0
    wall_seconds: float = 0
    upstream_attempts: int = 0
    input_tokens: int = 0
    cached_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_output_tokens: int = 0
    hypotheses: list[str] = field(default_factory=list)
    stagnant_calls: int = 0
    last_progress_fingerprint: str = ""
    attempted_failures: list[str] = field(default_factory=list)
    termination_reason: str = "running"

    @property
    def uncached_input_tokens(self) -> int:
        return self.input_tokens - self.cached_input_tokens

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def public(self) -> dict[str, Any]:
        result = asdict(self)
        result["uncached_input_tokens"] = self.uncached_input_tokens
        result["total_tokens"] = self.total_tokens
        return result


class RuntimeGuard:
    """Deterministic parent state for one dispatch lifecycle."""

    def __init__(self, dispatch: Mapping[str, Any]) -> None:
        errors = validate_dispatch(dispatch)
        if errors:
            raise ValueError("; ".join(errors))
        self.dispatch = dict(dispatch)
        self.stages: dict[str, StageTelemetry] = {}
        self.latches: dict[str, dict[str, str]] = {}
        self.role_leases: dict[str, str] = {
            str(_value(dispatch, "PLANNER_INSTANCE_ID")): str(_value(dispatch, "PLANNER_ROLE")),
            str(_value(dispatch, "AUDITOR_INSTANCE_ID")): "terra_auditor",
        }
        self.audit_jobs: dict[str, dict[str, str]] = {}
        self.last_completed_audits: dict[str, str] = {}
        self.repair_cycles: dict[str, int] = {}
        self.repair_evidence: dict[str, list[str]] = {}

    def _key(self, event: Mapping[str, Any]) -> str:
        fields = (
            "PLAN_ID", "DISPATCH_ID", "REVISION", "ROLE", "AGENT_INSTANCE_ID",
            "STAGE", "CONTRACT_VERSION", "EVIDENCE_FINGERPRINT",
        )
        values = [str(_value(event, name, "")).strip() for name in fields]
        if not all(values[:6]):
            raise ValueError("event identity fields must be non-empty")
        if values[0] != str(_value(self.dispatch, "PLAN_ID")) or values[1] != str(_value(self.dispatch, "DISPATCH_ID")):
            raise ValueError("event identity does not match dispatch")
        return ":".join(values)

    def _lease_role(self, event: Mapping[str, Any], *, record: bool) -> None:
        role = str(_value(event, "ROLE", "")).strip()
        instance = str(_value(event, "AGENT_INSTANCE_ID", "")).strip()
        if role not in ROLES or not instance:
            raise ValueError("event role and agent identity must be valid")
        leased = self.role_leases.get(instance)
        if leased is not None and leased != role:
            raise ValueError("AGENT_INSTANCE_ID cannot change role within PLAN_ID")
        if record:
            self.role_leases[instance] = role

    def _limits(self) -> Mapping[str, Any]:
        return _value(self.dispatch, "BUDGET", {})

    def can_resume(self, event: Mapping[str, Any]) -> bool:
        latch_key = ":".join(str(_value(event, name, "")) for name in ("PLAN_ID", "DISPATCH_ID", "ROLE", "STAGE"))
        latch = self.latches.get(latch_key)
        if latch is None:
            return True
        return any(
            str(_value(event, field, "")) != latch.get(field, "")
            for field in ("REVISION", "CONTRACT_VERSION", "EVIDENCE_FINGERPRINT")
        )

    def observe(self, event: Mapping[str, Any]) -> dict[str, Any]:
        """Record one completed model call and return a mechanical route decision."""
        if _value(event, "ACTION") == "write" and _value(event, "ROLE") != WRITER_ROLE:
            return self._decision(False, "unauthorized_writer", "parent:pause")
        telemetry_fields = EVENT_FIELDS[8:]
        event_keys = {str(name).casefold() for name in event}
        if any(name.casefold() not in event_keys for name in EVENT_FIELDS) or any(
            _value(event, name) is None for name in telemetry_fields
        ):
            return self._decision(False, "incomplete_telemetry", "parent:pause")
        if not self.can_resume(event):
            latch_key = ":".join(str(_value(event, name, "")) for name in ("PLAN_ID", "DISPATCH_ID", "ROLE", "STAGE"))
            terminal = self.latches.get(latch_key, {}).get("TERMINATION_REASON")
            if terminal == "pass":
                return self._decision(False, "duplicate_terminal_stage", "parent:manifest_gate")
            return self._decision(False, "escalation_latch", self._destination(str(_value(event, "ROLE"))))
        self._lease_role(event, record=False)
        key = self._key(event)
        stage = self.stages.get(key)
        if stage is None:
            stage = StageTelemetry(
                plan_id=str(_value(event, "PLAN_ID")),
                dispatch_id=str(_value(event, "DISPATCH_ID")),
                revision=str(_value(event, "REVISION")),
                role=str(_value(event, "ROLE")),
                agent_instance_id=str(_value(event, "AGENT_INSTANCE_ID")),
                stage=str(_value(event, "STAGE")),
                contract_version=str(_value(event, "CONTRACT_VERSION", "")),
                evidence_fingerprint=str(_value(event, "EVIDENCE_FINGERPRINT", "")),
            )

        calls = _positive_int(_value(event, "MODEL_CALLS"))
        active = _nonnegative_number(_value(event, "MODEL_ACTIVE_SECONDS"))
        wall = _nonnegative_number(_value(event, "WALL_SECONDS"))
        upstream = _value(event, "UPSTREAM_ATTEMPTS")
        if (
            calls is None
            or active is None
            or wall is None
            or not isinstance(upstream, int)
            or isinstance(upstream, bool)
            or upstream < 0
            or (wall and active > wall)
        ):
            return self._decision(False, "invalid_event", "parent:pause")
        token_values: dict[str, int] = {}
        for token_name in TOKEN_FIELDS:
            value = _value(event, token_name, 0)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                return self._decision(False, "invalid_event", "parent:pause")
            token_values[token_name] = value
        if token_values["CACHED_INPUT_TOKENS"] > token_values["INPUT_TOKENS"]:
            return self._decision(False, "invalid_event", "parent:pause")
        if token_values["REASONING_OUTPUT_TOKENS"] > token_values["OUTPUT_TOKENS"]:
            return self._decision(False, "invalid_event", "parent:pause")

        self._lease_role(event, record=True)
        self.stages.setdefault(key, stage)
        stage.model_calls += calls
        stage.model_active_seconds += active
        stage.wall_seconds += wall
        stage.upstream_attempts += upstream
        for token_name, value in token_values.items():
            attr = token_name.casefold()
            setattr(stage, attr, getattr(stage, attr) + value)

        hypothesis = str(_value(event, "HYPOTHESIS", "")).strip()
        if hypothesis and hypothesis not in stage.hypotheses:
            stage.hypotheses.append(hypothesis)
        progress = str(_value(event, "PROGRESS_FINGERPRINT", "")).strip()
        progress_changed = bool(progress and progress != stage.last_progress_fingerprint)
        if progress_changed:
            stage.last_progress_fingerprint = progress
            stage.stagnant_calls = 0
        else:
            stage.stagnant_calls += calls

        error_signature = str(_value(event, "ERROR_SIGNATURE", "")).strip()
        command_fingerprint = str(_value(event, "COMMAND_FINGERPRINT", "")).strip()
        failure = f"{hypothesis}|{error_signature}|{command_fingerprint}"
        if error_signature and failure in stage.attempted_failures and not progress_changed:
            return self._trip(event, stage, "repeated_failure_without_new_evidence")
        if error_signature:
            stage.attempted_failures.append(failure)

        limits = self._limits()
        checks = (
            (stage.model_calls, "MODEL_CALL_LIMIT", "model_call_limit"),
            (len(stage.hypotheses), "HYPOTHESIS_LIMIT", "hypothesis_limit"),
            (stage.model_active_seconds, "MODEL_ACTIVE_SECONDS_LIMIT", "model_active_time_limit"),
            (stage.stagnant_calls, "STAGNANT_CALL_LIMIT", "spinning"),
        )
        for actual, limit_name, reason in checks:
            limit = int(_value(limits, limit_name))
            if actual > limit:
                return self._trip(event, stage, reason)
        outcome = str(_value(event, "OUTCOME", "running")).casefold()
        if outcome not in {"running", "pass", "blocked", "escalate"}:
            return self._decision(False, "invalid_event", "parent:pause", stage)
        if outcome == "pass":
            if error_signature:
                return self._decision(False, "invalid_event", "parent:pause", stage)
            stage.termination_reason = "pass"
            self._latch(event, "pass")
            return self._decision(True, "stage_complete", "parent:manifest_gate", stage)
        if outcome in {"blocked", "escalate"}:
            stage.termination_reason = outcome
            self._latch(event, outcome)
            destination = "parent:pause" if outcome == "blocked" else self._destination(stage.role)
            return self._decision(False, outcome, destination, stage)
        for actual, limit_name, reason in checks:
            limit = int(_value(limits, limit_name))
            if actual >= limit:
                return self._trip(event, stage, reason)
        return self._decision(True, "continue", "parent:continue", stage)

    def begin_audit(self, packet: Mapping[str, Any]) -> dict[str, Any]:
        """Register an audit job once per dispatch revision."""
        required = AUDIT_BEGIN_FIELDS[1:]
        if any(not _present(_value(packet, name)) for name in required):
            return self._decision(False, "invalid_audit_job", "parent:pause")
        if _value(packet, "PLAN_ID") != _value(self.dispatch, "PLAN_ID") or _value(
            packet, "DISPATCH_ID"
        ) != _value(self.dispatch, "DISPATCH_ID"):
            return self._decision(False, "invalid_audit_job", "parent:pause")
        auditor = str(_value(packet, "AUDITOR_INSTANCE_ID"))
        if auditor != str(_value(self.dispatch, "AUDITOR_INSTANCE_ID")):
            return self._decision(False, "invalid_auditor_identity", "parent:pause")
        job_key = ":".join(
            str(_value(packet, name)) for name in ("PLAN_ID", "DISPATCH_ID", "REVISION", "AUDITOR_INSTANCE_ID")
        )
        if job_key in self.audit_jobs:
            return self._decision(False, "duplicate_audit_revision", "parent:manifest_gate")
        if any(job.get("status") == "running" for job in self.audit_jobs.values()):
            return self._decision(False, "audit_already_running", "parent:pause")
        dispatch_key = f"{_value(packet, 'PLAN_ID')}:{_value(packet, 'DISPATCH_ID')}"
        previous = self.last_completed_audits.get(dispatch_key, "")
        mode = str(_value(packet, "AUDIT_MODE", "")).casefold()
        if not previous and mode != "full":
            return self._decision(False, "initial_audit_must_be_full", "parent:pause")
        if previous:
            unresolved = _value(packet, "UNRESOLVED_FINDINGS")
            if (
                mode != "incremental"
                or str(_value(packet, "PREVIOUS_REVISION", "")) != previous
                or not isinstance(unresolved, list)
            ):
                return self._decision(False, "invalid_incremental_audit", "parent:pause")
        self.audit_jobs[job_key] = {"status": "running", "mode": mode}
        return self._decision(True, "audit_registered", "parent:terra")

    def complete_audit(self, packet: Mapping[str, Any]) -> dict[str, Any]:
        required = AUDIT_COMPLETE_FIELDS[1:]
        if any(not _present(_value(packet, name)) for name in required[:-2]):
            return self._decision(False, "invalid_audit_completion", "parent:pause")
        if not isinstance(_value(packet, "VERIFIED"), list) or not isinstance(
            _value(packet, "UNVERIFIED"), list
        ):
            return self._decision(False, "invalid_audit_completion", "parent:pause")
        if (
            _value(packet, "PLAN_ID") != _value(self.dispatch, "PLAN_ID")
            or _value(packet, "DISPATCH_ID") != _value(self.dispatch, "DISPATCH_ID")
            or _value(packet, "AUDITOR_INSTANCE_ID") != _value(self.dispatch, "AUDITOR_INSTANCE_ID")
        ):
            return self._decision(False, "invalid_audit_completion", "parent:pause")
        job_key = ":".join(
            str(_value(packet, name)) for name in ("PLAN_ID", "DISPATCH_ID", "REVISION", "AUDITOR_INSTANCE_ID")
        )
        job = self.audit_jobs.get(job_key)
        if not job or job.get("status") != "running":
            return self._decision(False, "audit_job_not_running", "parent:pause")
        job["status"] = "complete"
        job["termination_reason"] = str(_value(packet, "TERMINATION_REASON"))
        dispatch_key = f"{_value(packet, 'PLAN_ID')}:{_value(packet, 'DISPATCH_ID')}"
        self.last_completed_audits[dispatch_key] = str(_value(packet, "REVISION"))
        return self._decision(True, "audit_completed", "parent:manifest_gate")

    def audit_job(self, packet: Mapping[str, Any]) -> dict[str, Any]:
        action = str(_value(packet, "ACTION", "begin")).casefold()
        if action == "begin":
            return self.begin_audit(packet)
        if action == "complete":
            return self.complete_audit(packet)
        return self._decision(False, "invalid_audit_action", "parent:pause")

    def register_repair(self, packet: Mapping[str, Any]) -> dict[str, Any]:
        errors = validate_repair(packet, self.dispatch)
        if errors:
            return {"allowed": False, "reason": "invalid_repair", "destination": "parent:sol", "errors": errors}
        key = f"{_value(packet, 'PLAN_ID')}:{_value(packet, 'DISPATCH_ID')}"
        cycle = int(_value(packet, "REPAIR_CYCLE"))
        previous = self.repair_cycles.get(key, 0)
        if cycle != previous + 1:
            return self._decision(False, "non_sequential_repair_cycle", "parent:sol")
        evidence = str(_value(packet, "EVIDENCE_FINGERPRINT"))
        seen = self.repair_evidence.setdefault(key, [])
        if evidence in seen:
            return self._decision(False, "repeated_repair_without_new_evidence", "parent:sol")
        self.repair_cycles[key] = cycle
        seen.append(evidence)
        return self._decision(True, "repair_valid", "parent:luna")

    def _destination(self, role: str) -> str:
        if role == "luna_worker":
            return "parent:terra"
        if role == "terra_auditor":
            return "parent:sol"
        return "parent:pause"

    def _trip(self, event: Mapping[str, Any], stage: StageTelemetry, reason: str) -> dict[str, Any]:
        stage.termination_reason = reason
        self._latch(event, reason)
        return self._decision(False, reason, self._destination(stage.role), stage)

    def _latch(self, event: Mapping[str, Any], reason: str) -> None:
        latch_key = ":".join(str(_value(event, name, "")) for name in ("PLAN_ID", "DISPATCH_ID", "ROLE", "STAGE"))
        self.latches[latch_key] = {
            field: str(_value(event, field, ""))
            for field in ("REVISION", "CONTRACT_VERSION", "EVIDENCE_FINGERPRINT")
        }
        self.latches[latch_key]["TERMINATION_REASON"] = reason

    def _decision(
        self, allowed: bool, reason: str, destination: str, stage: StageTelemetry | None = None
    ) -> dict[str, Any]:
        result: dict[str, Any] = {"allowed": allowed, "reason": reason, "destination": destination}
        if stage is not None:
            result["telemetry"] = stage.public()
        return result

    def snapshot(self) -> dict[str, Any]:
        return {
            "dispatch": self.dispatch,
            "stages": {key: value.public() for key, value in self.stages.items()},
            "latches": self.latches,
            "role_leases": self.role_leases,
            "audit_jobs": self.audit_jobs,
            "last_completed_audits": self.last_completed_audits,
            "repair_cycles": self.repair_cycles,
            "repair_evidence": self.repair_evidence,
        }

    @classmethod
    def from_snapshot(cls, data: Mapping[str, Any]) -> "RuntimeGuard":
        guard = cls(_value(data, "dispatch", {}))
        for key, raw in _value(data, "stages", {}).items():
            values = dict(raw)
            values.pop("uncached_input_tokens", None)
            values.pop("total_tokens", None)
            guard.stages[key] = StageTelemetry(**values)
        guard.latches = dict(_value(data, "latches", {}))
        guard.role_leases = dict(_value(data, "role_leases", guard.role_leases))
        guard.audit_jobs = dict(_value(data, "audit_jobs", {}))
        guard.last_completed_audits = dict(_value(data, "last_completed_audits", {}))
        guard.repair_cycles = {
            str(key): int(value) for key, value in _value(data, "repair_cycles", {}).items()
        }
        guard.repair_evidence = {
            str(key): list(value) for key, value in _value(data, "repair_evidence", {}).items()
        }
        return guard


def _stdin_json() -> Mapping[str, Any]:
    value = json.load(sys.stdin)
    if not isinstance(value, Mapping):
        raise ValueError("stdin JSON must be an object")
    return value


def _load(path: Path) -> RuntimeGuard:
    return RuntimeGuard.from_snapshot(json.loads(path.read_text(encoding="utf-8")))


def _save(path: Path, guard: RuntimeGuard) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(guard.snapshot(), ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start", help="validate dispatch and initialize state")
    start.add_argument("--state", type=Path, required=True)
    event = sub.add_parser("event", help="record one model-call event")
    event.add_argument("--state", type=Path, required=True)
    repair = sub.add_parser("repair", help="validate repair packet against dispatch")
    repair.add_argument("--state", type=Path, required=True)
    audit = sub.add_parser("audit", help="register one audit per revision")
    audit.add_argument("--state", type=Path, required=True)
    show = sub.add_parser("snapshot", help="print compact telemetry")
    show.add_argument("--state", type=Path, required=True)
    sub.add_parser("schema", help="print required JSON fields and default ceilings")
    args = parser.parse_args()
    try:
        if args.command == "schema":
            result = {
                "dispatch_fields": DISPATCH_FIELDS,
                "budget_fields": BUDGET_FIELDS,
                "default_budget": DEFAULT_BUDGET,
                "event_fields": EVENT_FIELDS,
                "repair_fields": REPAIR_FIELDS,
                "audit_begin_fields": AUDIT_BEGIN_FIELDS,
                "audit_incremental_fields": AUDIT_INCREMENTAL_FIELDS,
                "audit_complete_fields": AUDIT_COMPLETE_FIELDS,
            }
        elif args.command == "start":
            if args.state.exists():
                result = {
                    "allowed": False,
                    "reason": "state_already_exists",
                    "destination": "parent:pause",
                }
                print(json.dumps(result, ensure_ascii=False, sort_keys=True))
                return 2
            guard = RuntimeGuard(_stdin_json())
            _save(args.state, guard)
            result = {"allowed": True, "reason": "dispatch_valid", "destination": "parent:luna"}
        elif args.command == "event":
            guard = _load(args.state)
            result = guard.observe(_stdin_json())
            _save(args.state, guard)
        elif args.command == "repair":
            guard = _load(args.state)
            result = guard.register_repair(_stdin_json())
            _save(args.state, guard)
        elif args.command == "audit":
            guard = _load(args.state)
            result = guard.audit_job(_stdin_json())
            _save(args.state, guard)
        else:
            result = _load(args.state).snapshot()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result.get("allowed", True) else 2
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"allowed": False, "reason": "invalid_input", "errors": [str(exc)]}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
