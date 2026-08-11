#!/usr/bin/env python3
"""Verify tracked and untracked Git paths against an explicit allow-list."""

from __future__ import annotations

import argparse
import json
import os
import subprocess


def git_paths(*args: str) -> list[str]:
    """Return NUL-delimited Git paths without relying on quotePath rendering."""
    result = subprocess.run(
        ["git", *args],
        check=False,
        capture_output=True,
    )
    if result.returncode:
        detail = os.fsdecode(result.stderr).strip() or f"exit={result.returncode}"
        raise RuntimeError(f"git {' '.join(args)}: {detail}")
    if not result.stdout:
        return []
    return [os.fsdecode(item) for item in result.stdout.split(b"\0") if item]


def normalize_allow_entry(path: str) -> str:
    """Normalize CLI separators only where backslash cannot name a file."""
    normalized = path.replace("\\", "/") if os.name == "nt" else path
    return normalized.strip("/")


def allowed(path: str, patterns: tuple[str, ...]) -> bool:
    """Match an exact Git path or one repository-relative directory subtree."""
    normalized = path.strip("/")
    for pattern in patterns:
        candidate = normalize_allow_entry(pattern)
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
        help="authorized repository-relative path or directory; repeat as needed",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    diff_args = ["diff", "--name-only", "--no-renames", "-z", args.baseline]
    if args.end:
        diff_args.append(args.end)
    diff_args.append("--")

    try:
        tracked = git_paths(*diff_args)
        standard_untracked = git_paths(
            "ls-files", "-z", "--others", "--exclude-standard"
        )
        ignored_untracked = git_paths(
            "ls-files", "-z", "--others", "--ignored", "--exclude-standard"
        )
    except RuntimeError as exc:
        print(f"SCOPE: BLOCKED; failure=dependency; proof={exc}")
        return 2

    all_paths = tracked + standard_untracked + ignored_untracked
    extras = sorted({path for path in all_paths if not allowed(path, tuple(args.allow))})
    status = "PASS" if not extras else "FAIL"
    boundary = f"baseline={args.baseline}"
    if args.end:
        boundary += f" end={args.end}"
    print(
        f"SCOPE: {status}; {boundary}; tracked={len(tracked)}; "
        f"untracked={len(standard_untracked)}; ignored={len(ignored_untracked)}; "
        f"extra={json.dumps(extras, ensure_ascii=True)}"
    )
    return 0 if not extras else 1


if __name__ == "__main__":
    raise SystemExit(main())
