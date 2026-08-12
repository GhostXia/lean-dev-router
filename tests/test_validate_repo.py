from __future__ import annotations

import itertools
import re
import tempfile
import unittest
from pathlib import Path

from scripts import validate_repo


class ValidateRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_root = validate_repo.ROOT
        self.original_errors = validate_repo.ERRORS
        self.temporary = tempfile.TemporaryDirectory()
        validate_repo.ROOT = Path(self.temporary.name)
        validate_repo.ERRORS = []

    def tearDown(self) -> None:
        validate_repo.ROOT = self.original_root
        validate_repo.ERRORS = self.original_errors
        self.temporary.cleanup()

    def source(self, relative: str) -> str:
        return (self.original_root / relative).read_text(encoding="utf-8")

    def write(self, relative: str, text: str) -> None:
        path = validate_repo.ROOT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def validate_skill(self, source: str) -> list[str]:
        self.write(".agents/skills/lean-dev-router/SKILL.md", source)
        validate_repo.validate_skill()
        return validate_repo.ERRORS

    def test_runtime_ascii_and_exact_language_rule(self) -> None:
        self.write("agents/runtime.toml", "café\n")
        validate_repo.validate_runtime_language()
        self.assertEqual(len(validate_repo.ERRORS), 1)

        validate_repo.ERRORS.clear()
        for relative in (
            "agents/luna-worker.toml",
            "agents/sol-planner.toml",
            "agents/terra-auditor.toml",
            "agents/terra-planner.toml",
        ):
            source = self.source(relative)
            if "luna-worker" in relative:
                source = source.replace(validate_repo.LANGUAGE_RULE, "Language: any")
            self.write(relative, source)
        validate_repo.validate_agents()
        self.assertTrue(any("luna-worker.toml" in e and "language" in e for e in validate_repo.ERRORS))

    def test_handoff_table_is_closed_and_parent_mechanical(self) -> None:
        expected = {
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
        self.assertEqual(validate_repo.HANDOFF_ROUTES, expected)
        for route, destination in expected.items():
            self.assertEqual(validate_repo.resolve_handoff_route(*route), destination)
        all_routes = itertools.product(
            ("luna_worker", "terra_auditor", "terra_planner", "sol_planner"),
            ("PASS", "BLOCKED", "ESCALATE"),
            ("none", "implementation", "technical_resolution", "planning_resolution", "human_authority"),
        )
        for route in set(all_routes) - set(expected):
            with self.assertRaises(ValueError):
                validate_repo.resolve_handoff_route(*route)

    def test_skill_protocol_and_semantic_contract(self) -> None:
        skill = self.source(".agents/skills/lean-dev-router/SKILL.md")
        self.assertEqual(self.validate_skill(skill), [])
        scenarios = {
            "planning waves": ("PLAN_MANIFEST", "DISPATCH_WAVE", "EXPANSION_GATE", "does not continuously schedule"),
            "direct audit": ("starts the preregistered Terra audit directly", "No routine Luna-to-Sol-to-Terra hop"),
            "revision": ("worktree-sha256:<64 lowercase hex>", "same state reproduces", "repair changes"),
            "artifacts": ("persistent writes only", "disposable artifact", "never enter revision identity"),
            "fuse": ("three materially distinct attempts", "twenty", "unchanged command"),
            "failure routes": ("technical_resolution", "dependency handling", "scope failures", "Baseline drift"),
            "replay": ("cwd, environment delta, exact command, exit code, and compact result",),
            "concurrency": ("prove the target failure/competition branch", "polling or a backstop timeout"),
            "causal audit": ("broader `AUDIT_SCOPE/IMPACT_CONE`", "causal impact cone", "**A**", "**B**", "**C**", "**D**"),
            "repair": ("CONTRACT_EFFECT: unchanged", "AFFECTED_PATHS", "two-cycle repair budget", "returns to Sol"),
            "human": ("REQUEST human_authority", "at most three", "one recommendation", "one question"),
        }
        for terms in scenarios.values():
            for term in terms:
                self.assertIn(term, skill)

    def test_skill_validation_rejects_semantic_anchor_removal(self) -> None:
        original = self.source(".agents/skills/lean-dev-router/SKILL.md")
        for term in (
            "PLAN_MANIFEST", "DISPATCH_WAVE", "EXPANSION_GATE",
            "<component>:<revision>:<stage>", "worktree-sha256:<64 lowercase hex>",
            "CONTRACT_EFFECT: unchanged", "parent:repair_or_sol",
        ):
            validate_repo.ERRORS.clear()
            errors = self.validate_skill(original.replace(term, "removed", 1))
            self.assertTrue(any(term in error for error in errors), term)

    def test_protocol_rejects_missing_request_and_illegal_route(self) -> None:
        original = self.source(".agents/skills/lean-dev-router/SKILL.md")
        without_request = original.replace(
            "REQUEST: none | implementation | technical_resolution | planning_resolution | human_authority\n",
            "", 1,
        )
        self.assertTrue(any("outbound protocol" in e for e in self.validate_skill(without_request)))

        validate_repo.ERRORS.clear()
        illegal = original.replace(
            "| `luna_worker` | `ESCALATE` | `technical_resolution` | `parent:terra` |",
            "| `luna_worker` | `ESCALATE` | `human_authority` | `parent:user` |",
        )
        self.assertTrue(any("illegal handoff" in e for e in self.validate_skill(illegal)))

    def test_dispatch_id_must_be_present_and_non_empty(self) -> None:
        original = self.source(".agents/skills/lean-dev-router/SKILL.md")
        for replacement in ("", "DISPATCH_ID:\n"):
            validate_repo.ERRORS.clear()
            changed = original.replace(
                "DISPATCH_ID: stable unique component/write identifier\n",
                replacement,
                1,
            )
            errors = self.validate_skill(changed)
            self.assertTrue(any("DISPATCH_ID" in error for error in errors))

    def test_agent_profiles_preserve_role_boundaries(self) -> None:
        originals = {
            path: self.source(path) for path in (
                "agents/luna-worker.toml", "agents/sol-planner.toml", "agents/terra-auditor.toml",
                "agents/terra-planner.toml",
            )
        }
        for path, source in originals.items():
            self.write(path, source)
        validate_repo.validate_agents()
        self.assertEqual(validate_repo.ERRORS, [])

        mutations = {
            "agents/sol-planner.toml": "EXPANSION_GATE",
            "agents/luna-worker.toml": "scripts/check_scope.py",
            "agents/terra-auditor.toml": "CONTRACT_EFFECT: unchanged",
            "agents/terra-planner.toml": "finite manifest",
        }
        for path, term in mutations.items():
            validate_repo.ERRORS.clear()
            for other, source in originals.items():
                self.write(other, source.replace(term, "removed", 1) if other == path else source)
            validate_repo.validate_agents()
            self.assertTrue(any(path in error and term in error for error in validate_repo.ERRORS))

    def test_agent_envelope_next_must_be_parent(self) -> None:
        paths = (
            "agents/luna-worker.toml", "agents/sol-planner.toml", "agents/terra-auditor.toml",
            "agents/terra-planner.toml",
        )
        for target in paths:
            validate_repo.ERRORS.clear()
            for path in paths:
                source = self.source(path)
                if path == target:
                    marker = "NEXT: parent | SUMMARY"
                    self.assertIn(marker, source)
                    source = source.replace(marker, "NEXT: sol_planner | SUMMARY", 1)
                self.write(path, source)
            validate_repo.validate_agents()
            self.assertTrue(
                any(target in error and "envelope NEXT" in error for error in validate_repo.ERRORS)
            )

    def test_pre_pass_technical_resolution_route_is_complete(self) -> None:
        luna = self.source("agents/luna-worker.toml")
        terra = self.source("agents/terra-auditor.toml")
        self.assertEqual(
            validate_repo.resolve_handoff_route(
                "luna_worker", "ESCALATE", "technical_resolution"
            ),
            "parent:terra",
        )
        for term in ("pre-PASS route", "current diff/paths", "exact failure/replay"):
            self.assertIn(term, luna)
        for term in (
            "does not require final scope or revision",
            "ESCALATE/planning_resolution",
            "never BLOCKED/none",
        ):
            self.assertIn(term, terra)

    def test_worker_authority_boundaries_are_required(self) -> None:
        paths = (
            "agents/luna-worker.toml", "agents/sol-planner.toml", "agents/terra-auditor.toml",
            "agents/terra-planner.toml",
        )
        boundaries = {
            "agents/luna-worker.toml": (
                "Never plan the task, authorize writes, schedule peers, or request human authority.",
                "Never plan the task, authorize writes, or request human authority.",
            ),
            "agents/terra-auditor.toml": (
                "Never edit, authorize a write, schedule peers, or request human authority.",
                "Never edit or request human authority.",
            ),
            "agents/terra-planner.toml": (
                "Never write, schedule, wait, amend after execution, audit, or request human_authority.",
                "Never write or request human_authority.",
            ),
        }
        for target, (required, weakened) in boundaries.items():
            validate_repo.ERRORS.clear()
            for path in paths:
                source = self.source(path)
                if path == target:
                    self.assertIn(required, source)
                    source = source.replace(required, weakened, 1)
                self.write(path, source)
            validate_repo.validate_agents()
            self.assertTrue(any(target in error and required in error for error in validate_repo.ERRORS))

    def test_terra_planner_eligibility_is_exact_and_routes_directly_to_sol(self) -> None:
        contract = {
            "LEVEL": "L2",
            "OBJECTIVE_FIXED": True,
            "BASELINE": "abc123",
            "SCOPE_ROOTS": ["src", "tests"],
            "ACCEPTANCE": ["python -m unittest"],
            "OPEN_MAJOR_DECISIONS": False,
            "RISK_FLAGS": None,
            "EXTERNAL_ACTIONS": [],
            "MAX_DISPATCHES": 1,
            "COMPONENT_COUNT": 2,
            "DEPENDENCY_DEPTH": 1,
            "PATHS_ALLOW": ["src/service.py"],
            "REQUIRED_PATHS": ["src/service.py"],
            "WRITE_BATCH_COUNT": 1,
            "CONTRACT_EXPANDED": False,
            "AMBIGUITY": False,
        }
        self.assertTrue(validate_repo.is_terra_planner_eligible(contract))
        self.assertEqual(validate_repo.route_planner(contract), "terra_planner")

        checks = {
            "LEVEL": "L3",
            "OBJECTIVE_FIXED": False,
            "BASELINE": "",
            "SCOPE_ROOTS": [],
            "ACCEPTANCE": "",
            "OPEN_MAJOR_DECISIONS": True,
            "EXTERNAL_ACTIONS": ["network"],
            "MAX_DISPATCHES": 2,
            "COMPONENT_COUNT": 3,
            "DEPENDENCY_DEPTH": 2,
            "REQUIRED_PATHS": ["outside/file.py"],
            "WRITE_BATCH_COUNT": 2,
            "CONTRACT_EXPANDED": True,
            "AMBIGUITY": True,
        }
        for field, value in checks.items():
            changed = dict(contract)
            changed[field] = value
            self.assertFalse(validate_repo.is_terra_planner_eligible(changed), field)
            self.assertEqual(validate_repo.route_planner(changed), "sol_planner", field)
        for risk in validate_repo.TERRA_RISK_FLAGS:
            changed = dict(contract, RISK_FLAGS=[risk])
            self.assertFalse(validate_repo.is_terra_planner_eligible(changed), risk)

        for field in (
            "REQUIRED_PATHS",
            "WRITE_BATCH_COUNT",
            "CONTRACT_EXPANDED",
            "AMBIGUITY",
        ):
            omitted = dict(contract)
            omitted.pop(field)
            self.assertFalse(validate_repo.is_terra_planner_eligible(omitted), field)
            self.assertEqual(validate_repo.route_planner(omitted), "sol_planner", field)

    def test_plan_identity_and_immutable_role_leases(self) -> None:
        plan = {
            "PLAN_ID": "plan-1",
            "PLANNER_ROLE": "terra_planner",
            "PLANNER_INSTANCE_ID": "planner-a",
            "AUDITOR_INSTANCE_ID": "auditor-b",
        }
        self.assertEqual(validate_repo.validate_plan_identity(plan), [])
        self.assertIn(
            "AUDITOR_INSTANCE_ID must differ from PLANNER_INSTANCE_ID",
            validate_repo.validate_plan_identity(dict(plan, AUDITOR_INSTANCE_ID="planner-a")),
        )
        registry = validate_repo.RoleLeaseRegistry()
        self.assertTrue(registry.record_planned("plan-1", "planner-a", "terra_planner"))
        self.assertFalse(registry.lease("plan-1", "planner-a", "sol_planner"))
        self.assertFalse(registry.record_implemented("plan-1", "planner-a", "luna_worker"))
        self.assertTrue(registry.record_implemented("plan-1", "worker-a", "luna_worker"))
        self.assertFalse(registry.record_planned("plan-1", "worker-a", "terra_planner"))
        self.assertTrue(registry.record_audited("plan-1", "auditor-c", "terra_auditor"))
        self.assertTrue(registry.validate_audit("plan-1", "planner-a", "auditor-c"))
        self.assertFalse(registry.record_audited("plan-1", "worker-a", "terra_auditor"))
        self.assertFalse(registry.validate_audit("plan-1", "planner-a", "planner-a"))
        self.assertFalse(registry.validate_audit("plan-1", "planner-a", "worker-a"))
        self.assertTrue(registry.validate_audit("plan-1", "planner-a", "auditor-b"))
        self.assertEqual(validate_repo.validate_role_independence(plan, lease_registry=registry), [])
        self.assertTrue(
            validate_repo.validate_role_independence(
                dict(plan, AUDITOR_INSTANCE_ID="worker-a"), lease_registry=registry
            )
        )

    def test_luna_dispatch_validates_terra_planner_authority(self) -> None:
        dispatch = {
            "DISPATCH_ID": "dispatch-1",
            "PLANNER_ROLE": "terra_planner",
            "PLAN_ID": "plan-1",
            "PLANNER_INSTANCE_ID": "planner-a",
            "AUDITOR_INSTANCE_ID": "auditor-b",
            "LEVEL": "L1",
            "OBJECTIVE_FIXED": True,
            "BASELINE": "abc123",
            "SCOPE_ROOTS": ["src"],
            "ACCEPTANCE": "python -m unittest",
            "OPEN_MAJOR_DECISIONS": False,
            "RISK_FLAGS": "none",
            "EXTERNAL_ACTIONS": "none",
            "MAX_DISPATCHES": 1,
            "COMPONENT_COUNT": 1,
            "DEPENDENCY_DEPTH": 0,
            "PATHS_ALLOW": ["src/service.py"],
            "REQUIRED_PATHS": [],
            "WRITE_BATCH_COUNT": 1,
            "CONTRACT_EXPANDED": False,
            "AMBIGUITY": False,
        }
        self.assertEqual(validate_repo.validate_dispatch_identity(dispatch), [])
        invalid = dict(dispatch, PLANNER_INSTANCE_ID="auditor-b")
        self.assertTrue(validate_repo.validate_dispatch_identity(invalid))
        missing_auditor = dict(dispatch)
        missing_auditor.pop("AUDITOR_INSTANCE_ID")
        self.assertTrue(validate_repo.validate_dispatch_identity(missing_auditor))

        malformed_scope_cases = (
            dict(dispatch, PATHS_ALLOW=["outside/write.py"]),
            dict(dispatch, REQUIRED_PATHS=True),
            dict(dispatch, SCOPE_ROOTS=1),
        )
        for malformed in malformed_scope_cases:
            self.assertFalse(validate_repo.is_terra_planner_eligible(malformed))
            self.assertEqual(validate_repo.route_planner(malformed), "sol_planner")
            self.assertTrue(validate_repo.validate_dispatch_identity(malformed))

        registry = validate_repo.RoleLeaseRegistry()
        self.assertTrue(registry.record_planned("plan-1", "planner-a", "terra_planner"))
        self.assertEqual(
            validate_repo.validate_dispatch_identity(dispatch, lease_registry=registry), []
        )
        self.assertTrue(registry.record_implemented("plan-1", "worker-a", "luna_worker"))
        reused_auditor = dict(dispatch, AUDITOR_INSTANCE_ID="worker-a")
        self.assertTrue(
            validate_repo.validate_dispatch_identity(
                reused_auditor, lease_registry=registry
            )
        )
        sol_dispatch = {
            "DISPATCH_ID": "dispatch-2",
            "PLANNER_ROLE": "sol_planner",
            "PLAN_ID": "plan-2",
            "PLANNER_INSTANCE_ID": "sol-a",
            "AUDITOR_INSTANCE_ID": "auditor-d",
        }
        self.assertEqual(validate_repo.validate_dispatch_identity(sol_dispatch), [])
        sol_dispatch.pop("AUDITOR_INSTANCE_ID")
        self.assertTrue(validate_repo.validate_dispatch_identity(sol_dispatch))

    def test_skill_stays_within_context_budget(self) -> None:
        skill = self.source(".agents/skills/lean-dev-router/SKILL.md")
        self.assertLessEqual(len(skill), 12_000)
        self.assertLessEqual(len(re.findall(r"\b[\w-]+\b", skill)), 1_500)

    def test_four_backtick_fence_wraps_shorter_fence(self) -> None:
        self.assertEqual(
            validate_repo.markdown_lines("````\n```\ninside\n````\noutside\n"),
            [(5, "outside")],
        )

    def test_missing_license_is_reported_without_traceback(self) -> None:
        validate_repo.validate_license()
        self.assertEqual(len(validate_repo.ERRORS), 1)
        self.assertIn("cannot read required file", validate_repo.ERRORS[0])


if __name__ == "__main__":
    unittest.main()
