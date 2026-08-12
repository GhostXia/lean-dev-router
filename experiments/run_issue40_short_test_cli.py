"""Run the Issue #40 short-test matrix through fresh `codex exec` sessions.

Each cell = variant x language x run, executed as an independent non-interactive
Codex session with a fixed model/reasoning effort. Real token counts are read
back from the session JSONL files (event_msg type=token_count).

Usage:
    python -B run_issue40_short_test_cli.py [--out DIR] [--workers N]

Requires the codex CLI path from CODEX_CLI env or the local default below.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

CODEX_CLI = os.environ.get(
    "CODEX_CLI",
    r"C:\Users\xiach\AppData\Local\OpenAI\Codex\bin\8e8bf206e63ac436\codex.exe",
)

VARIANTS = {
    "E0": ("en", r"skill-variants\en\SKILL.md"),
    "C0": ("zh", r"skill-variants\zhcn\SKILL.md"),
    "E1": ("en", r"skill-variants\en-optimized\SKILL.md"),
    "C1": ("zh", r"skill-variants\zhcn-optimized\SKILL.md"),
}
RUNS = 3
LANGUAGES = ("en", "zh")


def prompt_text(packet_dir: Path, language: str, variant: str, skill_path: str) -> str:
    template = (packet_dir / f"{language}.md").read_text(encoding="utf-8")
    return (
        template.replace("{{SKILL_PATH}}", skill_path)
        .replace("{{VARIANT}}", variant)
    )


def run_one(cell, workdir: Path, packet_dir: Path, out_dir: Path, logs_dir: Path):
    variant, language, run = cell
    variant_folder, rel_path = VARIANTS[variant]
    skill_path = str((workdir / rel_path).resolve())
    prompt = prompt_text(packet_dir, language, variant, skill_path)
    prompt_file = out_dir / f"prompt_{variant}_{language}_r{run}.txt"
    prompt_file.write_text(prompt, encoding="utf-8")

    log_file = logs_dir / f"run_{variant}_{language}_r{run}.log"
    started = time.time()
    proc = subprocess.run(
        [
            CODEX_CLI,
            "exec",
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
    return {
        "cell": cell,
        "ok": proc.returncode == 0 and session_id is not None,
        "returncode": proc.returncode,
        "elapsed_s": round(elapsed, 2),
        "session_id": session_id,
        "log_file": log_file.name,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="experiments/issue-40-cli")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    workdir = Path(r"D:\lean-dev-router-wt\issue-40-contract-dedup")
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
            pool.submit(run_one, cell, workdir, packet_dir, out_dir, logs_dir): cell
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

    manifest = out_dir / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "experiment": "issue-40-short-test-cli",
                "model": "deepseek-v4-flash",
                "reasoning_effort": "max (config default)",
                "results": results,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    ok = sum(1 for r in results if r.get("ok"))
    print(f"done: {ok}/{len(cells)} ok; manifest at {manifest}")


if __name__ == "__main__":
    main()
