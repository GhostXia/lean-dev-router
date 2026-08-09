#!/usr/bin/env python3
"""Validate repository-owned configuration and documentation invariants."""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ERRORS: list[str] = []


def error(message: str) -> None:
    """Record one validation failure without aborting the remaining checks."""
    ERRORS.append(message)


def read(relative: str) -> str:
    """Read one repository-relative UTF-8 text file."""
    return (ROOT / relative).read_text(encoding="utf-8")


def require_instruction_line(
    relative: str,
    instructions: str,
    anchor: str,
    required_terms: tuple[str, ...],
) -> None:
    """Require route controls to coexist in the instruction line they govern."""
    line = next(
        (candidate for candidate in instructions.splitlines() if anchor in candidate),
        None,
    )
    if line is None:
        error(f"{relative}: missing instruction section anchored by {anchor!r}")
        return
    for term in required_terms:
        if term not in line:
            error(
                f"{relative}: instruction section {anchor!r} is missing {term!r}"
            )


def validate_agents() -> None:
    """Validate Agent TOML metadata and route-specific instruction contracts."""
    expected = {
        "agents/luna-worker.toml": ("luna_worker", "gpt-5.6-luna", "max", None),
        "agents/sol-planner.toml": ("sol_planner", "gpt-5.6-sol", "medium", None),
        "agents/terra-auditor.toml": (
            "terra_auditor",
            "gpt-5.6-terra",
            "high",
            "read-only",
        ),
    }

    for relative, (name, model, effort, sandbox) in expected.items():
        path = ROOT / relative
        try:
            with path.open("rb") as handle:
                data = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            error(f"{relative}: TOML parse failed: {exc}")
            continue

        required = {
            "name": name,
            "model": model,
            "model_reasoning_effort": effort,
        }
        for key, value in required.items():
            if data.get(key) != value:
                error(f"{relative}: expected {key}={value!r}")
        if sandbox is not None and data.get("sandbox_mode") != sandbox:
            error(f"{relative}: expected sandbox_mode={sandbox!r}")
        if not str(data.get("description", "")).strip():
            error(f"{relative}: description is empty")
        instructions = str(data.get("developer_instructions", ""))
        if not instructions.strip():
            error(f"{relative}: developer_instructions is empty")
        if "语言 / Language" not in instructions:
            error(f"{relative}: bilingual language rule is missing")
        if name == "luna_worker":
            require_instruction_line(
                relative,
                instructions,
                "Every write task",
                (
                    "baseline commit",
                    "paths_allow",
                    "direct fast path",
                ),
            )
            require_instruction_line(
                relative,
                instructions,
                "Before returning PASS",
                ("git ls-files --others --ignored --exclude-standard",),
            )
        elif name == "terra_auditor":
            require_instruction_line(
                relative,
                instructions,
                "When assigned an integration audit",
                (
                    "exact combined commit",
                    "integration_acceptance",
                    "component-level audit PASS",
                ),
            )


def validate_markdown() -> None:
    """Validate Markdown fences, Python examples, and local links."""
    link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for path in ROOT.rglob("*.md"):
        relative = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        open_fence: int | None = None
        fence_language = ""
        fenced_lines: list[str] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if line.lstrip().startswith("```"):
                if open_fence is None:
                    open_fence = line_number
                    fence_language = line.lstrip()[3:].strip().lower()
                    fenced_lines = []
                else:
                    if fence_language == "python":
                        try:
                            ast.parse("\n".join(fenced_lines))
                        except SyntaxError as exc:
                            error(
                                f"{relative}:{open_fence}: invalid Python fence: "
                                f"{exc.msg} at fenced line {exc.lineno}"
                            )
                    open_fence = None
                    fence_language = ""
                    fenced_lines = []
            elif open_fence is not None:
                if fence_language in ("", "text") and re.match(r"^#{1,6}\s+", line):
                    error(
                        f"{relative}:{line_number}: Markdown heading appears inside "
                        f"a fence opened at line {open_fence}"
                    )
                fenced_lines.append(line)
        if open_fence is not None:
            error(f"{relative}:{open_fence}: unclosed Markdown code fence")

        for match in link_pattern.finditer(text):
            target = match.group(1).split(maxsplit=1)[0].strip("<>")
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            local_target = target.split("#", 1)[0]
            if local_target and not (path.parent / local_target).exists():
                error(f"{relative}: missing local link target {local_target!r}")


def validate_skill_and_manifest() -> None:
    """Validate the Skill frontmatter, protocol controls, and UI manifest."""
    skill = read(".agents/skills/lean-dev-router/SKILL.md")
    if not skill.startswith("---\n"):
        error("SKILL.md: missing YAML frontmatter")
    for required in (
        "name: lean-dev-router",
        "path: N/A (batch coverage)",
        "integration_owner",
        "integration_baseline",
        "integration_paths_allow",
        "integration_acceptance",
        "git ls-files --others --ignored --exclude-standard",
    ):
        if required not in skill:
            error(f"SKILL.md: missing required protocol text {required!r}")

    manifest = read(".agents/skills/lean-dev-router/agents/openai.yaml")
    for required in ("interface:", "display_name:", "short_description:", "default_prompt:"):
        if not re.search(rf"^\s*{re.escape(required)}", manifest, re.MULTILINE):
            error(f"openai.yaml: missing {required}")


def validate_repository_contract() -> None:
    """Validate cross-file repository contracts and license text."""
    required_text = {
        "README.md": (
            "path: N/A (batch coverage)",
            "integration_owner",
            "integration_paths_allow",
            "git ls-files --others --ignored --exclude-standard",
            "Historical evidence note:",
            "历史证据说明：",
        ),
        "agents/sol-planner.toml": (
            "integration_owner",
            "integration_paths_allow",
            "git ls-files --others --ignored --exclude-standard",
        ),
        "lean-dev-router-self-test-guide.md": (
            "integration_owner",
            "tracked/untracked scope evidence",
            "git ls-files --others --ignored --exclude-standard",
        ),
        "lean-dev-router-l3-idempotent-orders-task.md": (
            "threading.Barrier(3)",
            "git ls-files --others --exclude-standard",
            "git ls-files --others --ignored --exclude-standard",
            "join(timeout=5)",
            "assert not t1.is_alive()",
            "assert not t2.is_alive()",
        ),
    }
    for relative, snippets in required_text.items():
        text = read(relative)
        for snippet in snippets:
            if snippet not in text:
                error(f"{relative}: missing contract text {snippet!r}")

    if not read("LICENSE").startswith("MIT License\n"):
        error("LICENSE: expected MIT license text")


def main() -> int:
    """Run every repository validator and return a process exit code."""
    validate_agents()
    validate_markdown()
    validate_skill_and_manifest()
    validate_repository_contract()
    if ERRORS:
        for message in ERRORS:
            print(f"ERROR: {message}", file=sys.stderr)
        print(f"Validation failed with {len(ERRORS)} error(s).", file=sys.stderr)
        return 1
    print("Repository validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
