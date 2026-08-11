from __future__ import annotations

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

    def write(self, relative: str, text: str) -> None:
        path = validate_repo.ROOT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

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
            ("PROTOCOL: lean-dev-router/v1", "PROTOCOL: other/v1"),
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
                        source = source.replace("Never name or select another agent", f"Ask {peer}")
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

    def test_missing_license_is_reported_without_traceback(self) -> None:
        validate_repo.validate_license()

        self.assertEqual(len(validate_repo.ERRORS), 1)
        self.assertIn("LICENSE: cannot read required file", validate_repo.ERRORS[0])


if __name__ == "__main__":
    unittest.main()
