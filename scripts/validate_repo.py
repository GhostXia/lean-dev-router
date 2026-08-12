#!/usr/bin/env python3
"""Validate the repository's directly executable English runtime."""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ERRORS: list[str] = []
LANGUAGE_RULE = (
    "Language: Follow the parent task's primary language; when unspecified, use its "
    "dominant language. Keep code, commands, paths, model IDs, and agent names unchanged."
)
LEGACY_PATHS = (
    Path("runtime").joinpath("source"),
    Path("profiles").joinpath("codex"),
    Path("scripts").joinpath("build_" + "runtime.py"),
)
DISPATCH_FIELDS = (
    "PROTOCOL: lean-dev-router/v2",
    "STATUS: DISPATCH",
    "TARGET: implementation",
    "DISPATCH_ID",
    "PLAN_ID",
    "PLANNER_ROLE",
    "PLANNER_INSTANCE_ID",
    "AUDITOR_INSTANCE_ID",
    "TASK_SUMMARY",
    "BASELINE",
    "PATHS_ALLOW",
    "ACCEPTANCE",
    "CONSTRAINTS",
    "BUDGET",
    "NEXT: parent",
)
OUTBOUND_FIELDS = (
    "PROTOCOL",
    "AGENT",
    "STATUS",
    "FAILURE",
    "REQUEST",
    "EVIDENCE",
    "NEXT",
    "SUMMARY",
)
HANDOFF_ROUTES = {
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
LEGAL_HANDOFFS = set(HANDOFF_ROUTES)


def error(message: str) -> None:
    ERRORS.append(message)


def read(relative: str | Path) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def resolve_handoff_route(agent: str, status: str, request: str) -> str:
    """Resolve one v2 handoff using the authoritative finite transition table."""
    handoff = (agent, status, request)
    try:
        return HANDOFF_ROUTES[handoff]
    except KeyError as exc:
        raise ValueError(
            f"illegal handoff combination: {agent}/{status}/{request}"
        ) from exc


def require_instruction_line(
    relative: str,
    instructions: str,
    anchor: str,
    required_terms: tuple[str, ...],
) -> None:
    line = next((line for line in instructions.splitlines() if anchor in line), None)
    if line is None:
        error(f"{relative}: missing instruction anchored by {anchor!r}")
        return
    for term in required_terms:
        if term not in line:
            error(f"{relative}: {anchor!r} instruction is missing {term!r}")


def validate_agents() -> None:
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
        try:
            data = tomllib.loads(read(relative))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            error(f"{relative}: TOML parse failed: {exc}")
            continue
        for key, value in {
            "name": name,
            "model": model,
            "model_reasoning_effort": effort,
        }.items():
            if data.get(key) != value:
                error(f"{relative}: expected {key}={value!r}")
        if sandbox is not None and data.get("sandbox_mode") != sandbox:
            error(f"{relative}: expected sandbox_mode={sandbox!r}")
        if not str(data.get("description", "")).strip():
            error(f"{relative}: description is empty")
        description = str(data.get("description", ""))
        instructions = str(data.get("developer_instructions", ""))
        language_lines = [
            line.strip()
            for line in instructions.splitlines()
            if line.strip().startswith("Language:")
        ]
        if language_lines != [LANGUAGE_RULE]:
            error(f"{relative}: English language rule is missing or incorrect")
        envelope = next(
            (
                line.strip()
                for line in instructions.splitlines()
                if "outbound result envelope:" in line
            ),
            None,
        )
        if envelope is None:
            error(f"{relative}: missing outbound result envelope")
        else:
            next_field = re.search(r"\bNEXT:\s*([a-z_]+)", envelope)
            if next_field is None or next_field.group(1) != "parent":
                error(f"{relative}: outbound result envelope NEXT must equal parent")
        common = OUTBOUND_FIELDS
        role_terms = {
            "luna_worker": DISPATCH_FIELDS + (
                "PLAN_READY", "missing_dispatch", "scripts/check_scope.py",
                "worktree-sha256:<64 lowercase hex>", "repair budget",
                "Never plan the task, authorize writes, schedule peers, or request human authority.",
                "pre-PASS route", "current diff/paths", "exact failure/replay",
                "MODEL_CALL_LIMIT", "STAGNANT_CALL_LIMIT", "runtime guard",
            ),
            "sol_planner": DISPATCH_FIELDS + (
                "PLAN_MANIFEST", "DISPATCH_WAVE", "EXPANSION_GATE",
                "not continuously schedule", "Preregister Terra",
                "IMPACT_CONE", "worktree-sha256:<64 lowercase hex>",
                "three materially distinct attempts", "human_authority",
                "externally measurable latency", "sleep is only polling",
                "MODEL_CALL_LIMIT", "STAGNANT_CALL_LIMIT", "hard parent-enforced ceiling",
            ),
            "terra_auditor": (
                "Never edit, authorize a write, schedule peers, or request human authority.",
                "AUDIT_SCOPE/IMPACT_CONE", "callers/callees", "A =", "B =",
                "C =", "D =", "DISPATCH_ID", "CONTRACT_EFFECT: unchanged",
                "AFFECTED_PATHS", "ESCALATE/implementation",
                "ESCALATE/planning_resolution",
                "sleep alone is not synchronization proof",
                "pre-PASS technical-resolution", "does not require final scope or revision",
                "never BLOCKED/none",
                "AUDITOR_INSTANCE_ID", "incremental audit", "hard-budget telemetry",
            ),
        }
        for term in common + role_terms[name]:
            if term not in instructions:
                error(f"{relative}: missing required instruction {term!r}")


def markdown_lines(text: str) -> list[tuple[int, str]]:
    outside: list[tuple[int, str]] = []
    fence: tuple[str, int] | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        marker = re.match(r"^\s*(```+|~~~+)", line)
        if marker:
            opener = marker.group(1)
            token = opener[0]
            length = len(opener)
            if fence is None:
                fence = (token, length)
            elif fence[0] == token and length >= fence[1]:
                fence = None
        elif fence is None:
            outside.append((number, line))
    return outside


def fenced_blocks(text: str) -> list[str]:
    """Return Markdown fenced code block bodies without interpreting their prose."""
    blocks: list[str] = []
    fence: tuple[str, int] | None = None
    body: list[str] = []
    for line in text.splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})(.*)$", line)
        if fence is None:
            if marker:
                opener = marker.group(1)
                fence = (opener[0], len(opener))
                body = []
            continue
        if marker:
            closer = marker.group(1)
            if (
                closer[0] == fence[0]
                and len(closer) >= fence[1]
                and not marker.group(2).strip()
            ):
                blocks.append("\n".join(body))
                fence = None
                body = []
                continue
        body.append(line)
    return blocks


def protocol_fields(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in block.splitlines():
        match = re.match(r"^([A-Z][A-Z_]*):\s*(.*)$", line)
        if not match:
            continue
        name, value = match.groups()
        if name in fields:
            raise ValueError(f"duplicate protocol field {name}")
        fields[name] = value.strip()
    return fields


def validate_protocol_schema(relative: str, skill: str) -> None:
    parsed: list[dict[str, str]] = []
    for block in fenced_blocks(skill):
        try:
            fields = protocol_fields(block)
        except ValueError as exc:
            error(f"{relative}: {exc}")
            continue
        if fields:
            parsed.append(fields)

    dispatch = next(
        (fields for fields in parsed if fields.get("STATUS") == "DISPATCH"), None
    )
    outbound = next((fields for fields in parsed if "AGENT" in fields), None)
    schemas = (
        (
            "inbound DISPATCH protocol",
            dispatch,
            {
                "PROTOCOL": "lean-dev-router/v2",
                "STATUS": "DISPATCH",
                "TARGET": "implementation",
                "DISPATCH_ID": None,
                "PLAN_ID": None,
                "PLANNER_ROLE": "sol_planner",
                "PLANNER_INSTANCE_ID": None,
                "AUDITOR_INSTANCE_ID": None,
                "TASK_SUMMARY": None,
                "BASELINE": None,
                "PATHS_ALLOW": None,
                "ACCEPTANCE": None,
                "CONSTRAINTS": None,
                "BUDGET": None,
                "NEXT": "parent",
            },
        ),
        (
            "outbound protocol",
            outbound,
            {
                "PROTOCOL": "lean-dev-router/v2",
                "AGENT": "luna_worker | terra_auditor | sol_planner",
                "STATUS": "PASS | BLOCKED | ESCALATE",
                "FAILURE": "none | missing_dispatch | scope | verification | dependency | ambiguity | major-decision",
                "REQUEST": "none | implementation | technical_resolution | planning_resolution | human_authority",
                "EVIDENCE": None,
                "NEXT": "parent",
                "SUMMARY": None,
            },
        ),
    )
    for label, fields, expected in schemas:
        if fields is None:
            error(f"{relative}: missing {label}")
            continue
        missing = set(expected) - set(fields)
        unexpected = set(fields) - set(expected)
        if missing:
            error(f"{relative}: {label} missing fields: {', '.join(sorted(missing))}")
        if unexpected:
            error(
                f"{relative}: {label} has unexpected fields: "
                f"{', '.join(sorted(unexpected))}"
            )
        if label == "inbound DISPATCH protocol":
            for name in (
                "DISPATCH_ID", "PLAN_ID", "PLANNER_ROLE",
                "PLANNER_INSTANCE_ID", "AUDITOR_INSTANCE_ID",
            ):
                if not fields.get(name):
                    error(f"{relative}: inbound DISPATCH protocol {name} must be non-empty")
        for name, value in expected.items():
            if value is not None and fields.get(name) != value:
                error(
                    f"{relative}: {label} field {name} must be {value!r}"
                )


def validate_handoff_table(relative: str, skill: str) -> None:
    rows: dict[tuple[str, str, str], str] = {}
    row_pattern = re.compile(
        r"^\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*"
        r"\|\s*(.*?)\s*\|\s*$"
    )
    for number, line in markdown_lines(skill):
        match = row_pattern.match(line)
        if not match:
            continue
        agent, status, request, destination_cell = match.groups()
        handoff = (agent, status, request)
        if handoff in rows:
            error(
                f"{relative}:{number}: duplicate handoff route "
                f"{agent}/{status}/{request}"
            )
            continue
        if not destination_cell:
            rows[handoff] = ""
            error(
                f"{relative}:{number}: missing destination for handoff "
                f"{agent}/{status}/{request}"
            )
            continue
        destination_match = re.fullmatch(r"`([^`]+)`[^|]*", destination_cell)
        if destination_match is None:
            continue
        destination = destination_match.group(1)
        rows[handoff] = destination
        try:
            expected_destination = resolve_handoff_route(*handoff)
        except ValueError as exc:
            error(f"{relative}:{number}: {exc}")
            continue
        if destination != expected_destination:
            error(
                f"{relative}:{number}: handoff {agent}/{status}/{request} must route "
                f"to {expected_destination!r}, not {destination!r}"
            )
    for handoff in sorted(LEGAL_HANDOFFS - set(rows)):
        error(f"{relative}: missing handoff route {'/'.join(handoff)}")


def validate_skill_document(
    relative: str, required_text: tuple[str, ...], expected_titles: set[str]
) -> None:
    skill = read(relative)
    if not skill.startswith("---\n") or "\n---\n" not in skill[4:]:
        error(f"{relative}: missing YAML-style frontmatter")
    for required in required_text:
        if required not in skill:
            error(f"{relative}: missing required text {required!r}")

    validate_protocol_schema(relative, skill)
    validate_handoff_table(relative, skill)

    headings: list[tuple[int, str]] = []
    for number, line in markdown_lines(skill):
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading:
            headings.append((len(heading.group(1)), heading.group(2)))
        if re.match(r"^\s*(?:[-+*]|\d+\.)\s*$", line):
            error(f"{relative}:{number}: empty list item")
        if re.search(r"\s/\s*$", line):
            error(f"{relative}:{number}: unconsumed language separator")
    for previous, current in zip(headings, headings[1:]):
        if current[0] > previous[0] + 1:
            error(f"{relative}: heading level jumps from H{previous[0]} to H{current[0]}")
    actual_titles = {title for _, title in headings}
    for title in sorted(expected_titles - actual_titles):
        error(f"{relative}: missing heading {title!r}")
    for number, line in markdown_lines(skill):
        if line.strip() in expected_titles and not line.startswith("#"):
            error(f"{relative}:{number}: bare heading {line.strip()!r}")


def validate_skill() -> None:
    root = ".agents/skills/lean-dev-router/SKILL.md"
    english = "skill-variants/en/SKILL.md"
    chinese = "skill-variants/zhcn/SKILL.md"
    if read(root) != read(english):
        error(f"{root}: must exactly match {english}")

    common = (
        "name: lean-dev-router",
        "N/A (batch coverage)",
        "integration_owner",
        "integration_baseline",
        "integration_paths_allow",
        "integration_acceptance",
        "python scripts/check_scope.py",
        "FAILURE: missing_dispatch",
        "PLAN_MANIFEST",
        "DISPATCH_WAVE",
        "EXPANSION_GATE",
        "<component>:<revision>:<stage>",
        "all-component barrier",
        "worktree-sha256:<64 lowercase hex>",
        "CONTRACT_EFFECT: unchanged",
        "parent:repair_or_sol",
        "runtime_guard.py start",
        "runtime_guard.py audit",
        "ACTION: abandon",
    )
    validate_skill_document(
        root,
        common + (
            "does not continuously schedule",
            "Streaming and preregistered audit",
            "reuse one uninvolved Terra",
            "long parent commands",
            "within 60 seconds",
            "first eligible slot release",
            "not an outbound result envelope",
            "never updates the incremental-audit baseline",
            "Exit 2 means zero target calls",
            "deterministic `spinning` signal",
            "Parent never repairs or writes",
            "same revision is never",
        ),
        {
            "Lean Dev Router", "Language", "Authority and entry",
            "Bounded planning waves", "Protocol", "Scope, artifacts, and revision",
            "Risk fuse and replay", "Streaming and preregistered audit",
            "Terra causal audit and repair", "Integration",
            "Execution and human gate",
        },
    )
    validate_skill_document(
        chinese,
        common + (
            "Sol 不持续调度常规事件",
            "流式处理与预注册审计",
            "可复用一名未参与实现的 Terra",
            "父代理执行长命令",
            "60 秒内启动",
            "第一个可用 slot 释放时启动",
            "不使用出站结果信封",
            "绝不更新增量审计基线",
            "Exit 2 表示目标调用数为零",
            "确定性的 `spinning` 信号",
            "父代理在 Luna 失败或中断后绝不修复或写入",
            "相同 revision 不得重复审计",
        ),
        {
            "Lean Dev Router", "语言", "权限与入口", "有界规划波次", "协议",
            "范围、产物与版本", "风险熔断与复现", "流式处理与预注册审计",
            "Terra 因果审计与修复", "集成", "执行与用户门禁",
        },
    )


def validate_runtime_guard() -> None:
    relative = ".agents/skills/lean-dev-router/scripts/runtime_guard.py"
    try:
        source = read(relative)
    except OSError as exc:
        error(f"{relative}: cannot read runtime guard: {exc}")
        return
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        error(f"{relative}: invalid Python: {exc.msg}")
        return
    allowed_imports = {
        "__future__", "argparse", "hashlib", "json", "math", "sys",
        "dataclasses", "pathlib", "typing",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = {alias.name.split(".", 1)[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            names = {str(node.module).split(".", 1)[0]}
        else:
            continue
        for name in names - allowed_imports:
            error(f"{relative}: non-standard or undeclared import {name!r}")
    string_constants = {
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    definitions = {
        node.name for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    subcommands = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_parser"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }
    for term in ("validate_dispatch", "validate_repair", "abandon_audit"):
        if term not in definitions:
            error(f"{relative}: missing runtime gate {term!r}")
    for term in (
        "MODEL_CALL_LIMIT", "HYPOTHESIS_LIMIT", "MODEL_ACTIVE_SECONDS_LIMIT",
        "REPAIR_CYCLE_LIMIT", "STAGNANT_CALL_LIMIT", "EVIDENCE_FINGERPRINT",
        "CONTRACT_VERSION",
    ):
        if term not in string_constants:
            error(f"{relative}: missing runtime gate {term!r}")
    for term in ("start", "event", "repair", "audit", "schema"):
        if term not in subcommands:
            error(f"{relative}: missing runtime gate subcommand {term!r}")
    for term in (
        "repeated_failure_without_new_evidence", '"spinning"',
        "unauthorized_writer", "duplicate_audit_revision", "audit_abandoned",
        "uncached_input_tokens", "total_tokens",
    ):
        if term not in source:
            error(f"{relative}: missing runtime gate {term!r}")


def parse_manifest(text: str) -> dict[str, dict[str, str]]:
    """Parse the repository's intentionally small mapping-only YAML manifest."""
    result: dict[str, dict[str, str]] = {}
    section: str | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if "\t" in line:
            raise ValueError(f"line {number}: tabs are not allowed")
        top = re.fullmatch(r"([A-Za-z_][\w-]*):", line)
        if top:
            section = top.group(1)
            if section in result:
                raise ValueError(f"line {number}: duplicate section {section!r}")
            result[section] = {}
            continue
        item = re.fullmatch(r"  ([A-Za-z_][\w-]*):\s*(.+)", line)
        if item is None or section is None:
            raise ValueError(f"line {number}: unsupported YAML structure")
        key, raw_value = item.groups()
        if key in result[section]:
            raise ValueError(f"line {number}: duplicate key {key!r}")
        try:
            value = ast.literal_eval(raw_value)
        except (SyntaxError, ValueError) as exc:
            raise ValueError(f"line {number}: invalid quoted scalar") from exc
        if not isinstance(value, str):
            raise ValueError(f"line {number}: expected a string scalar")
        result[section][key] = value
    return result


def validate_manifest() -> None:
    relative = ".agents/skills/lean-dev-router/agents/openai.yaml"
    try:
        manifest = parse_manifest(read(relative))
    except (OSError, ValueError) as exc:
        error(f"{relative}: YAML parse failed: {exc}")
        return
    interface = manifest.get("interface", {})
    for key in ("display_name", "short_description", "default_prompt"):
        if not interface.get(key, "").strip():
            error(f"{relative}: interface.{key} is missing")
    if "$lean-dev-router" not in interface.get("default_prompt", ""):
        error(f"{relative}: default_prompt disagrees with the Skill name")


def validate_runtime_language() -> None:
    for root in (ROOT / ".agents", ROOT / "agents"):
        for path in root.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            relative = path.relative_to(ROOT).as_posix()
            if relative == ".agents/skills/lean-dev-router/SKILL.md":
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if not line.isascii():
                    error(f"{relative}:{number}: non-ASCII text is not allowed in runtime files")


def validate_markdown() -> None:
    link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for path in ROOT.rglob("*.md"):
        if ".git" in path.parts or ".workbuddy" in path.parts:
            continue
        relative = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        fence: tuple[str, int, int, str, list[str]] | None = None
        for number, line in enumerate(text.splitlines(), start=1):
            marker = re.match(r"^\s*(```+|~~~+)(.*)$", line)
            if marker:
                opener = marker.group(1)
                token = opener[0]
                length = len(opener)
                if fence is None:
                    fence = (token, length, number, marker.group(2).strip().lower(), [])
                elif fence[0] == token and length >= fence[1]:
                    if fence[3] == "python":
                        try:
                            ast.parse("\n".join(fence[4]))
                        except SyntaxError as exc:
                            error(f"{relative}:{fence[2]}: invalid Python fence: {exc.msg}")
                    fence = None
                else:
                    fence[4].append(line)
            elif fence is not None:
                fence[4].append(line)
        if fence is not None:
            error(f"{relative}:{fence[2]}: unclosed Markdown code fence")
        for match in link_pattern.finditer(text):
            target = match.group(1).split(maxsplit=1)[0].strip("<>")
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            local = target.split("#", 1)[0]
            if local and not (path.parent / local).exists():
                error(f"{relative}: missing local link target {local!r}")


def validate_repository_contract() -> None:
    for path in LEGACY_PATHS:
        if (ROOT / path).exists():
            error(f"legacy runtime path still exists: {path.as_posix()}")
    legacy_tokens = tuple(path.as_posix() for path in LEGACY_PATHS)
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or ".workbuddy" in path.parts:
            continue
        if path.suffix.lower() not in {".md", ".py", ".toml", ".yaml", ".yml"}:
            continue
        text = path.read_text(encoding="utf-8")
        for token in legacy_tokens:
            if token in text:
                error(f"{path.relative_to(ROOT).as_posix()}: legacy reference {token!r}")
    required_text = {
        "README.md": ("docs/zh-CN/README.md", "scripts/check_scope.py"),
        "docs/zh-CN/README.md": (
            "仅供人类阅读",
            ".agents/skills/lean-dev-router/SKILL.md",
            "scripts/check_scope.py",
        ),
        "lean-dev-router-self-test-guide.md": (
            "integration_owner",
            "tracked/untracked scope evidence",
        ),
        "lean-dev-router-l3-idempotent-orders-task.md": (
            "threading.Barrier(3)",
            "join(timeout=5)",
        ),
    }
    for relative, snippets in required_text.items():
        try:
            text = read(relative)
        except OSError as exc:
            error(f"{relative}: cannot read required file: {exc}")
            continue
        for snippet in snippets:
            if snippet not in text:
                error(f"{relative}: missing contract text {snippet!r}")
    validate_license()


def validate_license() -> None:
    relative = "LICENSE"
    try:
        text = read(relative)
    except (OSError, UnicodeError) as exc:
        error(f"{relative}: cannot read required file: {exc}")
        return
    if not text.startswith("MIT License\n"):
        error(f"{relative}: expected MIT license text")


def main() -> int:
    validate_agents()
    validate_skill()
    validate_runtime_guard()
    validate_manifest()
    validate_runtime_language()
    validate_markdown()
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
