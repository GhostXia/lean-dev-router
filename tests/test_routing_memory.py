from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MEMORY_PATH = ROOT / ".agents/skills/lean-dev-router/scripts/routing_memory.py"
SPEC = importlib.util.spec_from_file_location("routing_memory", MEMORY_PATH)
assert SPEC and SPEC.loader
routing_memory = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = routing_memory
SPEC.loader.exec_module(routing_memory)


def context(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "TASK_ID": "task-1",
        "DIMENSION": "bug-fix",
        "LANGUAGE": "python",
        "LEVEL": "L2",
        "TAGS": ["runtime", "cli"],
        "POLICY_VERSION": "ldr-v2.1",
        "ELIGIBLE_ACTIONS": ["parent:fast_path", "parent:sol"],
        "DEFAULT_ACTION": "parent:fast_path",
        "PERFORMANCE_WEIGHT": 1.0,
        "COST_WEIGHT": 0.1,
        "COST_SCALE_USD": 1.0,
    }
    value.update(overrides)
    return value


def feedback(decision: dict[str, object], **overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "DECISION_ID": decision["decision_id"],
        "ACTION": decision["action"],
        "OUTCOME": "pass",
        "VERIFIED": True,
        "SCORE": 1.0,
        "COST_USD": 0.2,
        "TOTAL_TOKENS": 1000,
        "MODEL_ACTIVE_SECONDS": 10.0,
        "EVIDENCE_FINGERPRINT": "evidence-1",
    }
    value.update(overrides)
    return value


class RoutingMemoryTests(unittest.TestCase):
    def complete(
        self, memory: dict[str, object], packet: dict[str, object], **result: object
    ) -> dict[str, object]:
        decision = routing_memory.decide(memory, packet)
        self.assertTrue(decision["allowed"])
        recorded = routing_memory.record_feedback(memory, feedback(decision, **result))
        self.assertTrue(recorded["allowed"])
        return decision

    def test_cold_start_uses_only_the_declared_default(self) -> None:
        memory = routing_memory.empty_memory()
        decision = routing_memory.decide(memory, context(RAW_PROMPT="private source text"))
        self.assertTrue(decision["allowed"])
        self.assertTrue(decision["advisory"])
        self.assertEqual(decision["action"], "parent:fast_path")
        self.assertEqual(decision["reason"], "cold_start")
        self.assertEqual(decision["authority"], "eligible_actions_only")
        self.assertEqual(memory["decisions"][0]["status"], "pending")
        self.assertEqual(memory["decisions"][0]["selector"]["min_samples"], 3)
        self.assertIn("parent:fast_path", memory["decisions"][0]["stats"])
        self.assertNotIn("raw_prompt", memory["decisions"][0]["context"])

    def test_verified_feedback_is_required_and_duplicate_is_rejected(self) -> None:
        memory = routing_memory.empty_memory()
        decision = routing_memory.decide(memory, context())
        rejected = routing_memory.record_feedback(memory, feedback(decision, VERIFIED=False))
        self.assertFalse(rejected["allowed"])
        self.assertEqual(memory["decisions"][0]["status"], "pending")
        accepted = routing_memory.record_feedback(memory, feedback(decision))
        self.assertTrue(accepted["allowed"])
        duplicate = routing_memory.record_feedback(memory, feedback(decision))
        self.assertEqual(duplicate["reason"], "duplicate_feedback")

    def test_memory_switches_only_after_both_actions_have_enough_evidence(self) -> None:
        memory = routing_memory.empty_memory()
        for index in range(3):
            self.complete(
                memory,
                context(TASK_ID=f"fast-{index}"),
                OUTCOME="failed",
                SCORE=1.0,
                COST_USD=0.1,
                EVIDENCE_FINGERPRINT=f"fast-{index}",
            )
        unsupported_default = routing_memory.decide(
            memory,
            context(TASK_ID="sol-0", DEFAULT_ACTION="parent:sol"),
        )
        self.assertEqual(unsupported_default["action"], "parent:sol")
        self.assertEqual(unsupported_default["reason"], "insufficient_default_evidence")
        self.assertTrue(
            routing_memory.record_feedback(
                memory, feedback(unsupported_default, EVIDENCE_FINGERPRINT="sol-0")
            )["allowed"]
        )
        for index in range(1, 3):
            self.complete(
                memory,
                context(TASK_ID=f"sol-{index}", DEFAULT_ACTION="parent:sol"),
                EVIDENCE_FINGERPRINT=f"sol-{index}",
            )
        learned = routing_memory.decide(memory, context(TASK_ID="learned"))
        self.assertEqual(learned["action"], "parent:sol")
        self.assertEqual(learned["reason"], "memory_advantage")
        self.assertEqual(learned["stats"]["parent:fast_path"]["mean_score"], 0.0)

    def test_cost_weight_breaks_equal_performance_toward_cheaper_action(self) -> None:
        memory = routing_memory.empty_memory()
        for index in range(3):
            self.complete(
                memory,
                context(TASK_ID=f"fast-cost-{index}"),
                COST_USD=0.9,
                EVIDENCE_FINGERPRINT=f"fast-cost-{index}",
            )
        for index in range(3):
            self.complete(
                memory,
                context(TASK_ID=f"sol-cost-{index}", DEFAULT_ACTION="parent:sol"),
                COST_USD=0.1,
                EVIDENCE_FINGERPRINT=f"sol-cost-{index}",
            )
        learned = routing_memory.decide(memory, context(TASK_ID="cost-choice"))
        self.assertEqual(learned["action"], "parent:sol")
        self.assertGreater(
            learned["stats"]["parent:sol"]["mean_utility"],
            learned["stats"]["parent:fast_path"]["mean_utility"],
        )

    def test_policy_versions_do_not_share_feedback(self) -> None:
        memory = routing_memory.empty_memory()
        for index in range(3):
            self.complete(
                memory,
                context(TASK_ID=f"old-{index}", DEFAULT_ACTION="parent:sol"),
                EVIDENCE_FINGERPRINT=f"old-{index}",
            )
        isolated = routing_memory.decide(
            memory, context(TASK_ID="new", POLICY_VERSION="ldr-v3")
        )
        self.assertEqual(isolated["reason"], "cold_start")
        self.assertEqual(isolated["action"], "parent:fast_path")

    def test_dimensions_do_not_share_feedback(self) -> None:
        memory = routing_memory.empty_memory()
        for index in range(3):
            self.complete(
                memory,
                context(TASK_ID=f"bug-{index}", DEFAULT_ACTION="parent:sol"),
                EVIDENCE_FINGERPRINT=f"bug-{index}",
            )
        isolated = routing_memory.decide(
            memory, context(TASK_ID="feature", DIMENSION="feature")
        )
        self.assertEqual(isolated["reason"], "cold_start")
        self.assertEqual(isolated["stats"]["parent:sol"]["samples"], 0)

    def test_memory_never_selects_an_action_outside_eligibility(self) -> None:
        memory = routing_memory.empty_memory()
        decision = routing_memory.decide(
            memory,
            context(ELIGIBLE_ACTIONS=["parent:sol"], DEFAULT_ACTION="parent:sol"),
        )
        self.assertEqual(decision["action"], "parent:sol")
        invalid = routing_memory.decide(
            memory,
            context(ELIGIBLE_ACTIONS=["parent:sol"], DEFAULT_ACTION="parent:fast_path"),
        )
        self.assertFalse(invalid["allowed"])

        too_many_tags = routing_memory.decide(
            memory, context(TAGS=[f"tag-{index}" for index in range(17)])
        )
        self.assertFalse(too_many_tags["allowed"])

    def test_completed_evidence_cannot_be_reused(self) -> None:
        memory = routing_memory.empty_memory()
        first = routing_memory.decide(memory, context(TASK_ID="one"))
        self.assertTrue(
            routing_memory.record_feedback(
                memory, feedback(first, EVIDENCE_FINGERPRINT="same-evidence")
            )["allowed"]
        )
        second = routing_memory.decide(memory, context(TASK_ID="two"))
        repeated = routing_memory.record_feedback(
            memory, feedback(second, EVIDENCE_FINGERPRINT="same-evidence")
        )
        self.assertFalse(repeated["allowed"])
        self.assertTrue(any("must not repeat" in error for error in repeated["errors"]))

    def test_capacity_evicts_completed_but_never_pending_decisions(self) -> None:
        memory = routing_memory.empty_memory(capacity=2)
        first = self.complete(memory, context(TASK_ID="one"), EVIDENCE_FINGERPRINT="one")
        second = self.complete(memory, context(TASK_ID="two"), EVIDENCE_FINGERPRINT="two")
        third = routing_memory.decide(memory, context(TASK_ID="three"))
        self.assertTrue(third["allowed"])
        self.assertNotIn(first["decision_id"], {item["decision_id"] for item in memory["decisions"]})
        self.assertIn(second["decision_id"], {item["decision_id"] for item in memory["decisions"]})

        pending = routing_memory.empty_memory(capacity=1)
        self.assertTrue(routing_memory.decide(pending, context())["allowed"])
        blocked = routing_memory.decide(pending, context(TASK_ID="other"))
        self.assertEqual(blocked["reason"], "memory_capacity_pending")

    def test_cli_persists_decision_and_feedback_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            memory_path = Path(directory) / "routing-memory.json"
            decided = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(MEMORY_PATH),
                    "decide",
                    "--memory",
                    str(memory_path),
                ],
                input=json.dumps(context()),
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(decided.returncode, 0, decided.stderr)
            decision = json.loads(decided.stdout)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(MEMORY_PATH),
                    "feedback",
                    "--memory",
                    str(memory_path),
                ],
                input=json.dumps(feedback(decision)),
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertFalse(memory_path.with_name(memory_path.name + ".tmp").exists())
            stored = json.loads(memory_path.read_text(encoding="utf-8"))
            self.assertEqual(stored["decisions"][0]["status"], "completed")

    def test_cli_rejects_corrupt_memory_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            memory_path = Path(directory) / "routing-memory.json"
            memory_path.write_text('{"protocol":"wrong"}', encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(MEMORY_PATH),
                    "snapshot",
                    "--memory",
                    str(memory_path),
                ],
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stderr, "")
            self.assertEqual(json.loads(result.stdout)["reason"], "invalid_input")

    def test_schema_exposes_resource_ceilings(self) -> None:
        result = subprocess.run(
            [sys.executable, "-B", str(MEMORY_PATH), "schema"],
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        schema = json.loads(result.stdout)
        self.assertEqual(schema["max_capacity"], 20000)
        self.assertEqual(schema["max_packet_bytes"], 65536)


if __name__ == "__main__":
    unittest.main()
