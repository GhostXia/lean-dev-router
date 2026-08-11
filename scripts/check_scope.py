#!/usr/bin/env python3
"""Verify scope and derive a stable revision for a worktree.

The scope check deliberately treats tracked, standard-untracked, and ignored
untracked paths as separate classes. A revision is calculated only after the
scope gate passes. Commits use their exact SHA; a dirty worktree uses a
NUL-framed SHA-256 over the resolved baseline, authorized tracked patches, and
authorized untracked file contents.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path


class ScopeError(RuntimeError):
    """Raised when a revision cannot be derived from an authorized state."""


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


def git_bytes(*args: str) -> bytes:
    """Run Git and return raw bytes without path quoting or text decoding."""
    result = subprocess.run(["git", *args], check=False, capture_output=True)
    if result.returncode:
        detail = os.fsdecode(result.stderr).strip() or f"exit={result.returncode}"
        raise RuntimeError(f"git {' '.join(args)}: {detail}")
    return result.stdout


def resolved_commit(revision: str) -> str:
    """Resolve a commit-ish to its exact 40-character SHA.

    Placeholder values are rejected before invoking Git so they cannot become
    an auditable job identity by accident.
    """
    value = str(revision).strip()
    if not value or "<" in value or ">" in value or value.startswith("${"):
        raise ScopeError("revision placeholder is not a commit")
    try:
        output = git_bytes("rev-parse", "--verify", f"{value}^{{commit}}")
    except RuntimeError as exc:
        raise ScopeError(str(exc)) from exc
    resolved = os.fsdecode(output).strip()
    if (
        not resolved
        or len(resolved) != 40
        or any(character not in "0123456789abcdef" for character in resolved)
    ):
        raise ScopeError(f"unresolved commit: {value}")
    return resolved


def normalize_allow_entry(path: str) -> str:
    """Return one normalized repository-relative path."""
    normalized = path.replace("\\", "/") if os.name == "nt" else path
    if normalized.startswith("/"):
        raise ValueError(f"allow path must be repository-relative: {path!r}")
    normalized = normalized.rstrip("/")
    if not normalized or any(part in ("", ".", "..") for part in normalized.split("/")):
        raise ValueError(f"invalid allow path: {path!r}")
    return normalized


def normalize_artifact_entry(path: str) -> str:
    """Normalize a repository-relative disposable artifact declaration."""
    normalized = normalize_allow_entry(path)
    if (
        not normalized
        or normalized == "."
        or normalized.startswith("../")
        or "/../" in normalized
    ):
        raise ValueError(f"invalid disposable artifact path: {path!r}")
    return normalized


def allowed(path: str, patterns: tuple[str, ...]) -> bool:
    """Match an exact Git path or one repository-relative directory subtree."""
    normalized = path.strip("/")
    for pattern in patterns:
        candidate = normalize_allow_entry(pattern)
        if normalized == candidate or normalized.startswith(f"{candidate}/"):
            return True
    return False


def matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    """Return whether *path* is inside one of the declared artifact roots."""
    return allowed(path, patterns)


def _frame(label: bytes, value: bytes) -> bytes:
    """Encode one length-delimited field; framing is safe for any pathname."""
    return (
        len(label).to_bytes(4, "big")
        + label
        + len(value).to_bytes(8, "big")
        + value
    )


def _read_file(path: str) -> tuple[bytes, bytes]:
    """Read an untracked file or link without following links outside the tree."""
    candidate = Path.cwd() / Path(path)
    try:
        if candidate.is_symlink():
            return b"symlink", os.fsencode(os.readlink(candidate))
        if candidate.is_file():
            return b"file", candidate.read_bytes()
        raise OSError("not a regular file or symbolic link")
    except OSError as exc:
        raise ScopeError(f"cannot read untracked path {path!r}: {exc}") from exc


def _tracked_paths(baseline: str, end: str | None = None) -> list[str]:
    args = ["diff", "--name-only", "--no-renames", "-z", baseline]
    if end:
        args.append(end)
    args.append("--")
    return git_paths(*args)


def _untracked_paths() -> tuple[list[str], list[str]]:
    standard = git_paths("ls-files", "-z", "--others", "--exclude-standard")
    ignored = git_paths(
        "ls-files", "-z", "--others", "--ignored", "--exclude-standard"
    )
    return standard, ignored


def scope_paths(
    baseline: str,
    allow: tuple[str, ...],
    *,
    end: str | None = None,
    artifacts: tuple[str, ...] = (),
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Collect scope classes and extra paths without deriving a revision."""
    tracked = _tracked_paths(baseline, end)
    standard, ignored = _untracked_paths()
    all_paths = tracked + standard + ignored
    retained_artifacts = sorted(
        {path for path in standard + ignored if matches_any(path, artifacts)}
    )
    extras = sorted({path for path in all_paths if not allowed(path, allow)})
    # Declared disposable files are never silently accepted while retained in
    # the worktree. They must be redirected outside the checkout or cleaned.
    extras = sorted(set(extras) | set(retained_artifacts))
    return tracked, standard, ignored, extras


def _worktree_dirty() -> bool:
    """Return whether HEAD has local tracked/untracked/ignored changes."""
    try:
        status = git_bytes(
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
            "--ignored",
        )
    except RuntimeError as exc:
        raise ScopeError(str(exc)) from exc
    return bool(status)


def compute_worktree_revision(
    baseline: str,
    allow: tuple[str, ...],
    *,
    end: str | None = None,
    artifacts: tuple[str, ...] = (),
    scope_result: tuple[list[str], list[str], list[str], list[str]] | None = None,
) -> str:
    """Return an exact commit SHA or a deterministic dirty-worktree SHA.

    The function repeats the scope invariant when called directly, preventing
    an unauthorized path from being laundered into a fingerprint.
    """
    resolved_baseline = resolved_commit(baseline)
    if scope_result is None:
        try:
            scope_result = scope_paths(
                resolved_baseline, allow, end=end, artifacts=artifacts
            )
        except (RuntimeError, ValueError) as exc:
            raise ScopeError(str(exc)) from exc
    tracked, standard, ignored, extras = scope_result
    if extras:
        raise ScopeError(
            "scope failed; unauthorized or retained artifact paths: "
            + ", ".join(extras)
        )

    dirty = _worktree_dirty()
    # End mode identifies an exact integrated commit; local tracked changes
    # are not part of baseline..end and therefore cannot be fingerprinted.
    if end:
        if dirty:
            raise ScopeError("--end revision requires a clean worktree")
        return resolved_commit(end)
    if not dirty:
        head = os.fsdecode(git_bytes("rev-parse", "--verify", "HEAD^{commit}"))
        return resolved_commit(head.strip())

    digest = hashlib.sha256()
    digest.update(_frame(b"format", b"lean-dev-router/worktree-sha256/v1"))
    digest.update(_frame(b"baseline", resolved_baseline.encode("ascii")))
    for path in sorted(set(tracked)):
        # One patch per path avoids Git's path quoting rules and keeps framing
        # independent of newlines, backslashes, or Unicode names.
        diff_args = [
            "-c",
            "core.quotePath=false",
            "diff",
            "--binary",
            "--full-index",
            "--no-renames",
            "--no-ext-diff",
            "--no-textconv",
            "--diff-algorithm=myers",
            "--no-indent-heuristic",
            resolved_baseline,
        ]
        diff_args.extend(("--", path))
        patch = git_bytes(*diff_args)
        digest.update(_frame(b"tracked-path", os.fsencode(path)))
        digest.update(_frame(b"tracked-diff", patch))

    for path in sorted(set(standard + ignored)):
        if matches_any(path, artifacts):
            # Retained artifacts should already have failed scope; this guard
            # keeps direct callers from ever hashing a disposable path.
            continue
        kind, content = _read_file(path)
        digest.update(_frame(b"untracked-path", os.fsencode(path)))
        digest.update(_frame(b"untracked-kind", kind))
        digest.update(_frame(b"untracked-content", content))
    return "worktree-sha256:" + digest.hexdigest()


# Public aliases keep the helper useful without introducing a scheduler API.
worktree_fingerprint = compute_worktree_revision
resolve_revision = compute_worktree_revision


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline", required=True, help="baseline commit for the tracked diff"
    )
    parser.add_argument("--end", help="optional combined commit; omit for the current worktree")
    parser.add_argument(
        "--allow",
        action="append",
        required=True,
        help="authorized repository-relative path or directory; repeat as needed",
    )
    parser.add_argument(
        "--revision",
        action="store_true",
        help="derive a commit SHA or deterministic dirty-worktree revision after scope PASS",
    )
    parser.add_argument(
        "--artifact",
        "--disposable-artifact",
        dest="artifacts",
        action="append",
        default=[],
        help="declared disposable artifact path; it must be cleaned before scope can pass",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        artifacts = tuple(normalize_artifact_entry(item) for item in args.artifacts)
        tracked, standard_untracked, ignored_untracked, extras = scope_paths(
            args.baseline,
            tuple(args.allow),
            end=args.end,
            artifacts=artifacts,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"SCOPE: BLOCKED; failure=dependency; proof={exc}")
        return 2

    status = "PASS" if not extras else "FAIL"
    boundary = f"baseline={args.baseline}"
    if args.end:
        boundary += f" end={args.end}"
    line = (
        f"SCOPE: {status}; {boundary}; tracked={len(tracked)}; "
        f"untracked={len(standard_untracked)}; ignored={len(ignored_untracked)}; "
        f"extra={json.dumps(extras, ensure_ascii=True)}"
    )
    if extras or not args.revision:
        print(line)
        return 0 if not extras else 1
    try:
        revision = compute_worktree_revision(
            args.baseline,
            tuple(args.allow),
            end=args.end,
            artifacts=artifacts,
            scope_result=(tracked, standard_untracked, ignored_untracked, extras),
        )
    except ScopeError as exc:
        print(f"{line}; revision=BLOCKED; failure=verification; proof={exc}")
        return 2
    print(line)
    print(f"REVISION: {revision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
