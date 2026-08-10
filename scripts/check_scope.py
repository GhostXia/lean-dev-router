#!/usr/bin/env python3
"""Mechanically verify tracked and untracked paths against an allow-list."""

from __future__ import annotations

import argparse
import subprocess


def git(*args: str) -> list[str]:
    """Return non-empty lines from a Git command or raise a dependency error."""
    result = subprocess.run(
        ["git", *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode:
        detail = result.stderr.strip() or f"exit={result.returncode}"
        raise RuntimeError(f"git {' '.join(args)}: {detail}")
    return [line.replace("\\", "/") for line in result.stdout.splitlines() if line]


def allowed(path: str, patterns: tuple[str, ...]) -> bool:
    """Match an exact path or a repository-relative directory subtree."""
    normalized = path.strip("/")
    for pattern in patterns:
        candidate = pattern.replace("\\", "/").strip("/")
        if normalized == candidate or normalized.startswith(f"{candidate}/"):
            return True
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, help="baseline commit for the tracked diff")
    parser.add_argument("--end", help="optional combined commit; omit for the current worktree")
    parser.add_argument(
        "--allow",
        action="append",
        required=True,
        help="authorized repository-relative path or directory; repeat for multiple entries",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    diff_args = ["diff", "--name-only", "--no-renames", args.baseline]
    if args.end:
        diff_args.append(args.end)
    diff_args.append("--")

    try:
        tracked = git(*diff_args)
        standard_untracked = git("ls-files", "--others", "--exclude-standard")
        ignored_untracked = git("ls-files", "--others", "--ignored", "--exclude-standard")
    except RuntimeError as exc:
        print(f"SCOPE: BLOCKED; failure=dependency; proof={exc}")
        return 2

    all_paths = tracked + standard_untracked + ignored_untracked
    extras = sorted({path for path in all_paths if not allowed(path, tuple(args.allow))})
    status = "PASS" if not extras else "FAIL"
    extra_text = ",".join(extras) if extras else "none"
    boundary = f"baseline={args.baseline}"
    if args.end:
        boundary += f" end={args.end}"
    print(
        f"SCOPE: {status}; {boundary}; tracked={len(tracked)}; "
        f"untracked={len(standard_untracked)}; ignored={len(ignored_untracked)}; extra={extra_text}"
    )
    return 0 if not extras else 1


if __name__ == "__main__":
    raise SystemExit(main())
