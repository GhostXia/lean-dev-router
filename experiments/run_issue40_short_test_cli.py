"""Run the Issue #40 short-test matrix through fresh `codex exec` sessions.

Each cell = variant x language x run, executed as an independent non-interactive
Codex session with a fixed model/reasoning effort. Real token counts are read
back from the session JSONL files (event_msg type=token_count).

Usage:
    python -B run_issue40_short_test_cli.py [--out DIR] [--workers N]

The CLI is selected by --codex-cli, CODEX_CLI, or portable PATH discovery.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

VARIANTS = {
    "E0": Path("skill-variants") / "en" / "SKILL.md",
    "C0": Path("skill-variants") / "zhcn" / "SKILL.md",
    "E1": Path("skill-variants") / "en-optimized" / "SKILL.md",
    "C1": Path("skill-variants") / "zhcn-optimized" / "SKILL.md",
}
RUNS = 3
LANGUAGES = ("en", "zh")
REQUIRED_TOKEN_EVENTS = 2


def prompt_text(packet_dir: Path, language: str, variant: str, skill_path: str) -> str:
    template = (packet_dir / f"{language}.md").read_text(encoding="utf-8")
    return (
        template.replace("{{SKILL_PATH}}", skill_path)
        .replace("{{VARIANT}}", variant)
    )


def find_session_file(sessions_dir: Path, session_id: str) -> Path | None:
    return next(sessions_dir.rglob(f"*{session_id}*.jsonl"), None)


def read_token_events(session_file: Path) -> list[dict[str, object]]:
    events = []
    for line in session_file.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        payload = record.get("payload", {})
        if record.get("type") != "event_msg" or payload.get("type") != "token_count":
            continue
        usage = payload.get("info", {}).get("last_token_usage")
        if not isinstance(usage, dict):
            continue
        event = {"timestamp": record.get("timestamp"), **usage}
        event["uncached_input_tokens"] = usage.get("input_tokens", 0) - usage.get(
            "cached_input_tokens", 0
        )
        events.append(event)
    return events


def run_one(
    cell,
    workdir: Path,
    packet_dir: Path,
    out_dir: Path,
    logs_dir: Path,
    codex_cli: str,
    sessions_dir: Path,
):
    variant, language, run = cell
    skill_path = str((workdir / VARIANTS[variant]).resolve())
    prompt = prompt_text(packet_dir, language, variant, skill_path)
    prompt_file = out_dir / f"prompt_{variant}_{language}_r{run}.txt"
    prompt_file.write_text(prompt, encoding="utf-8")

    log_file = logs_dir / f"run_{variant}_{language}_r{run}.log"
    started = time.time()
    proc = subprocess.run(
        [
            codex_cli,
            "exec",
            "--config",
            'model_reasoning_effort="max"',
            "--skip-git-repo-check",
            "-C",
            str(workdir),
            "-s",
            "read-only",
            "-m",
            "deepseek-v4-flash",
            prompt,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        cwd=str(workdir),
    )
    elapsed = time.time() - started
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    log_file.write_text(stdout + "\n---STDERR---\n" + stderr, encoding="utf-8")
    m = re.search(r"session id: ([0-9a-f-]+)", stdout)
    session_id = m.group(1) if m else None
    session_file = find_session_file(sessions_dir, session_id) if session_id else None
    token_events = read_token_events(session_file) if session_file else []
    return {
        "cell": cell,
        "ok": (
            proc.returncode == 0
            and session_id is not None
            and session_file is not None
            and len(token_events) >= REQUIRED_TOKEN_EVENTS
        ),
        "returncode": proc.returncode,
        "elapsed_s": round(elapsed, 2),
        "session_id": session_id,
        "session_file": session_file.name if session_file else None,
        "token_events": token_events,
        "log_file": log_file.name,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="experiments/issue-40-cli")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--workdir", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--codex-cli", default=os.environ.get("CODEX_CLI"))
    parser.add_argument(
        "--sessions-dir",
        type=Path,
        default=Path(os.environ.get("CODEX_SESSIONS_DIR", Path.home() / ".codex" / "sessions")),
    )
    args = parser.parse_args()

    workdir = args.workdir.resolve()
    codex_cli = args.codex_cli or shutil.which("codex")
    if not codex_cli:
        parser.error("codex CLI not found; pass --codex-cli or set CODEX_CLI")
    if not args.sessions_dir.is_dir():
        parser.error("Codex sessions directory not found; pass --sessions-dir or set CODEX_SESSIONS_DIR")
    packet_dir = workdir / "experiments" / "issue-40-task-packets"
    out_dir = workdir / args.out
    logs_dir = out_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    cells = [
        (variant, lang, run)
        for variant in ("E0", "C0", "E1", "C1")
        for lang in LANGUAGES
        for run in (1, 2, 3)
    ]
    # interleaved order: rotate language/variant instead of grouping
    cells = sorted(cells, key=lambda c: (c[2], (c[1] == "zh"), c[0]))

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {
            pool.submit(
                run_one,
                cell,
                workdir,
                packet_dir,
                out_dir,
                logs_dir,
                codex_cli,
                args.sessions_dir,
            ): cell
            for cell in cells
        }
        for fut in as_completed(futs):
            cell = futs[fut]
            try:
                res = fut.result()
            except Exception as exc:
                res = {"cell": cell, "ok": False, "error": str(exc)}
            results.append(res)
            print(json.dumps(res, ensure_ascii=False))

    results.sort(key=lambda result: tuple(result["cell"]))
    manifest = out_dir / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "experiment": "issue-40-short-test-cli",
                "model": "deepseek-v4-flash",
                "reasoning_effort": "max (explicit command override)",
                "results": results,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    ok = sum(1 for r in results if r.get("ok"))
    print(f"done: {ok}/{len(cells)} ok; manifest at {manifest}")
    return 0 if ok == len(cells) else 1


if __name__ == "__main__":
    raise SystemExit(main())
