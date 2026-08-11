from __future__ import annotations

import itertools
import re
import tempfile
import tomllib
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

    def write(self, relative: str, text: str) -> None:
        path = validate_repo.ROOT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def validate_skill_source(self, source: str) -> list[str]:
        self.write(".agents/skills/lean-dev-router/SKILL.md", source)
        validate_repo.validate_skill()
        return validate_repo.ERRORS

    def test_runtime_files_require_ascii_and_agent_language_rule_is_exact(self) -> None:
        self.write(".agents/runtime.txt", "ASCII only\n")
        self.write("agents/runtime.toml", "café\n")

        validate_repo.validate_runtime_language()

        self.assertEqual(
            validate_repo.ERRORS,
            [
                "agents/runtime.toml:1: non-ASCII text is not allowed in runtime files",
            ],
        )

        validate_repo.ERRORS.clear()
        for relative in (
            "agents/luna-worker.toml",
            "agents/sol-planner.toml",
            "agents/terra-auditor.toml",
        ):
            source = (self.original_root / relative).read_text(encoding="utf-8")
            if relative.endswith("luna-worker.toml"):
                source = source.replace(validate_repo.LANGUAGE_RULE, "Language: any language")
            self.write(relative, source)

        validate_repo.validate_agents()

        language_errors = [
            message
            for message in validate_repo.ERRORS
            if "English language rule" in message
        ]
        self.assertEqual(len(language_errors), 1)
        self.assertIn("luna-worker.toml", language_errors[0])

    def test_workers_require_complete_protocol_without_peer_knowledge(self) -> None:
        agent_paths = (
            "agents/luna-worker.toml",
            "agents/sol-planner.toml",
            "agents/terra-auditor.toml",
        )
        originals = {
            relative: (self.original_root / relative).read_text(encoding="utf-8")
            for relative in agent_paths
        }

        for required, replacement in (
            ("PROTOCOL: lean-dev-router/v2", "PROTOCOL: other/v2"),
            ("`TASK_SUMMARY`", "`TASK`"),
            ("NEXT: parent", "NEXT: none"),
        ):
            with self.subTest(required=required):
                validate_repo.ERRORS.clear()
                for relative, source in originals.items():
                    if relative.endswith("luna-worker.toml"):
                        source = source.replace(required, replacement, 1)
                    self.write(relative, source)

                validate_repo.validate_agents()

                self.assertTrue(
                    any(
                        "luna-worker.toml" in message and required.strip("`") in message
                        for message in validate_repo.ERRORS
                    )
                )

        validate_repo.ERRORS.clear()
        for role, peer, expected in (
            ("luna-worker.toml", "terra_auditor", "Luna instructions must not name terra"),
            ("terra-auditor.toml", "luna_worker", "Terra instructions must not name luna"),
        ):
            with self.subTest(role=role, peer=peer):
                validate_repo.ERRORS.clear()
                for relative, source in originals.items():
                    if relative.endswith(role):
                        source = source.replace(
                            'description = "', f'description = "Ask {peer}; ', 1
                        )
                    self.write(relative, source)

                validate_repo.validate_agents()

                self.assertTrue(
                    any(expected in message for message in validate_repo.ERRORS)
                )

        validate_repo.ERRORS.clear()
        for relative, source in originals.items():
            if relative.endswith("luna-worker.toml"):
                source = source.replace("PROTOCOL, AGENT, STATUS, FAILURE, REQUEST", "PROTOCOL, AGENT, STATUS, FAILURE")
            self.write(relative, source)

        validate_repo.validate_agents()

        self.assertTrue(any("REQUEST" in message for message in validate_repo.ERRORS))

    def test_four_backtick_fence_wraps_shorter_backtick_fence(self) -> None:
        text = "````\n```\ninside\n````\noutside\n"

        self.assertEqual(validate_repo.markdown_lines(text), [(5, "outside")])

        self.write("nested.md", text)
        validate_repo.validate_markdown()

        self.assertEqual(validate_repo.ERRORS, [])

    def test_handoff_route_table_accepts_only_legal_combinations(self) -> None:
        expected = {
            ("luna_worker", "PASS", "none"): "current_coordinator",
            ("luna_worker", "BLOCKED", "none"): "current_coordinator",
            ("luna_worker", "ESCALATE", "technical_resolution"): "terra_auditor",
            ("terra_auditor", "PASS", "none"): "current_coordinator",
            ("terra_auditor", "BLOCKED", "none"): "current_coordinator",
            ("terra_auditor", "ESCALATE", "implementation"): "sol_planner",
            ("terra_auditor", "ESCALATE", "planning_resolution"): "sol_planner",
            ("sol_planner", "PASS", "none"): "current_coordinator",
            ("sol_planner", "BLOCKED", "none"): "current_coordinator",
            ("sol_planner", "BLOCKED", "implementation"): "luna_worker",
            ("sol_planner", "BLOCKED", "human_authority"): "user",
        }
        self.assertEqual(validate_repo.LEGAL_HANDOFFS, set(expected))
        for handoff, destination in expected.items():
            with self.subTest(handoff=handoff):
                self.assertEqual(
                    validate_repo.resolve_handoff_route(*handoff), destination
                )

        combinations = itertools.product(
            ("luna_worker", "terra_auditor", "sol_planner"),
            ("PASS", "BLOCKED", "ESCALATE"),
            (
                "none",
                "implementation",
                "technical_resolution",
                "planning_resolution",
                "human_authority",
            ),
        )
        for illegal in set(combinations) - set(expected):
            with self.subTest(illegal=illegal):
                with self.assertRaisesRegex(ValueError, "illegal handoff combination"):
                    validate_repo.resolve_handoff_route(*illegal)

    def test_skill_protocol_validation_allows_equivalent_prose(self) -> None:
        source = (
            self.original_root / ".agents/skills/lean-dev-router/SKILL.md"
        ).read_text(encoding="utf-8")
        original = (
            "Only Sol may author or amend `DISPATCH`; the parent may relay it unchanged."
        )
        self.assertIn(original, source)
        source = source.replace(
            original,
            "The parent may forward `DISPATCH` unchanged, while authorship and amendments remain Sol-only.",
        )

        self.assertEqual(self.validate_skill_source(source), [])

    def test_skill_protocol_validation_rejects_missing_request(self) -> None:
        source = (
            self.original_root / ".agents/skills/lean-dev-router/SKILL.md"
        ).read_text(encoding="utf-8")
        source = source.replace(
            "REQUEST: none | implementation | technical_resolution | planning_resolution | human_authority\n",
            "",
            1,
        )

        errors = self.validate_skill_source(source)

        self.assertTrue(
            any(
                "outbound protocol" in message and "REQUEST" in message
                for message in errors
            )
        )

    def test_skill_protocol_validation_rejects_wrong_version(self) -> None:
        source = (
            self.original_root / ".agents/skills/lean-dev-router/SKILL.md"
        ).read_text(encoding="utf-8")
        source = source.replace(
            "PROTOCOL: lean-dev-router/v2",
            "PROTOCOL: lean-dev-router/v1",
            1,
        )

        errors = self.validate_skill_source(source)

        self.assertTrue(
            any(
                "inbound DISPATCH protocol field PROTOCOL" in message
                for message in errors
            )
        )

    def test_skill_protocol_validation_rejects_illegal_luna_human_route(self) -> None:
        source = (
            self.original_root / ".agents/skills/lean-dev-router/SKILL.md"
        ).read_text(encoding="utf-8")
        source = source.replace(
            "| `luna_worker` | `ESCALATE` | `technical_resolution` | `terra_auditor` |",
            "| `luna_worker` | `ESCALATE` | `human_authority` | `user` |",
        )

        errors = self.validate_skill_source(source)

        self.assertTrue(
            any("illegal handoff combination" in message for message in errors)
        )

    def test_skill_protocol_validation_requires_sol_human_route(self) -> None:
        source = (
            self.original_root / ".agents/skills/lean-dev-router/SKILL.md"
        ).read_text(encoding="utf-8")
        source = source.replace(
            "| `sol_planner` | `BLOCKED` | `human_authority` | `user`, through parent |\n",
            "",
        )

        errors = self.validate_skill_source(source)

        self.assertTrue(
            any(
                "missing handoff route" in message and "human_authority" in message
                for message in errors
            )
        )

    def test_skill_protocol_validation_reports_empty_route_destination(self) -> None:
        source = (
            self.original_root / ".agents/skills/lean-dev-router/SKILL.md"
        ).read_text(encoding="utf-8")
        source = source.replace(
            "| `sol_planner` | `BLOCKED` | `human_authority` | `user`, through parent |",
            "| `sol_planner` | `BLOCKED` | `human_authority` | |",
        )

        errors = self.validate_skill_source(source)

        self.assertTrue(
            any(
                "missing destination for handoff "
                "sol_planner/BLOCKED/human_authority" in message
                for message in errors
            )
        )

    def test_skill_stays_within_context_budget(self) -> None:
        source = (
            self.original_root / ".agents/skills/lean-dev-router/SKILL.md"
        ).read_text(encoding="utf-8")

        self.assertLessEqual(len(source), 12_000)
        self.assertLessEqual(len(re.findall(r"\b[\w-]+\b", source)), 1_500)

    def test_compaction_preserves_representative_scenarios(self) -> None:
        skill = (
            self.original_root / ".agents/skills/lean-dev-router/SKILL.md"
        ).read_text(encoding="utf-8")
        sol = (self.original_root / "agents/sol-planner.toml").read_text(
            encoding="utf-8"
        )

        for scenario, required in {
            "bounded L1 write": ("minimal single-step `DISPATCH`", "`sol_planner`"),
            "read-only audit": ("audit", "`terra_auditor`"),
            "multi-batch integration": (
                "integration_owner",
                "integration_baseline",
                "integration_paths_allow",
                "integration_acceptance",
            ),
            "no nested spawning": ("cannot spawn nested workers", "`DISPATCH` manifest"),
            "security boundary": (
                "not a cryptographic signature",
                "sandbox_mode = \"read-only\"",
                "trusted coordination plane",
                "host-level write access",
            ),
            "incomplete handoff": (
                "originating role",
                "FAILURE: verification",
                "correction details in `EVIDENCE` and `SUMMARY`",
            ),
            "scope fallback": (
                "verify every allow entry together",
                "repeated `--allow <paths_allow_entry>` flag for each entry",
                "if the helper is unavailable",
                "Missing or failed scope evidence",
            ),
            "language fallback": (
                "otherwise the dominant language",
                "Use English when no natural-language signal exists",
            ),
            "streaming component scheduling": (
                "Process each independent component result as it arrives",
                "<component>:<revision>:<stage>",
                "queued",
                "running",
                "complete",
                "failed",
                "all-component barrier",
                "`token-first` may reuse one uninvolved Terra",
                "long parent commands",
                "within 60 seconds",
            ),
            "terra assignment envelope": (
                "STATUS: DISPATCH",
                "only Luna write authorization",
                "not an outbound result envelope",
            ),
        }.items():
            with self.subTest(scenario=scenario):
                for term in required:
                    self.assertIn(term, skill)

        for handoff, destination in {
            ("luna_worker", "ESCALATE", "technical_resolution"): "terra_auditor",
            ("terra_auditor", "ESCALATE", "implementation"): "sol_planner",
            ("terra_auditor", "ESCALATE", "planning_resolution"): "sol_planner",
            ("sol_planner", "BLOCKED", "human_authority"): "user",
        }.items():
            with self.subTest(handoff=handoff):
                self.assertEqual(
                    validate_repo.resolve_handoff_route(*handoff), destination
                )

        sol_instructions = tomllib.loads(sol)["developer_instructions"]
        for contract, (anchor, required) in {
            "single coordinator": (
                "You are sol_planner",
                ("non-overlapping orchestration scopes", "never spawn a peer Sol"),
            ),
            "scope defense": (
                "Use Todo/`DISPATCH`",
                ("primary scope defense", "low-frequency secondary control"),
            ),
            "write isolation": (
                "Give every parallel Luna writer",
                ("dedicated worktree", "branch alone is not isolation"),
            ),
            "integration contract": (
                "When two or more write batches",
                (
                    "integration_order",
                    "integration_baseline",
                    "integration_paths_allow",
                    "integration_acceptance",
                ),
            ),
            "integration failure routing": (
                "On integration failure",
                ("FAILURE: scope", "verification", "dependency", "ambiguity"),
            ),
            "nested-spawn fallback": (
                "If this session cannot spawn nested workers",
                ("`DISPATCH` manifest", "worker metadata", "integration_worktree"),
            ),
            "streaming component scheduling": (
                "Process each independent component result as it arrives",
                (
                    "same Sol",
                    "audit",
                    "re-audit",
                    "all-component barrier",
                    "token-first",
                    "long parent commands",
                    "60 seconds",
                ),
            ),
            "idempotent partial retry": (
                "Use a stable `<component>:<revision>:<stage>` job key",
                ("queued", "running", "complete", "failed", "partial failure"),
            ),
            "coordinator continuity": (
                "Keep this coordinator resumable",
                ("BLOCKED/dependency", "same Sol", "only if unavailable"),
            ),
        }.items():
            with self.subTest(contract=contract):
                line = next(
                    (
                        line
                        for line in sol_instructions.splitlines()
                        if anchor in line
                    ),
                    None,
                )
                self.assertIsNotNone(line)
                for term in required:
                    self.assertIn(term, line)

    def test_missing_license_is_reported_without_traceback(self) -> None:
        validate_repo.validate_license()

        self.assertEqual(len(validate_repo.ERRORS), 1)
        self.assertIn("LICENSE: cannot read required file", validate_repo.ERRORS[0])


if __name__ == "__main__":
    unittest.main()
