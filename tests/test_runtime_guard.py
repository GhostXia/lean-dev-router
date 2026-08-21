from __future__ import annotations

import importlib.util
import json
import shutil
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


def parent_dispatch(**overrides: object) -> dict[str, object]:
    value = dispatch()
    value.update(
        {
            "PLANNER_ROLE": "parent",
            "PLANNER_CAPABILITY": "bounded_l1_l2_dispatch",
            "LEVEL": "L1",
            "OBJECTIVE_FIXED": True,
            "SCOPE_ROOTS": ["src"],
            "OPEN_MAJOR_DECISIONS": False,
            "RISK_FLAGS": "none",
            "EXTERNAL_ACTIONS": "none",
            "MAX_DISPATCHES": 1,
            "COMPONENT_COUNT": 1,
            "DEPENDENCY_DEPTH": 0,
            "REQUIRED_PATHS": [],
            "WRITE_BATCH_COUNT": 1,
            "INTEGRATION": False,
            "CONFLICT": False,
            "CONTRACT_EXPANDED": False,
            "AMBIGUITY": False,
            "CONTRACT_CHANGE": False,
            "SCOPE_CHANGE": False,
            "ACCEPTANCE_CHANGE": False,
            "CONSTRAINT_CHANGE": False,
            "ARCHITECTURE_CHANGE": False,
            "SECURITY_CHANGE": False,
            "COMPATIBILITY_CHANGE": False,
            "BUDGET": dict(runtime_guard.PARENT_FAST_PATH_BUDGET),
        }
    )
    value.update(overrides)
    return value


def trusted_parent_kwargs(value: dict[str, object]) -> dict[str, str]:
    return {
        "trusted_parent_instance_id": str(value["PLANNER_INSTANCE_ID"]),
        "trusted_parent_model": "gpt-5.6-terra",
        "trusted_parent_reasoning_effort": "high",
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


def retry_packet(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "ACTION": "retry",
        "PLAN_ID": "p-1",
        "DISPATCH_ID": "d-1",
        "EXECUTION_ATTEMPT": 2,
        "REVISION": "a" * 40,
        "DISPATCH_FINGERPRINT": runtime_guard.fingerprint(dispatch()),
        "PRODUCT_COUNT": 0,
    }
    value.update(overrides)
    return value


class DispatchValidationTests(unittest.TestCase):
    def test_clean_revision_accepts_any_concrete_git_sha(self) -> None:
        self.assertEqual(runtime_guard.validate_revision("b" * 40, "a" * 40), [])
        self.assertEqual(runtime_guard.validate_revision("c" * 64, "a" * 40), [])

    def test_schema_cli_exposes_required_usage_fields(self) -> None:
        result = subprocess.run(
            [sys.executable, "-B", str(GUARD_PATH), "schema"],
            text=True, capture_output=True, check=False, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        schema = json.loads(result.stdout)
        self.assertIn("CACHED_INPUT_TOKENS", schema["event_fields"])
        self.assertEqual(schema["terminal_event_fields"], ["PRODUCT_COUNT"])
        self.assertEqual(schema["default_budget"]["MODEL_CALL_LIMIT"], 8)
        for packet in ("audit_begin_fields", "audit_complete_fields", "audit_abandon_fields"):
            self.assertIn("AUDITOR_ROLE", schema[packet])
            self.assertIn("AUDITOR_INSTANCE_ID", schema[packet])
            self.assertIn("AGENT_INSTANCE_ID", schema[packet])

    def test_rejects_incomplete_dispatch(self) -> None:
        value = dispatch()
        del value["BUDGET"]
        errors = runtime_guard.validate_dispatch(value)
        self.assertTrue(any("BUDGET" in error for error in errors))

    def test_preflight_cli_validates_without_creating_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            result = subprocess.run(
                [sys.executable, "-B", str(GUARD_PATH), "preflight"],
                input=json.dumps(dispatch()), text=True, capture_output=True, check=False,
                timeout=30,
            )
            payload = json.loads(result.stdout)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(payload["allowed"])
            self.assertEqual(payload["reason"], "dispatch_valid")
            self.assertEqual(payload["destination"], "parent:luna")
            self.assertRegex(payload["dispatch_fingerprint"], r"^[0-9a-f]{64}$")
            self.assertFalse(state.exists())

    def test_installed_skill_preflight_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            installed = Path(directory) / "skills" / "lean-dev-router"
            shutil.copytree(GUARD_PATH.parents[1], installed)
            guard = installed / "scripts" / "runtime_guard.py"
            schema = subprocess.run(
                [sys.executable, "-B", str(guard), "schema"],
                text=True, capture_output=True, check=False, timeout=30,
            )
            preflight = subprocess.run(
                [sys.executable, "-B", str(guard), "preflight"],
                input=json.dumps(dispatch()), text=True, capture_output=True, check=False,
                timeout=30,
            )
            self.assertEqual(schema.returncode, 0, schema.stderr)
            self.assertIn("dispatch_fields", json.loads(schema.stdout))
            self.assertEqual(preflight.returncode, 0, preflight.stderr)
            self.assertTrue(json.loads(preflight.stdout)["allowed"])

    def test_preflight_and_start_reject_the_same_invalid_dispatch(self) -> None:
        value = dispatch()
        value["BASELINE"] = "NOT-A-GIT-HASH"
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            preflight = subprocess.run(
                [sys.executable, "-B", str(GUARD_PATH), "preflight"],
                input=json.dumps(value), text=True, capture_output=True, check=False,
                timeout=30,
            )
            started = subprocess.run(
                [sys.executable, "-B", str(GUARD_PATH), "start", "--state", str(state)],
                input=json.dumps(value), text=True, capture_output=True, check=False,
                timeout=30,
            )
            self.assertEqual(preflight.returncode, 2)
            self.assertEqual(started.returncode, 2)
            preflight_result = json.loads(preflight.stdout)
            start_result = json.loads(started.stdout)
            self.assertEqual(preflight_result["reason"], "invalid_dispatch")
            self.assertEqual(start_result["reason"], preflight_result["reason"])
            self.assertEqual(start_result["errors"], preflight_result["errors"])
            self.assertEqual(
                start_result["dispatch_fingerprint"],
                preflight_result["dispatch_fingerprint"],
            )
            self.assertIn("BASELINE", " ".join(preflight_result["errors"]))
            self.assertFalse(state.exists())

    def test_revision_must_be_concrete_clean_or_dirty_identity(self) -> None:
        valid = (
            "a" * 40,
            "worktree-sha256:" + "b" * 64,
        )
        for revision in valid:
            value = dispatch()
            value["REVISION"] = revision
            self.assertEqual(runtime_guard.validate_dispatch(value), [])
        for revision in (
            "<luna-revision>",
            "worktree-sha256:" + "B" * 64,
            "worktree-sha256:" + "b" * 63,
        ):
            value = dispatch()
            value["REVISION"] = revision
            self.assertTrue(any("REVISION" in error for error in runtime_guard.validate_dispatch(value)))

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
                for command in (
                    [sys.executable, "-B", str(GUARD_PATH), "preflight"],
                    [sys.executable, "-B", str(GUARD_PATH), "start", "--state", str(state)],
                ):
                    result = subprocess.run(
                        command, input=payload, text=True, capture_output=True,
                        check=False, timeout=30,
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
                input=json.dumps(event(PROGRESS_FINGERPRINT="p", OUTCOME="pass", PRODUCT_COUNT=1)),
                text=True, capture_output=True, check=False,
                timeout=30,
            )
            self.assertEqual(observed.returncode, 0, observed.stderr)
            self.assertFalse(state.with_name(state.name + ".tmp").exists())
            snapshot = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(snapshot["execution_attempts"], 1)
            self.assertEqual(snapshot["execution_history"][0]["status"], "completed")
            self.assertEqual(next(iter(snapshot["stages"].values()))["termination_reason"], "pass")

    def test_execution_retry_requires_authoritative_zero_product_completion(self) -> None:
        never_started = runtime_guard.RuntimeGuard(dispatch())
        required = never_started.validate_audit_prerequisites({})
        self.assertEqual(required["reason"], "execution_required")
        self.assertEqual(required["destination"], "parent:luna")

        guard = runtime_guard.RuntimeGuard(dispatch())
        self.assertTrue(guard.register_initial_execution()["allowed"])
        missing = guard.observe(
            event(REVISION="a" * 40, OUTCOME="blocked", PROGRESS_FINGERPRINT="blocked")
        )
        self.assertEqual(missing["reason"], "product_telemetry_missing")
        uncertain = guard.validate_audit_prerequisites({})
        self.assertEqual(uncertain["reason"], "execution_telemetry_missing")
        self.assertEqual(uncertain["destination"], "parent:pause")

        completed = guard.observe(
            event(
                REVISION="a" * 40, OUTCOME="blocked",
                PROGRESS_FINGERPRINT="blocked", PRODUCT_COUNT=0,
            )
        )
        self.assertEqual(completed["reason"], "blocked")
        retry_required = guard.validate_audit_prerequisites({})
        self.assertEqual(retry_required["reason"], "execution_retry_required")
        retry = guard.register_execution(retry_packet())
        self.assertTrue(retry["allowed"])
        self.assertEqual(retry["execution_attempt"], 2)

        missing_product = retry_packet(EXECUTION_ATTEMPT=3)
        missing_product.pop("PRODUCT_COUNT")
        invalid = guard.register_execution(missing_product)
        self.assertEqual(invalid["reason"], "invalid_execution")
        self.assertTrue(any("zero product" in error for error in invalid["errors"]))

        changed_revision = retry_packet(REVISION="b" * 40)
        changed = runtime_guard.validate_execution(changed_revision, dispatch())
        self.assertTrue(any("unchanged clean BASELINE" in error for error in changed))

    def test_non_sol_dispatch_authority_is_rejected(self) -> None:
        value = dispatch()
        value["PLANNER_ROLE"] = "other_planner"
        errors = runtime_guard.validate_dispatch(value)
        self.assertTrue(any("PLANNER_ROLE" in error for error in errors))

    def test_eligible_parent_fast_path_dispatch_is_accepted(self) -> None:
        value = parent_dispatch(LEVEL="L2", RISK_FLAGS=[])
        self.assertEqual(
            runtime_guard.validate_dispatch(
                value, **trusted_parent_kwargs(value)
            ),
            [],
        )
        denied = runtime_guard.preflight_dispatch(value)
        self.assertFalse(denied["allowed"])
        self.assertEqual(denied["destination"], "parent:sol")
        self.assertIn("trusted parent instance identity", " ".join(denied["errors"]))
        mismatch = runtime_guard.preflight_dispatch(
            value, **dict(trusted_parent_kwargs(value), trusted_parent_instance_id="different-parent")
        )
        self.assertFalse(mismatch["allowed"])
        wrong_model = runtime_guard.preflight_dispatch(
            value, **dict(trusted_parent_kwargs(value), trusted_parent_model="gpt-5.6-luna")
        )
        self.assertFalse(wrong_model["allowed"])
        accepted = runtime_guard.preflight_dispatch(value, **trusted_parent_kwargs(value))
        self.assertTrue(accepted["allowed"])
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "parent-state.json"
            denied_cli = subprocess.run(
                [sys.executable, "-B", str(GUARD_PATH), "start", "--state", str(state)],
                input=json.dumps(value), text=True, capture_output=True, check=False, timeout=30,
            )
            self.assertEqual(denied_cli.returncode, 2)
            self.assertFalse(state.exists())
            accepted_cli = subprocess.run(
                [
                    sys.executable, "-B", str(GUARD_PATH), "start", "--state", str(state),
                    "--trusted-parent-instance-id", str(value["PLANNER_INSTANCE_ID"]),
                    "--trusted-parent-model", "gpt-5.6-terra",
                    "--trusted-parent-reasoning-effort", "high",
                ],
                input=json.dumps(value), text=True, capture_output=True, check=False, timeout=30,
            )
            self.assertEqual(accepted_cli.returncode, 0, accepted_cli.stderr)
            self.assertTrue(state.exists())

        for field in runtime_guard.PARENT_CHANGE_FIELDS:
            for invalid in (None, "none", ["none"], True):
                changed = dict(value, **{field: invalid})
                self.assertTrue(runtime_guard.validate_dispatch(changed), (field, invalid))

        non_change_none = dict(
            value,
            RISK_FLAGS=None,
            EXTERNAL_ACTIONS=["none"],
            INTEGRATION="none",
            CONFLICT=None,
            CONTRACT_EXPANDED=["none"],
        )
        self.assertEqual(
            runtime_guard.validate_dispatch(
                non_change_none,
                **trusted_parent_kwargs(non_change_none),
            ),
            [],
        )

        for field, invalid in (
            ("RISK_FLAGS", ["security"]),
            ("PATHS_ALLOW", ["outside/file.py"]),
            ("WRITE_BATCH_COUNT", 2),
            ("PLANNER_CAPABILITY", "other"),
            ("COMPONENT_COUNT", 2),
        ):
            changed = dict(value, **{field: invalid})
            self.assertTrue(runtime_guard.validate_dispatch(changed), field)

        missing = dict(value)
        missing.pop("REQUIRED_PATHS")
        self.assertTrue(runtime_guard.validate_dispatch(missing))

    def test_parent_fast_path_budget_and_sol_exhaustion(self) -> None:
        value = parent_dispatch()
        guard = runtime_guard.RuntimeGuard(
            value, **trusted_parent_kwargs(value)
        )
        result = guard.observe(event(PROGRESS_FINGERPRINT="p-1"))
        self.assertTrue(result["allowed"])
        result = guard.observe(event(PROGRESS_FINGERPRINT="p-1"))
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "spinning")
        self.assertEqual(result["destination"], "parent:sol")

    def test_parent_and_planner_identity_cannot_be_final_auditor(self) -> None:
        value = parent_dispatch()
        value["AUDITOR_INSTANCE_ID"] = value["PLANNER_INSTANCE_ID"]
        self.assertTrue(runtime_guard.validate_dispatch(value))


class RuntimeBudgetTests(unittest.TestCase):
    def test_parent_self_audit_role_is_case_insensitive(self) -> None:
        guard = runtime_guard.RuntimeGuard(dispatch())
        result = guard.observe(event(ROLE=" PARENT ", ACTION="AuDiT"))
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "parent_cannot_self_audit")
        self.assertEqual(result["destination"], "parent:sol")

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
        result = guard.observe(event(PROGRESS_FINGERPRINT="p-3", OUTCOME="pass", PRODUCT_COUNT=1))
        self.assertTrue(result["allowed"])
        self.assertEqual(result["reason"], "stage_complete")
        duplicate = guard.observe(event(PROGRESS_FINGERPRINT="p-3", OUTCOME="pass", PRODUCT_COUNT=1))
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
            event(
                EVIDENCE_FINGERPRINT="e-2", PROGRESS_FINGERPRINT="new",
                OUTCOME="pass", PRODUCT_COUNT=1,
            )
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
    def luna_pass(
        self, guard: runtime_guard.RuntimeGuard, **overrides: object
    ) -> dict[str, object]:
        if not guard.execution_history:
            self.assertTrue(guard.register_initial_execution()["allowed"])
        values: dict[str, object] = {
            "REVISION": "a" * 40,
            "OUTCOME": "pass",
            "PROGRESS_FINGERPRINT": "luna-pass",
            "PRODUCT_COUNT": 1,
            "SCOPE_EVIDENCE": "scope-pass",
            "REPLAY_EVIDENCE": "replay-pass",
            "DEPENDENCIES": [],
        }
        values.update(overrides)
        result = guard.observe(
            event(**values)
        )
        self.assertTrue(result["allowed"])
        assert guard.luna_pass is not None
        return guard.luna_pass

    def test_audit_rejects_unregistered_execution_even_with_synthetic_pass(self) -> None:
        guard = runtime_guard.RuntimeGuard(dispatch())
        result = guard.observe(
            event(
                REVISION="a" * 40,
                OUTCOME="pass",
                PROGRESS_FINGERPRINT="synthetic-pass",
                PRODUCT_COUNT=1,
            )
        )
        self.assertTrue(result["allowed"])
        rejected = guard.validate_audit_prerequisites(self.audit_packet(guard))
        self.assertEqual(rejected["reason"], "execution_registration_missing")
        self.assertEqual(rejected["destination"], "parent:sol")

    def audit_packet(self, guard: runtime_guard.RuntimeGuard, **overrides: object) -> dict[str, object]:
        evidence = guard.luna_pass or {}
        packet: dict[str, object] = {
            "ACTION": "begin",
            "PLAN_ID": "p-1",
            "DISPATCH_ID": "d-1",
            "REVISION": "a" * 40,
            "AUDITOR_ROLE": "terra_auditor",
            "AUDITOR_INSTANCE_ID": "terra-audit-1",
            "AGENT_INSTANCE_ID": "terra-audit-1",
            "AUDIT_SCOPE": ["src/one.py"],
            "AUDIT_MODE": "full",
            "LUNA_STATUS": "PASS",
            "LUNA_DISPATCH_ID": "d-1",
            "LUNA_REVISION": evidence.get("REVISION", ""),
            "LUNA_EVIDENCE_FINGERPRINT": evidence.get("EVIDENCE_FINGERPRINT", ""),
            "SCOPE_EVIDENCE": "scope-pass",
            "REPLAY_EVIDENCE": "replay-pass",
            "DEPENDENCIES": [],
            "TELEMETRY": evidence.get("TELEMETRY", {}),
        }
        packet.update(overrides)
        return packet

    def repair(self, **overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "PLAN_ID": "p-1",
            "DISPATCH_ID": "d-1",
            "AUDITOR_INSTANCE_ID": "terra-audit-1",
            "FINDING_CLASS": "A",
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

    def test_only_explicit_class_a_can_enter_luna_repair(self) -> None:
        guard = runtime_guard.RuntimeGuard(dispatch())
        for finding in ("B", "C", "D", "unknown", "a"):
            result = guard.register_repair(self.repair(FINDING_CLASS=finding))
            self.assertFalse(result["allowed"], finding)
            self.assertEqual(result["reason"], "finding_requires_sol", finding)
            self.assertEqual(result["destination"], "parent:sol", finding)
            self.assertEqual(guard.repair_cycles, {}, finding)

        missing = self.repair()
        missing.pop("FINDING_CLASS")
        result = guard.register_repair(missing)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "finding_requires_sol")
        self.assertEqual(result["destination"], "parent:sol")
        self.assertEqual(guard.repair_cycles, {})

        accepted = guard.register_repair(self.repair())
        self.assertTrue(accepted["allowed"])
        self.assertEqual(accepted["destination"], "parent:luna")
        self.assertEqual(guard.repair_cycles, {"p-1:d-1": 1})

    def test_same_revision_audit_is_registered_once(self) -> None:
        guard = runtime_guard.RuntimeGuard(dispatch())
        self.luna_pass(guard)
        packet = self.audit_packet(guard, AUDIT_SCOPE=["src/one.py", "callers"])
        self.assertTrue(guard.begin_audit(packet)["allowed"])
        duplicate = guard.begin_audit(packet)
        self.assertFalse(duplicate["allowed"])
        self.assertEqual(duplicate["reason"], "duplicate_audit_revision")
        concurrent = guard.begin_audit(
            dict(packet, REVISION="b" * 40, LUNA_REVISION="b" * 40)
        )
        self.assertFalse(concurrent["allowed"])
        self.assertEqual(concurrent["reason"], "audit_already_running")

        complete = {
            "ACTION": "complete",
            "PLAN_ID": "p-1",
            "DISPATCH_ID": "d-1",
            "REVISION": "a" * 40,
            "AUDITOR_ROLE": "terra_auditor",
            "AUDITOR_INSTANCE_ID": "terra-audit-1",
            "AGENT_INSTANCE_ID": "terra-audit-1",
            "TERMINATION_REASON": "pass",
            "VERIFIED": ["acceptance"],
            "UNVERIFIED": [],
        }
        self.assertTrue(guard.audit_job(complete)["allowed"])
        next_revision = "b" * 40
        self.luna_pass(
            guard,
            REVISION=next_revision,
            EVIDENCE_FINGERPRINT="e-2",
            PROGRESS_FINGERPRINT="luna-pass-2",
        )
        incremental = self.audit_packet(
            guard,
            REVISION=next_revision,
            AUDIT_MODE="incremental",
            PREVIOUS_REVISION="a" * 40,
            UNRESOLVED_FINDINGS=[],
        )
        self.assertTrue(guard.audit_job(incremental)["allowed"])

    def test_audit_requires_matching_luna_pass_and_prerequisites(self) -> None:
        guard = runtime_guard.RuntimeGuard(dispatch())
        packet = self.audit_packet(guard)
        missing = guard.begin_audit(packet)
        self.assertEqual(missing["request"], "execution")
        self.luna_pass(guard)
        incomplete = guard.begin_audit(dict(packet, SCOPE_EVIDENCE=""))
        self.assertEqual(incomplete["destination"], "parent:sol")
        mismatched = guard.begin_audit(
            dict(self.audit_packet(guard), LUNA_EVIDENCE_FINGERPRINT="wrong")
        )
        self.assertEqual(mismatched["destination"], "parent:sol")
        telemetry = dict(self.audit_packet(guard)["TELEMETRY"])
        telemetry["input_tokens"] = int(telemetry["input_tokens"]) + 1
        mismatched_telemetry = guard.begin_audit(
            dict(self.audit_packet(guard), TELEMETRY=telemetry)
        )
        self.assertEqual(mismatched_telemetry["reason"], "audit_prerequisite_failed")
        self.assertTrue(
            any("complete recorded PASS telemetry" in error for error in mismatched_telemetry["errors"])
        )

    def test_changed_revision_rejects_full_reaudit(self) -> None:
        guard = runtime_guard.RuntimeGuard(dispatch())
        self.luna_pass(guard)
        begin = self.audit_packet(guard)
        guard.audit_job(begin)
        guard.audit_job(
            {
                "ACTION": "complete", "PLAN_ID": "p-1", "DISPATCH_ID": "d-1",
                "REVISION": "a" * 40, "AUDITOR_ROLE": "terra_auditor",
                "AUDITOR_INSTANCE_ID": "terra-audit-1", "AGENT_INSTANCE_ID": "terra-audit-1",
                "TERMINATION_REASON": "pass", "VERIFIED": [], "UNVERIFIED": [],
            }
        )
        next_revision = "b" * 40
        self.luna_pass(
            guard,
            REVISION=next_revision,
            EVIDENCE_FINGERPRINT="e-2",
            PROGRESS_FINGERPRINT="luna-pass-2",
        )
        result = guard.audit_job(
            self.audit_packet(guard, REVISION=next_revision, AUDIT_MODE="full")
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "invalid_incremental_audit")

    def test_abandoned_audit_releases_slot_without_incremental_baseline(self) -> None:
        guard = runtime_guard.RuntimeGuard(dispatch())
        self.luna_pass(guard)
        begin = self.audit_packet(guard)
        self.assertTrue(guard.audit_job(begin)["allowed"])
        abandoned = guard.audit_job(
            {
                "ACTION": "abandon", "PLAN_ID": "p-1", "DISPATCH_ID": "d-1",
                "REVISION": "a" * 40, "AUDITOR_ROLE": "terra_auditor",
                "AUDITOR_INSTANCE_ID": "terra-audit-1", "AGENT_INSTANCE_ID": "terra-audit-1",
                "TERMINATION_REASON": "model_call_limit",
            }
        )
        self.assertFalse(abandoned["allowed"])
        self.assertEqual(abandoned["reason"], "audit_abandoned")
        self.assertEqual(abandoned["destination"], "parent:sol")
        self.assertEqual(guard.last_completed_audits, {})
        next_revision = "b" * 40
        self.luna_pass(
            guard,
            REVISION=next_revision,
            EVIDENCE_FINGERPRINT="e-2",
            PROGRESS_FINGERPRINT="luna-pass-2",
        )
        next_audit = guard.audit_job(
            self.audit_packet(guard, REVISION=next_revision, AUDIT_MODE="full")
        )
        self.assertTrue(next_audit["allowed"])

    def test_abandon_rejects_wrong_identity_and_non_running_job(self) -> None:
        guard = runtime_guard.RuntimeGuard(dispatch())
        packet = {
            "ACTION": "abandon", "PLAN_ID": "p-1", "DISPATCH_ID": "d-1",
            "REVISION": "r-2", "AUDITOR_ROLE": "terra_auditor",
            "AUDITOR_INSTANCE_ID": "wrong-auditor", "AGENT_INSTANCE_ID": "wrong-auditor",
            "TERMINATION_REASON": "blocked",
        }
        self.assertEqual(guard.audit_job(packet)["reason"], "invalid_audit_abandon")
        packet["AUDITOR_INSTANCE_ID"] = "terra-audit-1"
        packet["AGENT_INSTANCE_ID"] = "terra-audit-1"
        self.assertEqual(guard.audit_job(packet)["reason"], "audit_job_not_running")

    def test_audit_packets_fail_closed_on_role_and_actor_identity(self) -> None:
        begin = {
            "ACTION": "begin", "PLAN_ID": "p-1", "DISPATCH_ID": "d-1",
            "REVISION": "r-2", "AUDITOR_ROLE": "terra_auditor",
            "AUDITOR_INSTANCE_ID": "terra-audit-1", "AGENT_INSTANCE_ID": "TERRA-AUDIT-1",
            "AUDIT_SCOPE": ["src/one.py"], "AUDIT_MODE": "full",
        }
        for field in ("AUDITOR_ROLE", "AGENT_INSTANCE_ID"):
            invalid = dict(begin)
            invalid.pop(field)
            self.assertFalse(runtime_guard.RuntimeGuard(dispatch()).audit_job(invalid)["allowed"], field)
        for role in ("parent", "sol_planner"):
            invalid = dict(begin, AUDITOR_ROLE=role)
            self.assertFalse(runtime_guard.RuntimeGuard(dispatch()).audit_job(invalid)["allowed"], role)
        mismatch = dict(begin, AGENT_INSTANCE_ID="different-terra")
        self.assertFalse(runtime_guard.RuntimeGuard(dispatch()).audit_job(mismatch)["allowed"])

        for action in ("complete", "abandon"):
            guard = runtime_guard.RuntimeGuard(dispatch())
            self.luna_pass(guard)
            valid_begin = self.audit_packet(guard)
            self.assertTrue(guard.audit_job(valid_begin)["allowed"])
            terminal = {
                "ACTION": action, "PLAN_ID": "p-1", "DISPATCH_ID": "d-1",
                "REVISION": "a" * 40, "AUDITOR_ROLE": "terra_auditor",
                "AUDITOR_INSTANCE_ID": "TERRA-AUDIT-1", "AGENT_INSTANCE_ID": "terra-audit-1",
                "TERMINATION_REASON": "pass" if action == "complete" else "blocked",
            }
            if action == "complete":
                terminal.update(VERIFIED=["acceptance"], UNVERIFIED=[])
            for field in ("AUDITOR_ROLE", "AGENT_INSTANCE_ID"):
                invalid = dict(terminal)
                invalid.pop(field)
                self.assertFalse(guard.audit_job(invalid)["allowed"], (action, field))
            for role in ("parent", "sol_planner"):
                self.assertFalse(guard.audit_job(dict(terminal, AUDITOR_ROLE=role))["allowed"], (action, role))
            self.assertFalse(
                guard.audit_job(dict(terminal, AGENT_INSTANCE_ID="different-terra"))["allowed"], action
            )
            guard.role_leases["terra-audit-1"] = "sol_planner"
            self.assertFalse(guard.audit_job(terminal)["allowed"], (action, "role lease"))
            guard.role_leases["terra-audit-1"] = "terra_auditor"
            result = guard.audit_job(terminal)
            self.assertEqual(result["reason"], "audit_completed" if action == "complete" else "audit_abandoned")

    def test_snapshot_round_trip_preserves_gates(self) -> None:
        guard = runtime_guard.RuntimeGuard(dispatch())
        guard.observe(event(PROGRESS_FINGERPRINT="p"))
        guard.register_repair(self.repair())
        restored = runtime_guard.RuntimeGuard.from_snapshot(guard.snapshot())
        self.assertEqual(restored.snapshot(), guard.snapshot())


if __name__ == "__main__":
    unittest.main()
