from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import check_scope


CHECK_SCOPE = Path(__file__).resolve().parents[1] / "scripts" / "check_scope.py"


class ScopeRepository:
    def __init__(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.git("init", "-q")
        self.git("config", "user.email", "scope-tests@example.invalid")
        self.git("config", "user.name", "Scope Tests")
        self.write(".gitignore", "ignored/\n")
        self.write("seed.txt", "seed\n")
        self.git("add", ".")
        self.git("commit", "-qm", "seed")
        self.baseline = self.git("rev-parse", "HEAD").stdout.strip()

    def close(self) -> None:
        self.temporary.cleanup()

    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def write(self, relative: str, content: str = "content\n") -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def check(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CHECK_SCOPE), *args],
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )


class CheckScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = ScopeRepository()

    def tearDown(self) -> None:
        self.repo.close()

    def test_allowed_uses_path_component_boundaries(self) -> None:
        patterns = ("src",)

        self.assertTrue(check_scope.allowed("src", patterns))
        self.assertTrue(check_scope.allowed("src/file.py", patterns))
        self.assertFalse(check_scope.allowed("src_backup/file.py", patterns))
        self.assertFalse(check_scope.allowed("src/file.py.bak", ("src/file.py",)))

    def test_worktree_accepts_tracked_standard_and_ignored_paths(self) -> None:
        self.repo.write("seed.txt", "changed\n")
        self.repo.write("ascii/new.txt")
        self.repo.write("文档/说明.md")
        self.repo.write("space dir/file name.txt")
        self.repo.write("ignored/cache.txt")

        result = self.repo.check(
            "--baseline",
            self.repo.baseline,
            "--allow",
            "seed.txt",
            "--allow",
            "ascii",
            "--allow",
            "文档",
            "--allow",
            "space dir",
            "--allow",
            "ignored",
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SCOPE: PASS", result.stdout)
        self.assertIn("tracked=1", result.stdout)
        self.assertIn("untracked=3", result.stdout)
        self.assertIn("ignored=1", result.stdout)

    def test_unicode_extra_is_reported_without_git_quoting(self) -> None:
        self.repo.write("文档/说明.md")

        result = self.repo.check(
            "--baseline", self.repo.baseline, "--allow", "different"
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("SCOPE: FAIL", result.stdout)
        self.assertIn(r"\u6587\u6863/\u8bf4\u660e.md", result.stdout)
        self.assertNotIn(r"\346\226", result.stdout)

    def test_end_mode_checks_the_exact_commit_range(self) -> None:
        self.repo.write("committed.txt")
        self.repo.git("add", "committed.txt")
        self.repo.git("commit", "-qm", "add committed path")
        end = self.repo.git("rev-parse", "HEAD").stdout.strip()

        result = self.repo.check(
            "--baseline",
            self.repo.baseline,
            "--end",
            end,
            "--allow",
            "committed.txt",
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"end={end}", result.stdout)
        self.assertIn("tracked=1", result.stdout)

    @unittest.skipIf(os.name == "nt", "Windows filenames cannot contain these characters")
    def test_nul_framing_preserves_newline_and_backslash_names(self) -> None:
        self.repo.write("odd/new\nline.txt")
        self.repo.write("odd/back\\slash.txt")

        result = self.repo.check(
            "--baseline", self.repo.baseline, "--allow", "odd"
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("untracked=2", result.stdout)

    def test_git_failure_uses_blocked_contract(self) -> None:
        result = self.repo.check(
            "--baseline", "not-a-commit", "--allow", "anything"
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("SCOPE: BLOCKED; failure=dependency", result.stdout)


if __name__ == "__main__":
    unittest.main()
