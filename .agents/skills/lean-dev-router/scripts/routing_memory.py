#!/usr/bin/env python3
"""Bounded execution-grounded memory for advisory LDR routing decisions."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping


PROTOCOL = "lean-dev-router/routing-memory/v1"
DEFAULT_CAPACITY = 2000
DEFAULT_NEIGHBORS = 20
DEFAULT_MIN_SAMPLES = 3
MAX_CAPACITY = 20000
MAX_NEIGHBORS = 100
MAX_PACKET_BYTES = 65536
MAX_ENTRY_BYTES = 8192
MAX_TAGS = 16
MAX_ACTIONS = 16
OUTCOMES = {"pass", "blocked", "escalate", "failed"}
CONTEXT_FIELDS = (
    "TASK_ID",
    "DIMENSION",
    "LANGUAGE",
    "LEVEL",
    "TAGS",
    "POLICY_VERSION",
    "ELIGIBLE_ACTIONS",
    "DEFAULT_ACTION",
    "PERFORMANCE_WEIGHT",
    "COST_WEIGHT",
    "COST_SCALE_USD",
)
FEEDBACK_FIELDS = (
    "DECISION_ID",
    "ACTION",
    "OUTCOME",
    "VERIFIED",
    "SCORE",
    "COST_USD",
    "TOTAL_TOKENS",
    "MODEL_ACTIVE_SECONDS",
    "EVIDENCE_FINGERPRINT",
)


def _value(data: Mapping[str, Any], key: str, default: Any = None) -> Any:
    folded = key.casefold()
    for candidate, value in data.items():
        if str(candidate).casefold() == folded:
            return value
    return default


def _reject_conflicting_keys(data: Mapping[str, Any], path: str = "$") -> None:
    seen: set[str] = set()
    for key, value in data.items():
        folded = str(key).casefold()
        if folded in seen:
            raise ValueError(f"conflicting case-insensitive field: {path}.{key}")
        seen.add(folded)
        if isinstance(value, Mapping):
            _reject_conflicting_keys(value, f"{path}.{key}")


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    seen: set[str] = set()
    for key, item in pairs:
        folded = key.casefold()
        if folded in seen:
            raise ValueError(f"conflicting case-insensitive field: {key}")
        seen.add(folded)
        value[key] = item
    return value


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any, *, positive: bool = False) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    if not math.isfinite(result) or result < 0 or (positive and result <= 0):
        return None
    return result


def _integer(value: Any, *, positive: bool = False) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0 or (positive and value <= 0):
        return None
    return value


def _string_list(value: Any, *, allow_empty: bool = False) -> list[str] | None:
    if not isinstance(value, list) or (not value and not allow_empty):
        return None
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _text(item)
        folded = text.casefold()
        if not text or folded in seen:
            return None
        seen.add(folded)
        result.append(text)
    return result


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _lower_hex(value: str, length: int) -> bool:
    return len(value) == length and all(character in "0123456789abcdef" for character in value)


def empty_memory(capacity: int = DEFAULT_CAPACITY) -> dict[str, Any]:
    return {
        "protocol": PROTOCOL,
        "capacity": capacity,
        "next_sequence": 1,
        "decisions": [],
    }


def validate_context(packet: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for name in CONTEXT_FIELDS:
        if not any(str(key).casefold() == name.casefold() for key in packet):
            errors.append(f"{name} must be explicit")
    limits = {"TASK_ID": 128, "DIMENSION": 64, "LANGUAGE": 32, "LEVEL": 2, "POLICY_VERSION": 64}
    for name, limit in limits.items():
        text = _text(_value(packet, name))
        if not text or len(text) > limit:
            errors.append(f"{name} must be non-empty")
    if _text(_value(packet, "LEVEL")).upper() not in {"L1", "L2", "L3"}:
        errors.append("LEVEL must be L1, L2, or L3")
    tags = _string_list(_value(packet, "TAGS"), allow_empty=True)
    if tags is None or len(tags) > MAX_TAGS or any(len(tag) > 64 for tag in tags):
        errors.append("TAGS must be a unique string array")
    actions = _string_list(_value(packet, "ELIGIBLE_ACTIONS"))
    if actions is None or len(actions) > MAX_ACTIONS or any(len(action) > 128 for action in actions):
        errors.append("ELIGIBLE_ACTIONS must be a non-empty unique string array")
    elif _text(_value(packet, "DEFAULT_ACTION")).casefold() not in {
        action.casefold() for action in actions
    }:
        errors.append("DEFAULT_ACTION must be in ELIGIBLE_ACTIONS")
    for name in ("PERFORMANCE_WEIGHT", "COST_WEIGHT"):
        if _number(_value(packet, name)) is None:
            errors.append(f"{name} must be a finite non-negative number")
    if _number(_value(packet, "COST_SCALE_USD"), positive=True) is None:
        errors.append("COST_SCALE_USD must be a finite positive number")
    return list(dict.fromkeys(errors))


def _context(packet: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task_id": _text(_value(packet, "TASK_ID")),
        "dimension": _text(_value(packet, "DIMENSION")).casefold(),
        "language": _text(_value(packet, "LANGUAGE")).casefold(),
        "level": _text(_value(packet, "LEVEL")).upper(),
        "tags": sorted(tag.casefold() for tag in (_string_list(_value(packet, "TAGS"), allow_empty=True) or [])),
        "policy_version": _text(_value(packet, "POLICY_VERSION")),
    }


def validate_memory(memory: Mapping[str, Any]) -> None:
    if _value(memory, "protocol") != PROTOCOL:
        raise ValueError(f"memory protocol must equal {PROTOCOL}")
    capacity = _integer(_value(memory, "capacity"), positive=True)
    sequence = _integer(_value(memory, "next_sequence"), positive=True)
    decisions = _value(memory, "decisions")
    if (
        capacity is None
        or capacity > MAX_CAPACITY
        or sequence is None
        or not isinstance(decisions, list)
    ):
        raise ValueError("memory header is invalid")
    if len(decisions) > capacity:
        raise ValueError("memory exceeds capacity")
    seen: set[str] = set()
    previous_sequence = 0
    for item in decisions:
        if not isinstance(item, Mapping):
            raise ValueError("memory decision must be an object")
        decision_id = _text(_value(item, "decision_id"))
        item_sequence = _integer(_value(item, "sequence"), positive=True)
        status = _text(_value(item, "status"))
        if (
            not decision_id.startswith("route-sha256:")
            or not _lower_hex(decision_id[len("route-sha256:"):], 64)
            or decision_id in seen
            or item_sequence is None
        ):
            raise ValueError("memory decision identity is invalid")
        if item_sequence <= previous_sequence or status not in {"pending", "completed"}:
            raise ValueError("memory decision order or status is invalid")
        context = _value(item, "context")
        actions = _string_list(_value(item, "eligible_actions"))
        action = _text(_value(item, "action"))
        default = _text(_value(item, "default_action"))
        if not isinstance(context, Mapping) or actions is None:
            raise ValueError("memory decision context or eligibility is invalid")
        context_limits = {"task_id": 128, "dimension": 64, "language": 32, "level": 2, "policy_version": 64}
        if any(
            not _text(context.get(name)) or len(_text(context.get(name))) > limit
            for name, limit in context_limits.items()
        ):
            raise ValueError("memory decision context is incomplete")
        tags = _string_list(context.get("tags"), allow_empty=True)
        if tags is None or len(tags) > MAX_TAGS or any(len(tag) > 64 for tag in tags):
            raise ValueError("memory decision tags are invalid")
        if len(actions) > MAX_ACTIONS or any(len(candidate) > 128 for candidate in actions):
            raise ValueError("memory decision eligibility is invalid")
        eligible = {candidate.casefold() for candidate in actions}
        if action.casefold() not in eligible or default.casefold() not in eligible:
            raise ValueError("memory decision exceeds recorded eligibility")
        selector = _value(item, "selector")
        stats = _value(item, "stats")
        if not isinstance(selector, Mapping) or not isinstance(stats, Mapping):
            raise ValueError("memory decision selector evidence is missing")
        selector_neighbors = _integer(_value(selector, "neighbors"), positive=True)
        selector_minimum = _integer(_value(selector, "min_samples"), positive=True)
        if (
            selector_neighbors is None
            or selector_neighbors > MAX_NEIGHBORS
            or selector_minimum is None
            or selector_minimum > selector_neighbors
            or _number(_value(selector, "performance_weight")) is None
            or _number(_value(selector, "cost_weight")) is None
            or _number(_value(selector, "cost_scale_usd"), positive=True) is None
        ):
            raise ValueError("memory decision selector is invalid")
        if {str(key).casefold() for key in stats} != eligible:
            raise ValueError("memory decision statistics do not match eligibility")
        if any(not isinstance(value, Mapping) for value in stats.values()):
            raise ValueError("memory decision statistics are invalid")
        memory_revision = _text(_value(item, "memory_revision"))
        if not _lower_hex(memory_revision, 64):
            raise ValueError("memory decision revision is invalid")
        if status == "completed":
            _validate_completed(item)
        if len(_canonical(item).encode("utf-8")) > MAX_ENTRY_BYTES:
            raise ValueError("memory decision exceeds the per-entry size bound")
        seen.add(decision_id)
        previous_sequence = item_sequence
    if previous_sequence >= sequence:
        raise ValueError("memory next_sequence must follow all decisions")


def _validate_completed(item: Mapping[str, Any]) -> None:
    if _value(item, "verified") is not True:
        raise ValueError("completed feedback must be verified")
    if _text(_value(item, "outcome")).casefold() not in OUTCOMES:
        raise ValueError("completed feedback outcome is invalid")
    if _number(_value(item, "score")) is None or float(_value(item, "score")) > 1:
        raise ValueError("completed feedback score is invalid")
    for name in ("cost_usd", "model_active_seconds"):
        if _number(_value(item, name)) is None:
            raise ValueError(f"completed feedback {name} is invalid")
    if _integer(_value(item, "total_tokens")) is None:
        raise ValueError("completed feedback total_tokens is invalid")
    evidence = _text(_value(item, "evidence_fingerprint"))
    if not evidence or len(evidence) > 256:
        raise ValueError("completed feedback evidence is required")


def load_memory(path: Path, capacity: int = DEFAULT_CAPACITY) -> dict[str, Any]:
    if not path.exists():
        return empty_memory(capacity)
    if path.stat().st_size > MAX_ENTRY_BYTES * capacity + MAX_PACKET_BYTES:
        raise ValueError("memory file exceeds the configured size bound")
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_json_object)
    if not isinstance(value, Mapping):
        raise ValueError("memory JSON must be an object")
    _reject_conflicting_keys(value)
    validate_memory(value)
    if _value(value, "capacity") != capacity:
        raise ValueError("configured capacity does not match existing memory")
    return dict(value)


def save_memory(path: Path, memory: Mapping[str, Any]) -> None:
    validate_memory(memory)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(_canonical(memory), encoding="utf-8")
    temporary.replace(path)


def _similarity(left: Mapping[str, Any], right: Mapping[str, Any]) -> float:
    if left["dimension"] != right["dimension"]:
        return 0.0
    score = 4.0
    if left["level"] == right["level"]:
        score += 2.0
    if left["language"] == right["language"]:
        score += 1.0
    left_tags = set(left["tags"])
    right_tags = set(right["tags"])
    union = left_tags | right_tags
    if union:
        score += 3.0 * len(left_tags & right_tags) / len(union)
    return score


def _action_stats(
    memory: Mapping[str, Any], context: Mapping[str, Any], action: str, *,
    neighbors: int, min_samples: int, performance_weight: float,
    cost_weight: float, cost_scale_usd: float,
) -> dict[str, Any]:
    candidates: list[tuple[float, int, Mapping[str, Any]]] = []
    for item in _value(memory, "decisions", []):
        if _value(item, "status") != "completed" or _text(_value(item, "action")).casefold() != action.casefold():
            continue
        item_context = _value(item, "context", {})
        if not isinstance(item_context, Mapping) or item_context.get("policy_version") != context["policy_version"]:
            continue
        similarity = _similarity(context, item_context)
        if similarity > 0:
            candidates.append((similarity, int(_value(item, "sequence")), item))
    candidates.sort(key=lambda value: (value[0], value[1]), reverse=True)
    selected = [item for _, _, item in candidates[:neighbors]]
    utilities: list[float] = []
    scores: list[float] = []
    costs: list[float] = []
    passes = 0
    for item in selected:
        passed = _text(_value(item, "outcome")).casefold() == "pass"
        effective_score = float(_value(item, "score")) if passed else 0.0
        cost = float(_value(item, "cost_usd"))
        utilities.append(performance_weight * effective_score - cost_weight * (cost / cost_scale_usd))
        scores.append(effective_score)
        costs.append(cost)
        passes += int(passed)
    samples = len(selected)
    mean_utility = sum(utilities) / samples if samples else None
    lower_bound = mean_utility - (0.1 / math.sqrt(samples)) if samples else None
    return {
        "samples": samples,
        "supported": samples >= min_samples,
        "pass_rate": round(passes / samples, 6) if samples else None,
        "mean_score": round(sum(scores) / samples, 6) if samples else None,
        "mean_cost_usd": round(sum(costs) / samples, 6) if samples else None,
        "mean_utility": round(mean_utility, 6) if mean_utility is not None else None,
        "lower_bound": round(lower_bound, 6) if lower_bound is not None else None,
    }


def decide(
    memory: dict[str, Any], packet: Mapping[str, Any], *,
    neighbors: int = DEFAULT_NEIGHBORS, min_samples: int = DEFAULT_MIN_SAMPLES,
) -> dict[str, Any]:
    errors = validate_context(packet)
    if errors:
        return {"allowed": False, "reason": "invalid_context", "errors": errors}
    if (
        _integer(neighbors, positive=True) is None
        or neighbors > MAX_NEIGHBORS
        or _integer(min_samples, positive=True) is None
        or min_samples > neighbors
    ):
        return {"allowed": False, "reason": "invalid_selector_limits"}
    context = _context(packet)
    actions = _string_list(_value(packet, "ELIGIBLE_ACTIONS")) or []
    default = next(
        action for action in actions
        if action.casefold() == _text(_value(packet, "DEFAULT_ACTION")).casefold()
    )
    performance_weight = float(_value(packet, "PERFORMANCE_WEIGHT"))
    cost_weight = float(_value(packet, "COST_WEIGHT"))
    cost_scale_usd = float(_value(packet, "COST_SCALE_USD"))
    stats = {
        action: _action_stats(
            memory, context, action, neighbors=neighbors, min_samples=min_samples,
            performance_weight=performance_weight, cost_weight=cost_weight,
            cost_scale_usd=cost_scale_usd,
        )
        for action in actions
    }
    selected = default
    reason = "cold_start"
    supported = [action for action in actions if stats[action]["supported"]]
    if stats[default]["supported"] and supported:
        selected = max(supported, key=lambda action: (stats[action]["lower_bound"], action == default))
        reason = "memory_advantage" if selected != default else "default_supported"
    elif supported:
        reason = "insufficient_default_evidence"
    decisions = _value(memory, "decisions")
    assert isinstance(decisions, list)
    if len(decisions) >= int(_value(memory, "capacity")):
        completed_index = next(
            (index for index, item in enumerate(decisions) if _value(item, "status") == "completed"),
            None,
        )
        if completed_index is None:
            return {"allowed": False, "reason": "memory_capacity_pending"}
        decisions.pop(completed_index)
    sequence = int(_value(memory, "next_sequence"))
    memory_revision = _digest(decisions)
    decision_id = "route-sha256:" + _digest(
        {"sequence": sequence, "context": context, "actions": actions, "memory_revision": memory_revision}
    )
    decisions.append(
        {
            "sequence": sequence,
            "decision_id": decision_id,
            "status": "pending",
            "context": context,
            "eligible_actions": actions,
            "default_action": default,
            "action": selected,
            "reason": reason,
            "memory_revision": memory_revision,
            "selector": {
                "neighbors": neighbors,
                "min_samples": min_samples,
                "performance_weight": performance_weight,
                "cost_weight": cost_weight,
                "cost_scale_usd": cost_scale_usd,
            },
            "stats": stats,
        }
    )
    memory["next_sequence"] = sequence + 1
    return {
        "allowed": True,
        "advisory": True,
        "action": selected,
        "default_action": default,
        "reason": reason,
        "decision_id": decision_id,
        "memory_revision": memory_revision,
        "stats": stats,
        "authority": "eligible_actions_only",
    }


def record_feedback(memory: dict[str, Any], packet: Mapping[str, Any]) -> dict[str, Any]:
    missing = [name for name in FEEDBACK_FIELDS if not any(str(key).casefold() == name.casefold() for key in packet)]
    if missing:
        return {"allowed": False, "reason": "invalid_feedback", "errors": [f"{name} must be explicit" for name in missing]}
    decision_id = _text(_value(packet, "DECISION_ID"))
    decisions = _value(memory, "decisions", [])
    item = next((candidate for candidate in decisions if _value(candidate, "decision_id") == decision_id), None)
    if not isinstance(item, dict):
        return {"allowed": False, "reason": "unknown_decision"}
    if _value(item, "status") != "pending":
        return {"allowed": False, "reason": "duplicate_feedback"}
    errors: list[str] = []
    if _text(_value(packet, "ACTION")).casefold() != _text(_value(item, "action")).casefold():
        errors.append("ACTION must match the recorded decision")
    if _value(packet, "VERIFIED") is not True:
        errors.append("VERIFIED must equal true")
    if _text(_value(packet, "OUTCOME")).casefold() not in OUTCOMES:
        errors.append("OUTCOME is invalid")
    score = _number(_value(packet, "SCORE"))
    if score is None or score > 1:
        errors.append("SCORE must be between 0 and 1")
    for name in ("COST_USD", "MODEL_ACTIVE_SECONDS"):
        if _number(_value(packet, name)) is None:
            errors.append(f"{name} must be a finite non-negative number")
    if _integer(_value(packet, "TOTAL_TOKENS")) is None:
        errors.append("TOTAL_TOKENS must be a non-negative integer")
    evidence = _text(_value(packet, "EVIDENCE_FINGERPRINT"))
    if not evidence or len(evidence) > 256:
        errors.append("EVIDENCE_FINGERPRINT must be non-empty")
    elif any(
        _value(candidate, "status") == "completed"
        and _value(candidate, "evidence_fingerprint") == evidence
        for candidate in decisions
    ):
        errors.append("EVIDENCE_FINGERPRINT must not repeat completed feedback")
    if errors:
        return {"allowed": False, "reason": "invalid_feedback", "errors": errors}
    item.update(
        {
            "status": "completed",
            "outcome": _text(_value(packet, "OUTCOME")).casefold(),
            "verified": True,
            "score": score,
            "cost_usd": float(_value(packet, "COST_USD")),
            "total_tokens": int(_value(packet, "TOTAL_TOKENS")),
            "model_active_seconds": float(_value(packet, "MODEL_ACTIVE_SECONDS")),
            "evidence_fingerprint": evidence,
        }
    )
    return {
        "allowed": True,
        "reason": "feedback_recorded",
        "decision_id": decision_id,
        "memory_revision": _digest(decisions),
    }


def _stdin_json() -> Mapping[str, Any]:
    raw = sys.stdin.read(MAX_PACKET_BYTES + 1)
    if len(raw.encode("utf-8")) > MAX_PACKET_BYTES:
        raise ValueError("stdin JSON exceeds the packet size limit")
    value = json.loads(raw, object_pairs_hook=_json_object)
    if not isinstance(value, Mapping):
        raise ValueError("stdin JSON must be an object")
    _reject_conflicting_keys(value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    decide_parser = sub.add_parser("decide", help="record one advisory routing action")
    decide_parser.add_argument("--memory", type=Path, required=True)
    decide_parser.add_argument("--capacity", type=int, default=DEFAULT_CAPACITY)
    decide_parser.add_argument("--neighbors", type=int, default=DEFAULT_NEIGHBORS)
    decide_parser.add_argument("--min-samples", type=int, default=DEFAULT_MIN_SAMPLES)
    feedback_parser = sub.add_parser("feedback", help="attach verified execution feedback")
    feedback_parser.add_argument("--memory", type=Path, required=True)
    feedback_parser.add_argument("--capacity", type=int, default=DEFAULT_CAPACITY)
    snapshot_parser = sub.add_parser("snapshot", help="show bounded routing memory")
    snapshot_parser.add_argument("--memory", type=Path, required=True)
    snapshot_parser.add_argument("--capacity", type=int, default=DEFAULT_CAPACITY)
    sub.add_parser("schema", help="show the C-A-F packet contract")
    args = parser.parse_args()
    try:
        if args.command == "schema":
            result = {
                "protocol": PROTOCOL,
                "context_fields": CONTEXT_FIELDS,
                "feedback_fields": FEEDBACK_FIELDS,
                "default_capacity": DEFAULT_CAPACITY,
                "max_capacity": MAX_CAPACITY,
                "default_neighbors": DEFAULT_NEIGHBORS,
                "max_neighbors": MAX_NEIGHBORS,
                "default_min_samples": DEFAULT_MIN_SAMPLES,
                "max_packet_bytes": MAX_PACKET_BYTES,
                "authority": "advisory_only; never expands ELIGIBLE_ACTIONS",
            }
        else:
            if _integer(args.capacity, positive=True) is None or args.capacity > MAX_CAPACITY:
                raise ValueError(f"capacity must be between 1 and {MAX_CAPACITY}")
            memory = load_memory(args.memory, args.capacity)
            if args.command == "decide":
                result = decide(
                    memory, _stdin_json(), neighbors=args.neighbors,
                    min_samples=args.min_samples,
                )
            elif args.command == "feedback":
                result = record_feedback(memory, _stdin_json())
            else:
                result = memory
            if args.command in {"decide", "feedback"} and result.get("allowed"):
                save_memory(args.memory, memory)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result.get("allowed", True) else 2
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"allowed": False, "reason": "invalid_input", "errors": [str(exc)]}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
