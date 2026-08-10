#!/usr/bin/env python3
"""Build one single-language runtime profile from the bilingual source files."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runtime" / "source"
TARGETS = (
    Path(".agents/skills/lean-dev-router/SKILL.md"),
    Path("agents/luna-worker.toml"),
    Path("agents/sol-planner.toml"),
    Path("agents/terra-auditor.toml"),
)
STATIC_TARGETS = (Path(".agents/skills/lean-dev-router/agents/openai.yaml"),)
LANGUAGES = ("en", "zh-CN")
DESCRIPTION_START = re.compile(r"\s+(Executes|Performs|The default single planner)")


def split_pair(line: str, language: str) -> str:
    """Select one side of an English / Chinese source line."""
    if " / " not in line:
        return line
    left, _, right = line.partition(" / ")
    return left if language == "en" else right


def split_quoted_pair(line: str, language: str) -> str:
    """Select one side of a paired value while preserving YAML quotes."""
    first_quote = line.find('"')
    last_quote = line.rfind('"')
    if first_quote < 0 or last_quote <= first_quote or " / " not in line[first_quote:last_quote]:
        return line
    value = line[first_quote + 1 : last_quote]
    selected = split_pair(value, language)
    return f'{line[:first_quote + 1]}{selected}{line[last_quote:]}'


def render_skill(language: str) -> bytes:
    source = (SOURCE / "SKILL.md").read_text(encoding="utf-8")
    in_fence = False
    rendered: list[str] = []
    for line in source.splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
            rendered.append(line)
        elif in_fence:
            rendered.append(line)
        else:
            rendered.append(split_pair(line, language))
    return ("\n".join(rendered) + "\n").encode("utf-8")


def render_agent(source_path: Path, language: str) -> bytes:
    lines = source_path.read_text(encoding="utf-8").splitlines()
    open_index = next(i for i, line in enumerate(lines) if line.startswith("developer_instructions ="))
    close_index = len(lines) - 1 - next(i for i, line in enumerate(reversed(lines)) if line == '"""')
    header = lines[:open_index]
    description_index = next(i for i, line in enumerate(header) if line.startswith("description = "))
    description = header[description_index]
    match = DESCRIPTION_START.search(description)
    if not match:
        raise ValueError(f"cannot split agent description: {source_path}")
    if language == "zh-CN":
        header[description_index] = description[: match.start()].rstrip() + '"'
    else:
        header[description_index] = 'description = "' + description[match.start() :].strip()[:-1] + '"'

    body = lines[open_index + 1 : close_index]
    language_index = next(i for i, line in enumerate(body) if "语言 / Language:" in line)
    chinese_index = next(i for i, line in enumerate(body) if line.startswith("你是 "))
    english_index = next(i for i, line in enumerate(body) if line.startswith("You are "))
    language_line = (
        "Language: Follow the parent task's primary language; when unspecified, use its dominant language. "
        "Keep code, commands, paths, model IDs, and agent names unchanged."
        if language == "en"
        else "语言: 跟随父任务的主要语言；如果父任务未明确指定，使用父任务占主导的语言。"
        "保持代码、命令、路径、模型 ID 和 Agent 名称不变。"
    )
    selected = [language_line, ""]
    selected.extend(body[chinese_index:english_index] if language == "zh-CN" else body[english_index:])
    output = header + ['developer_instructions = """'] + selected + ['"""'] + lines[close_index + 1 :]
    return ("\n".join(output) + "\n").encode("utf-8")


def render(relative: Path, language: str) -> bytes:
    if relative == TARGETS[0]:
        return render_skill(language)
    if relative in STATIC_TARGETS:
        source = (SOURCE / "openai.yaml").read_text(encoding="utf-8")
        rendered = [split_quoted_pair(line, language) for line in source.splitlines()]
        return ("\n".join(rendered) + "\n").encode("utf-8")
    return render_agent(SOURCE / "agents" / relative.name, language)


def normalized(data: bytes) -> bytes:
    """Make profile checks stable across Git's Windows line-ending conversion."""
    return data.replace(b"\r\n", b"\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", choices=LANGUAGES, default="en")
    parser.add_argument(
        "--output-dir",
        default=".",
        help="directory receiving the generated runtime (default: repository root)",
    )
    parser.add_argument("--check", action="store_true", help="verify active files match the selected profile")
    parser.add_argument("--check-all", action="store_true", help="parse both source profiles without changing active files")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    profiles = LANGUAGES if args.check_all else (args.language,)
    output_root = Path(args.output_dir)
    if not output_root.is_absolute():
        output_root = ROOT / output_root
    targets = TARGETS + STATIC_TARGETS
    for language in profiles:
        for relative in targets:
            expected = render(relative, language)
            target = output_root / relative
            if args.check or args.check_all:
                if args.check and (not target.is_file() or normalized(target.read_bytes()) != normalized(expected)):
                    raise SystemExit(f"ERROR: active runtime does not match profile {language!r}: {relative}")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(expected)
    if args.check_all:
        print("All runtime language profiles parsed successfully.")
    elif args.check:
        print(f"Active runtime matches profile {args.language!r}.")
    else:
        print(f"Runtime profile {args.language!r} materialized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
