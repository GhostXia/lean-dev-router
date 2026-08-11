from __future__ import annotations

import os
import re
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
        with self.assertRaises(ValueError):
            check_scope.allowed("src/file.py", ("../src",))
        with self.assertRaises(ValueError):
            check_scope.allowed("src/file.py", ("/src",))

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

    def test_end_revision_requires_clean_worktree(self) -> None:
        self.repo.write("committed.txt")
        self.repo.git("add", "committed.txt")
        self.repo.git("commit", "-qm", "end")
        end = self.repo.git("rev-parse", "HEAD").stdout.strip()
        self.repo.write("committed.txt", "local change\n")

        result = self.repo.check(
            "--baseline", self.repo.baseline, "--end", end,
            "--allow", "committed.txt", "--revision",
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("--end revision requires a clean worktree", result.stdout)
        self.assertNotIn("REVISION:", result.stdout)

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

    def revision(self, *allow: str) -> subprocess.CompletedProcess[str]:
        args = ["--baseline", self.repo.baseline]
        for path in allow:
            args.extend(("--allow", path))
        return self.repo.check(*args, "--revision")

    def test_clean_revision_is_exact_head(self) -> None:
        result = self.revision("seed.txt")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"REVISION: {self.repo.baseline}\n", result.stdout)

    def test_dirty_revision_is_stable_and_changes_with_tracked_repair(self) -> None:
        self.repo.write("seed.txt", "first repair\n")
        first = self.revision("seed.txt")
        repeated = self.revision("seed.txt")
        self.repo.write("seed.txt", "second repair\n")
        changed = self.revision("seed.txt")

        pattern = r"REVISION: (worktree-sha256:[0-9a-f]{64})"
        first_id = re.search(pattern, first.stdout).group(1)
        self.assertEqual(first_id, re.search(pattern, repeated.stdout).group(1))
        self.assertNotEqual(first_id, re.search(pattern, changed.stdout).group(1))

    def test_untracked_and_ignored_content_affect_revision(self) -> None:
        self.repo.write("new/item.txt", "one\n")
        self.repo.write("ignored/cache.txt", "alpha\n")
        first = self.revision("new", "ignored")
        self.repo.write("ignored/cache.txt", "beta\n")
        second = self.revision("new", "ignored")

        pattern = r"REVISION: (worktree-sha256:[0-9a-f]{64})"
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertNotEqual(
            re.search(pattern, first.stdout).group(1),
            re.search(pattern, second.stdout).group(1),
        )

    def test_unauthorized_or_retained_artifact_never_gets_revision(self) -> None:
        self.repo.write("build/cache.bin")
        unauthorized = self.revision("seed.txt")
        declared = self.repo.check(
            "--baseline", self.repo.baseline, "--allow", "build",
            "--artifact", "build", "--revision",
        )

        for result in (unauthorized, declared):
            self.assertEqual(result.returncode, 1)
            self.assertIn("SCOPE: FAIL", result.stdout)
            self.assertNotIn("REVISION:", result.stdout)

    def test_placeholder_baseline_is_blocked_without_revision(self) -> None:
        result = self.repo.check(
            "--baseline", "<luna-revision>", "--allow", "seed.txt", "--revision"
        )

        self.assertEqual(result.returncode, 2)
        self.assertNotIn("REVISION:", result.stdout)


if __name__ == "__main__":
    unittest.main()
