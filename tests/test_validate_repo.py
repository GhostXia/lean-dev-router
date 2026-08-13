from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from scripts import validate_repo


def parent_contract() -> dict[str, object]:
    return {
        "PLANNER_ROLE": "parent",
        "PLANNER_CAPABILITY": "bounded_l1_l2_dispatch",
        "PLAN_ID": "plan-1",
        "DISPATCH_ID": "dispatch-1",
        "PLANNER_INSTANCE_ID": "parent-1",
        "AUDITOR_INSTANCE_ID": "auditor-1",
        "LEVEL": "L1",
        "OBJECTIVE_FIXED": True,
        "BASELINE": "a" * 40,
        "SCOPE_ROOTS": ["src"],
        "ACCEPTANCE": ["focused test passes"],
        "CONSTRAINTS": ["one component"],
        "OPEN_MAJOR_DECISIONS": False,
        "RISK_FLAGS": "none",
        "EXTERNAL_ACTIONS": "none",
        "MAX_DISPATCHES": 1,
        "COMPONENT_COUNT": 1,
        "DEPENDENCY_DEPTH": 0,
        "PATHS_ALLOW": ["src/service.py"],
        "REQUIRED_PATHS": ["src/service.py"],
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
        "BUDGET": {
            "MODEL_CALL_LIMIT": 4,
            "HYPOTHESIS_LIMIT": 2,
            "MODEL_ACTIVE_SECONDS_LIMIT": 600,
            "REPAIR_CYCLE_LIMIT": 1,
            "STAGNANT_CALL_LIMIT": 1,
        },
    }


class ValidatorContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = validate_repo.ROOT
        self.errors = validate_repo.ERRORS
        validate_repo.ERRORS = []

    def tearDown(self) -> None:
        validate_repo.ROOT = self.root
        validate_repo.ERRORS = self.errors

    def copy_fixture(self, directory: str, *relative_paths: str) -> Path:
        fixture_root = Path(directory)
        for relative in relative_paths:
            source = self.root / relative
            target = fixture_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        validate_repo.ROOT = fixture_root
        return fixture_root

    def test_parent_fast_path_accepts_strict_l1_and_routes_failures_to_sol(self) -> None:
        contract = parent_contract()
        self.assertTrue(validate_repo.is_parent_fast_path_eligible(contract))
        self.assertEqual(validate_repo.route_planner(contract), "parent")
        for field in validate_repo.PARENT_CHANGE_FIELDS:
            for value in (None, "none", ["none"], True):
                changed = dict(contract, **{field: value})
                self.assertFalse(validate_repo.is_parent_fast_path_eligible(changed), (field, value))
                self.assertEqual(validate_repo.route_planner(changed), "sol_planner", (field, value))

        non_change_none = dict(
            contract,
            RISK_FLAGS=None,
            EXTERNAL_ACTIONS=["none"],
            INTEGRATION="none",
            CONFLICT=None,
            CONTRACT_EXPANDED=["none"],
        )
        self.assertTrue(validate_repo.is_parent_fast_path_eligible(non_change_none))
        for field, value in {
            "LEVEL": "L3",
            "RISK_FLAGS": ["security"],
            "COMPONENT_COUNT": 2,
            "DEPENDENCY_DEPTH": 1,
            "INTEGRATION": True,
            "AMBIGUITY": True,
            "CONSTRAINTS": [],
            "PATHS_ALLOW": ["outside/file.py"],
        }.items():
            changed = dict(contract, **{field: value})
            self.assertFalse(validate_repo.is_parent_fast_path_eligible(changed), field)
            self.assertEqual(validate_repo.route_planner(changed), "sol_planner", field)

    def test_parent_predicate_requires_explicit_evidence(self) -> None:
        contract = parent_contract()
        for field in validate_repo.PARENT_FAST_PATH_FIELDS:
            changed = dict(contract)
            changed.pop(field, None)
            self.assertFalse(validate_repo.is_parent_fast_path_eligible(changed), field)

    def test_parent_predicate_routes_runtime_guard_mismatches_to_sol(self) -> None:
        contract = parent_contract()
        self.assertEqual(validate_repo.route_planner(contract), "parent")
        for changed, label in (
            (dict(contract, PLANNER_ROLE="sol_planner"), "sol_planner role"),
            (dict(contract, BASELINE="not-a-git-sha"), "invalid baseline"),
            (
                dict(contract, BUDGET=dict(contract["BUDGET"], MODEL_CALL_LIMIT=5)),
                "parent call ceiling",
            ),
        ):
            self.assertEqual(validate_repo.route_planner(changed), "sol_planner", label)

    def test_identity_collision_and_auditor_independence(self) -> None:
        plan = parent_contract()
        self.assertEqual(validate_repo.validate_plan_identity(plan), [])
        self.assertTrue(validate_repo.validate_plan_identity(dict(plan, AUDITOR_INSTANCE_ID="parent-1")))
        self.assertTrue(validate_repo.validate_plan_identity(dict(plan, AUDITOR_INSTANCE_ID="PARENT-1")))
        self.assertTrue(validate_repo.validate_plan_identity(dict(plan, AUDITOR_INSTANCE_ID="parent")))
        leases = validate_repo.RoleLeaseRegistry()
        self.assertTrue(leases.record_planned("plan-1", "parent-1", "parent"))
        self.assertTrue(leases.record_audited("plan-1", "auditor-1"))
        self.assertTrue(leases.validate_audit("plan-1", "parent-1", "auditor-1"))
        self.assertFalse(leases.validate_audit("plan-1", "parent-1", "parent-1"))

    def test_dispatch_identity_allows_sol_and_strict_parent_only(self) -> None:
        sol = {
            "PLAN_ID": "p", "PLANNER_ROLE": "sol_planner", "PLANNER_INSTANCE_ID": "s",
            "AUDITOR_INSTANCE_ID": "a", "DISPATCH_ID": "d",
        }
        self.assertEqual(validate_repo.validate_dispatch_identity(sol), [])
        self.assertEqual(validate_repo.validate_dispatch_identity(parent_contract()), [])
        self.assertTrue(validate_repo.validate_dispatch_identity(dict(parent_contract(), PLANNER_CAPABILITY="other")))

    def test_repository_validator_passes_and_retired_profile_is_absent(self) -> None:
        validate_repo.validate_agents()
        validate_repo.validate_skill()
        validate_repo.validate_runtime_guard()
        validate_repo.validate_manifest()
        validate_repo.validate_runtime_language()
        validate_repo.validate_markdown()
        validate_repo.validate_repository_contract()
        self.assertEqual(validate_repo.ERRORS, [], "\n".join(validate_repo.ERRORS))
        self.assertFalse((validate_repo.ROOT / "agents/terra-planner.toml").exists())

    def test_validate_agents_rejects_wrong_model(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_fixture(
                directory,
                "agents/luna-worker.toml",
                "agents/sol-planner.toml",
                "agents/terra-auditor.toml",
            )
            luna = root / "agents/luna-worker.toml"
            luna.write_text(
                luna.read_text(encoding="utf-8").replace(
                    'model = "gpt-5.6-luna"', 'model = "gpt-5.6-terra"'
                ),
                encoding="utf-8",
            )
            validate_repo.validate_agents()
            self.assertTrue(any("expected model='gpt-5.6-luna'" in item for item in validate_repo.ERRORS))

    def test_validate_skill_rejects_canonical_variant_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = (
                ".agents/skills/lean-dev-router/SKILL.md",
                "skill-variants/en/SKILL.md",
                "skill-variants/zhcn/SKILL.md",
                "skill-variants/en-optimized/SKILL.md",
                "skill-variants/zhcn-optimized/SKILL.md",
            )
            root = self.copy_fixture(directory, *paths)
            canonical = root / paths[0]
            canonical.write_text(
                canonical.read_text(encoding="utf-8") + "\nfixture drift\n",
                encoding="utf-8",
            )
            validate_repo.validate_skill()
            self.assertTrue(any("must exactly match" in item for item in validate_repo.ERRORS))

    def test_validate_handoff_table_rejects_missing_routes(self) -> None:
        validate_repo.validate_handoff_table(
            "fixture.md",
            "| `luna_worker` | `PASS` | `none` | `parent:manifest_gate` |",
        )
        self.assertTrue(any("missing handoff route" in item for item in validate_repo.ERRORS))

    def test_validate_markdown_reports_opening_fence_line(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "broken.md").write_text("heading\n\n```text\nunclosed\n", encoding="utf-8")
            validate_repo.ROOT = root
            validate_repo.validate_markdown()
            self.assertIn("broken.md:3: unclosed Markdown code fence", validate_repo.ERRORS)

    def test_validate_license_rejects_non_mit_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "LICENSE").write_text("not the expected license\n", encoding="utf-8")
            validate_repo.ROOT = root
            validate_repo.validate_license()
            self.assertIn("LICENSE: expected MIT license text", validate_repo.ERRORS)

    def test_runtime_language_ignores_bytecode_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original = validate_repo.ROOT
            validate_repo.ROOT = Path(directory)
            cache = Path(directory) / "agents" / "__pycache__"
            cache.mkdir(parents=True)
            (cache / "x.pyc").write_bytes(b"\xff")
            validate_repo.validate_runtime_language()
            self.assertEqual(validate_repo.ERRORS, [])
            validate_repo.ROOT = original


if __name__ == "__main__":
    unittest.main()
