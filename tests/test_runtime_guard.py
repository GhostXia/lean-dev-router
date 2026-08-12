from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUARD_PATH = ROOT / ".agents/skills/lean-dev-router/scripts/runtime_guard.py"
SPEC = importlib.util.spec_from_file_location("runtime_guard", GUARD_PATH)
assert SPEC and SPEC.loader
runtime_guard = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runtime_guard
SPEC.loader.exec_module(runtime_guard)


def dispatch() -> dict[str, object]:
    return {
        "PROTOCOL": "lean-dev-router/v2",
        "STATUS": "DISPATCH",
        "TARGET": "implementation",
        "DISPATCH_ID": "d-1",
        "PLAN_ID": "p-1",
        "PLANNER_ROLE": "sol_planner",
        "PLANNER_INSTANCE_ID": "sol-1",
        "AUDITOR_INSTANCE_ID": "terra-audit-1",
        "TASK_SUMMARY": "Make one bounded change",
        "BASELINE": "a" * 40,
        "PATHS_ALLOW": ["src/one.py"],
        "ACCEPTANCE": ["focused test passes"],
        "CONSTRAINTS": ["no dependency changes"],
        "BUDGET": {
            "MODEL_CALL_LIMIT": 3,
            "HYPOTHESIS_LIMIT": 2,
            "MODEL_ACTIVE_SECONDS_LIMIT": 60,
            "REPAIR_CYCLE_LIMIT": 2,
            "STAGNANT_CALL_LIMIT": 2,
        },
        "NEXT": "parent",
    }


def event(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "PLAN_ID": "p-1",
        "DISPATCH_ID": "d-1",
        "REVISION": "r-1",
        "ROLE": "luna_worker",
        "AGENT_INSTANCE_ID": "luna-1",
        "STAGE": "implementation",
        "CONTRACT_VERSION": "c-1",
        "EVIDENCE_FINGERPRINT": "e-1",
        "MODEL_CALLS": 1,
        "MODEL_ACTIVE_SECONDS": 4,
        "WALL_SECONDS": 7,
        "UPSTREAM_ATTEMPTS": 1,
        "INPUT_TOKENS": 100,
        "CACHED_INPUT_TOKENS": 40,
        "CACHE_CREATION_INPUT_TOKENS": 10,
        "OUTPUT_TOKENS": 20,
        "REASONING_OUTPUT_TOKENS": 5,
        "OUTCOME": "running",
    }
    value.update(overrides)
    return value


class DispatchValidationTests(unittest.TestCase):
    def test_schema_cli_exposes_required_usage_fields(self) -> None:
        result = subprocess.run(
            [sys.executable, "-B", str(GUARD_PATH), "schema"],
            text=True, capture_output=True, check=False, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        schema = json.loads(result.stdout)
        self.assertIn("CACHED_INPUT_TOKENS", schema["event_fields"])
        self.assertEqual(schema["default_budget"]["MODEL_CALL_LIMIT"], 8)

    def test_rejects_incomplete_dispatch(self) -> None:
        value = dispatch()
        del value["BUDGET"]
        errors = runtime_guard.validate_dispatch(value)
        self.assertTrue(any("BUDGET" in error for error in errors))

    def test_budget_cannot_raise_runtime_ceiling(self) -> None:
        value = dispatch()
        value["BUDGET"] = dict(value["BUDGET"], MODEL_CALL_LIMIT=9)
        errors = runtime_guard.validate_dispatch(value)
        self.assertTrue(any("runtime ceiling" in error for error in errors))

    def test_start_cli_does_not_create_state_for_invalid_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            result = subprocess.run(
                [sys.executable, "-B", str(GUARD_PATH), "start", "--state", str(state)],
                input=json.dumps({"PROTOCOL": "lean-dev-router/v2"}),
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(result.returncode, 2)
            self.assertFalse(state.exists())

    def test_cli_rejects_conflicting_case_insensitive_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            payloads = (
                json.dumps(dispatch())[:-1] + ', "protocol": "other"}',
                json.dumps(dispatch())[:-1] + ', "PROTOCOL": "other"}',
                json.dumps(dispatch()).replace(
                    '"MODEL_CALL_LIMIT": 3', '"MODEL_CALL_LIMIT": 3, "model_call_limit": 1'
                ),
            )
            for payload in payloads:
                result = subprocess.run(
                    [sys.executable, "-B", str(GUARD_PATH), "start", "--state", str(state)],
                    input=payload, text=True, capture_output=True, check=False, timeout=30,
                )
                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stdout)["reason"], "invalid_input")
                self.assertFalse(state.exists())

    def test_cli_reports_corrupt_state_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            for corrupt in ([], {"dispatch": dispatch(), "stages": []}):
                state.write_text(json.dumps(corrupt), encoding="utf-8")
                result = subprocess.run(
                    [sys.executable, "-B", str(GUARD_PATH), "snapshot", "--state", str(state)],
                    text=True, capture_output=True, check=False, timeout=30,
                )
                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stdout)["reason"], "invalid_input")
                self.assertEqual(result.stderr, "")

    def test_cli_persists_valid_state_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            started = subprocess.run(
                [sys.executable, "-B", str(GUARD_PATH), "start", "--state", str(state)],
                input=json.dumps(dispatch()), text=True, capture_output=True, check=False,
                timeout=30,
            )
            self.assertEqual(started.returncode, 0, started.stderr)
            duplicate_start = subprocess.run(
                [sys.executable, "-B", str(GUARD_PATH), "start", "--state", str(state)],
                input=json.dumps(dispatch()), text=True, capture_output=True, check=False,
                timeout=30,
            )
            self.assertEqual(duplicate_start.returncode, 2)
            self.assertEqual(json.loads(duplicate_start.stdout)["reason"], "state_already_exists")
            observed = subprocess.run(
                [sys.executable, "-B", str(GUARD_PATH), "event", "--state", str(state)],
                input=json.dumps(event(PROGRESS_FINGERPRINT="p", OUTCOME="pass")),
                text=True, capture_output=True, check=False,
                timeout=30,
            )
            self.assertEqual(observed.returncode, 0, observed.stderr)
            self.assertFalse(state.with_name(state.name + ".tmp").exists())
            snapshot = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(next(iter(snapshot["stages"].values()))["termination_reason"], "pass")

    def test_non_sol_dispatch_authority_is_rejected(self) -> None:
        value = dispatch()
        value["PLANNER_ROLE"] = "other_planner"
        errors = runtime_guard.validate_dispatch(value)
        self.assertTrue(any("PLANNER_ROLE" in error for error in errors))

    def test_eligible_terra_planner_dispatch_is_accepted(self) -> None:
        value = dispatch()
        value.update(
            {
                "PLANNER_ROLE": "terra_planner",
                "LEVEL": "L2",
                "OBJECTIVE_FIXED": True,
                "SCOPE_ROOTS": ["src"],
                "OPEN_MAJOR_DECISIONS": False,
                "RISK_FLAGS": [],
                "EXTERNAL_ACTIONS": "none",
                "MAX_DISPATCHES": 1,
                "COMPONENT_COUNT": 1,
                "DEPENDENCY_DEPTH": 0,
                "REQUIRED_PATHS": [],
                "WRITE_BATCH_COUNT": 1,
                "CONTRACT_EXPANDED": False,
                "AMBIGUITY": False,
            }
        )
        self.assertEqual(runtime_guard.validate_dispatch(value), [])

        for field, invalid in (
            ("RISK_FLAGS", ["security"]),
            ("PATHS_ALLOW", ["outside/file.py"]),
            ("WRITE_BATCH_COUNT", 2),
        ):
            changed = dict(value, **{field: invalid})
            self.assertTrue(runtime_guard.validate_dispatch(changed), field)

        missing = dict(value)
        missing.pop("REQUIRED_PATHS")
        self.assertTrue(runtime_guard.validate_dispatch(missing))


class RuntimeBudgetTests(unittest.TestCase):
    def test_counts_tokens_time_and_upstream_attempts(self) -> None:
        guard = runtime_guard.RuntimeGuard(dispatch())
        result = guard.observe(event(PROGRESS_FINGERPRINT="progress-1"))
        self.assertTrue(result["allowed"])
        telemetry = result["telemetry"]
        self.assertEqual(telemetry["uncached_input_tokens"], 60)
        self.assertEqual(telemetry["total_tokens"], 120)
        self.assertEqual(telemetry["model_active_seconds"], 4)
        self.assertEqual(telemetry["wall_seconds"], 7)
        self.assertEqual(telemetry["upstream_attempts"], 1)

    def test_repeated_failure_without_changed_progress_trips(self) -> None:
        guard = runtime_guard.RuntimeGuard(dispatch())
        first = event(
            ERROR_SIGNATURE="E1", COMMAND_FINGERPRINT="cmd", HYPOTHESIS="h1",
            PROGRESS_FINGERPRINT="progress-1",
        )
        self.assertTrue(guard.observe(first)["allowed"])
        second = dict(first)
        result = guard.observe(second)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "repeated_failure_without_new_evidence")
        self.assertEqual(result["destination"], "parent:terra")

    def test_stagnation_trips_at_hard_limit(self) -> None:
        guard = runtime_guard.RuntimeGuard(dispatch())
        self.assertTrue(guard.observe(event())["allowed"])
        result = guard.observe(event())
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "spinning")

    def test_call_hypothesis_and_active_time_limits_are_hard(self) -> None:
        cases = (
            (
                [event(PROGRESS_FINGERPRINT=f"p-{index}") for index in range(1, 4)],
                "model_call_limit",
            ),
            (
                [
                    event(PROGRESS_FINGERPRINT="p-1", HYPOTHESIS="h-1"),
                    event(PROGRESS_FINGERPRINT="p-2", HYPOTHESIS="h-2"),
                ],
                "hypothesis_limit",
            ),
            (
                [event(PROGRESS_FINGERPRINT="p-1", MODEL_ACTIVE_SECONDS=60, WALL_SECONDS=60)],
                "model_active_time_limit",
            ),
        )
        for events, reason in cases:
            guard = runtime_guard.RuntimeGuard(dispatch())
            result = None
            for item in events:
                result = guard.observe(item)
            assert result is not None
            self.assertFalse(result["allowed"], reason)
            self.assertEqual(result["reason"], reason)

    def test_success_on_final_allowed_call_is_accepted_then_latched(self) -> None:
        guard = runtime_guard.RuntimeGuard(dispatch())
        guard.observe(event(PROGRESS_FINGERPRINT="p-1"))
        guard.observe(event(PROGRESS_FINGERPRINT="p-2"))
        result = guard.observe(event(PROGRESS_FINGERPRINT="p-3", OUTCOME="pass"))
        self.assertTrue(result["allowed"])
        self.assertEqual(result["reason"], "stage_complete")
        duplicate = guard.observe(event(PROGRESS_FINGERPRINT="p-3", OUTCOME="pass"))
        self.assertFalse(duplicate["allowed"])
        self.assertEqual(duplicate["reason"], "duplicate_terminal_stage")

    def test_invalid_token_breakdown_does_not_consume_budget(self) -> None:
        guard = runtime_guard.RuntimeGuard(dispatch())
        result = guard.observe(
            event(INPUT_TOKENS=10, CACHED_INPUT_TOKENS=11, CACHE_CREATION_INPUT_TOKENS=2)
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(guard.stages, {})

    def test_invalid_outcome_does_not_consume_budget(self) -> None:
        guard = runtime_guard.RuntimeGuard(dispatch())
        result = guard.observe(event(OUTCOME="unknown", PROGRESS_FINGERPRINT="bad"))
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "invalid_event")
        self.assertEqual(guard.stages, {})

    def test_changed_evidence_does_not_reset_stage_budget(self) -> None:
        guard = runtime_guard.RuntimeGuard(dispatch())
        first = guard.observe(event(EVIDENCE_FINGERPRINT="e-1", PROGRESS_FINGERPRINT="p-1"))
        second = guard.observe(event(EVIDENCE_FINGERPRINT="e-2", PROGRESS_FINGERPRINT="p-2"))
        self.assertTrue(first["allowed"])
        self.assertTrue(second["allowed"])
        self.assertEqual(second["telemetry"]["model_calls"], 2)
        self.assertEqual(len(guard.stages), 1)

    def test_missing_usage_field_fails_closed(self) -> None:
        guard = runtime_guard.RuntimeGuard(dispatch())
        item = event()
        del item["CACHED_INPUT_TOKENS"]
        result = guard.observe(item)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "incomplete_telemetry")
        self.assertEqual(guard.stages, {})

    def test_latch_requires_changed_revision_contract_or_evidence(self) -> None:
        guard = runtime_guard.RuntimeGuard(dispatch())
        guard.observe(event())
        guard.observe(event())
        blocked = guard.observe(event())
        self.assertEqual(blocked["reason"], "escalation_latch")
        resumed = guard.observe(
            event(EVIDENCE_FINGERPRINT="e-2", PROGRESS_FINGERPRINT="new", OUTCOME="pass")
        )
        self.assertTrue(resumed["allowed"])
        self.assertEqual(resumed["telemetry"]["model_calls"], 3)

    def test_non_luna_writer_is_rejected(self) -> None:
        guard = runtime_guard.RuntimeGuard(dispatch())
        result = guard.observe(
            event(ROLE="parent", AGENT_INSTANCE_ID="parent-1", ACTION="write")
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "unauthorized_writer")

    def test_agent_identity_cannot_change_role(self) -> None:
        guard = runtime_guard.RuntimeGuard(dispatch())
        guard.observe(event(PROGRESS_FINGERPRINT="p"))
        with self.assertRaisesRegex(ValueError, "cannot change role"):
            guard.observe(
                event(ROLE="terra_auditor", AGENT_INSTANCE_ID="luna-1", STAGE="audit")
            )


class RepairAndAuditTests(unittest.TestCase):
    def repair(self, **overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "PLAN_ID": "p-1",
            "DISPATCH_ID": "d-1",
            "AUDITOR_INSTANCE_ID": "terra-audit-1",
            "CONTRACT_EFFECT": "unchanged",
            "AFFECTED_PATHS": ["src/one.py"],
            "ACCEPTANCE": ["focused test passes"],
            "REPAIR_CYCLE": 1,
            "REVISION": "r-2",
            "EVIDENCE_FINGERPRINT": "finding-1",
        }
        value.update(overrides)
        return value

    def test_repair_must_be_sequential_and_inside_contract(self) -> None:
        guard = runtime_guard.RuntimeGuard(dispatch())
        self.assertTrue(guard.register_repair(self.repair())["allowed"])
        repeated = guard.register_repair(self.repair())
        self.assertEqual(repeated["reason"], "non_sequential_repair_cycle")
        repeated_evidence = guard.register_repair(
            self.repair(REPAIR_CYCLE=2, REVISION="r-3")
        )
        self.assertEqual(repeated_evidence["reason"], "repeated_repair_without_new_evidence")
        outside = guard.register_repair(
            self.repair(
                REPAIR_CYCLE=2,
                AFFECTED_PATHS=["elsewhere/file.py"],
                EVIDENCE_FINGERPRINT="finding-2",
            )
        )
        self.assertEqual(outside["reason"], "invalid_repair")
        exhausted = guard.register_repair(self.repair(REPAIR_CYCLE=3))
        self.assertEqual(exhausted["reason"], "invalid_repair")

    def test_same_revision_audit_is_registered_once(self) -> None:
        guard = runtime_guard.RuntimeGuard(dispatch())
        packet = {
            "ACTION": "begin",
            "PLAN_ID": "p-1",
            "DISPATCH_ID": "d-1",
            "REVISION": "r-2",
            "AUDITOR_INSTANCE_ID": "terra-audit-1",
            "AUDIT_SCOPE": ["src/one.py", "callers"],
            "AUDIT_MODE": "full",
        }
        self.assertTrue(guard.begin_audit(packet)["allowed"])
        duplicate = guard.begin_audit(packet)
        self.assertFalse(duplicate["allowed"])
        self.assertEqual(duplicate["reason"], "duplicate_audit_revision")
        concurrent = guard.begin_audit(dict(packet, REVISION="r-3"))
        self.assertFalse(concurrent["allowed"])
        self.assertEqual(concurrent["reason"], "audit_already_running")

        complete = {
            "ACTION": "complete",
            "PLAN_ID": "p-1",
            "DISPATCH_ID": "d-1",
            "REVISION": "r-2",
            "AUDITOR_INSTANCE_ID": "terra-audit-1",
            "TERMINATION_REASON": "pass",
            "VERIFIED": ["acceptance"],
            "UNVERIFIED": [],
        }
        self.assertTrue(guard.audit_job(complete)["allowed"])
        incremental = dict(
            packet,
            REVISION="r-3",
            AUDIT_MODE="incremental",
            PREVIOUS_REVISION="r-2",
            UNRESOLVED_FINDINGS=[],
        )
        self.assertTrue(guard.audit_job(incremental)["allowed"])

    def test_changed_revision_rejects_full_reaudit(self) -> None:
        guard = runtime_guard.RuntimeGuard(dispatch())
        begin = {
            "ACTION": "begin", "PLAN_ID": "p-1", "DISPATCH_ID": "d-1",
            "REVISION": "r-2", "AUDITOR_INSTANCE_ID": "terra-audit-1",
            "AUDIT_SCOPE": ["src/one.py"], "AUDIT_MODE": "full",
        }
        guard.audit_job(begin)
        guard.audit_job(
            {
                "ACTION": "complete", "PLAN_ID": "p-1", "DISPATCH_ID": "d-1",
                "REVISION": "r-2", "AUDITOR_INSTANCE_ID": "terra-audit-1",
                "TERMINATION_REASON": "pass", "VERIFIED": [], "UNVERIFIED": [],
            }
        )
        result = guard.audit_job(dict(begin, REVISION="r-3"))
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "invalid_incremental_audit")

    def test_abandoned_audit_releases_slot_without_incremental_baseline(self) -> None:
        guard = runtime_guard.RuntimeGuard(dispatch())
        begin = {
            "ACTION": "begin", "PLAN_ID": "p-1", "DISPATCH_ID": "d-1",
            "REVISION": "r-2", "AUDITOR_INSTANCE_ID": "terra-audit-1",
            "AUDIT_SCOPE": ["src/one.py"], "AUDIT_MODE": "full",
        }
        self.assertTrue(guard.audit_job(begin)["allowed"])
        abandoned = guard.audit_job(
            {
                "ACTION": "abandon", "PLAN_ID": "p-1", "DISPATCH_ID": "d-1",
                "REVISION": "r-2", "AUDITOR_INSTANCE_ID": "terra-audit-1",
                "TERMINATION_REASON": "model_call_limit",
            }
        )
        self.assertFalse(abandoned["allowed"])
        self.assertEqual(abandoned["reason"], "audit_abandoned")
        self.assertEqual(abandoned["destination"], "parent:sol")
        self.assertEqual(guard.last_completed_audits, {})
        next_audit = guard.audit_job(dict(begin, REVISION="r-3"))
        self.assertTrue(next_audit["allowed"])

    def test_abandon_rejects_wrong_identity_and_non_running_job(self) -> None:
        guard = runtime_guard.RuntimeGuard(dispatch())
        packet = {
            "ACTION": "abandon", "PLAN_ID": "p-1", "DISPATCH_ID": "d-1",
            "REVISION": "r-2", "AUDITOR_INSTANCE_ID": "wrong-auditor",
            "TERMINATION_REASON": "blocked",
        }
        self.assertEqual(guard.audit_job(packet)["reason"], "invalid_audit_abandon")
        packet["AUDITOR_INSTANCE_ID"] = "terra-audit-1"
        self.assertEqual(guard.audit_job(packet)["reason"], "audit_job_not_running")

    def test_snapshot_round_trip_preserves_gates(self) -> None:
        guard = runtime_guard.RuntimeGuard(dispatch())
        guard.observe(event(PROGRESS_FINGERPRINT="p"))
        guard.register_repair(self.repair())
        restored = runtime_guard.RuntimeGuard.from_snapshot(guard.snapshot())
        self.assertEqual(restored.snapshot(), guard.snapshot())


if __name__ == "__main__":
    unittest.main()
