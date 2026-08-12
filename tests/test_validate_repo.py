from __future__ import annotations

import itertools
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
        ):
            source = self.source(relative)
            if "luna-worker" in relative:
                source = source.replace(validate_repo.LANGUAGE_RULE, "Language: any")
            self.write(relative, source)
        validate_repo.validate_agents()
        self.assertTrue(any("luna-worker.toml" in e and "language" in e for e in validate_repo.ERRORS))

    def test_runtime_language_ignores_python_bytecode_cache(self) -> None:
        path = validate_repo.ROOT / "agents" / "__pycache__" / "runtime.pyc"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"\xff\x00")
        validate_repo.validate_runtime_language()
        self.assertEqual(validate_repo.ERRORS, [])

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
        }
        self.assertEqual(validate_repo.HANDOFF_ROUTES, expected)
        for route, destination in expected.items():
            self.assertEqual(validate_repo.resolve_handoff_route(*route), destination)
        all_routes = itertools.product(
            ("luna_worker", "terra_auditor", "sol_planner"),
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
            "direct audit": ("launches Terra directly", "No routine Luna-to-Sol-to-Terra hop"),
            "revision": ("worktree-sha256:<64 lowercase hex>", "same state reproduces", "repair changes"),
            "artifacts": ("persistent writes only", "disposable artifact", "never enter revision identity"),
            "fuse": ("MODEL_CALL_LIMIT", "deterministic `spinning` signal", "hard budget"),
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
                "agents/luna-worker.toml", "agents/sol-planner.toml", "agents/terra-auditor.toml"
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
        }
        for path, term in mutations.items():
            validate_repo.ERRORS.clear()
            for other, source in originals.items():
                self.write(other, source.replace(term, "removed", 1) if other == path else source)
            validate_repo.validate_agents()
            self.assertTrue(any(path in error and term in error for error in validate_repo.ERRORS))

    def test_agent_envelope_next_must_be_parent(self) -> None:
        paths = (
            "agents/luna-worker.toml", "agents/sol-planner.toml", "agents/terra-auditor.toml"
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
            "agents/luna-worker.toml", "agents/sol-planner.toml", "agents/terra-auditor.toml"
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

    def test_skill_stays_within_context_budget(self) -> None:
        skill = self.source(".agents/skills/lean-dev-router/SKILL.md")
        self.assertLessEqual(len(skill), 12_000)
        self.assertLessEqual(len(re.findall(r"\b[\w-]+\b", skill)), 1_500)

    def test_runtime_guard_has_required_contract(self) -> None:
        source = self.source(".agents/skills/lean-dev-router/scripts/runtime_guard.py")
        self.write(".agents/skills/lean-dev-router/scripts/runtime_guard.py", source)
        validate_repo.validate_runtime_guard()
        self.assertEqual(validate_repo.ERRORS, [])

        validate_repo.ERRORS.clear()
        self.write(
            ".agents/skills/lean-dev-router/scripts/runtime_guard.py",
            source.replace("duplicate_audit_revision", "removed"),
        )
        validate_repo.validate_runtime_guard()
        self.assertTrue(any("duplicate_audit_revision" in error for error in validate_repo.ERRORS))

    def test_runtime_guard_reports_read_syntax_and_import_errors(self) -> None:
        with mock.patch.object(validate_repo, "read", side_effect=OSError("denied")):
            validate_repo.validate_runtime_guard()
        self.assertTrue(any("cannot read runtime guard" in error for error in validate_repo.ERRORS))

        validate_repo.ERRORS.clear()
        self.write(".agents/skills/lean-dev-router/scripts/runtime_guard.py", "def broken(:\n")
        validate_repo.validate_runtime_guard()
        self.assertTrue(any("invalid Python" in error for error in validate_repo.ERRORS))

        validate_repo.ERRORS.clear()
        self.write(".agents/skills/lean-dev-router/scripts/runtime_guard.py", "import requests\n")
        validate_repo.validate_runtime_guard()
        self.assertTrue(any("requests" in error for error in validate_repo.ERRORS))

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
