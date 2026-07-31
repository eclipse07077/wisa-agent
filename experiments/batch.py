from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


MODES = (
    "sleep",
    "reactive",
    "layerchain",
    "report",
    "report_v9",
    "report_v10",
    "report_v11",
    "report_v12",
    "report_transition",
    "report_no_chain",
    "report_no_honeypot",
    "report_no_guard",
)
REDS = ("default", "chain")


def run_condition(
    runner: Path,
    output_dir: Path,
    mode: str,
    red: str,
    episodes: int,
    steps: int,
    seed: int,
) -> tuple[str, Path, str]:
    key = f"{mode}__{red}"
    output = output_dir / f"{key}.json"
    command = [
        sys.executable,
        str(runner),
        "--episodes",
        str(episodes),
        "--steps",
        str(steps),
        "--seed",
        str(seed),
        "--modes",
        mode,
        "--reds",
        red,
        "--output",
        str(output),
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    return key, output, completed.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="CAGE 일괄 실험")
    parser.add_argument("--episodes", type=int, default=30)
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--seed", type=int, default=3407)
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--modes", nargs="+", choices=MODES, default=MODES)
    parser.add_argument("--reds", nargs="+", choices=REDS, default=("default",))
    args = parser.parse_args()
    conditions = tuple(
        (mode, red) for red in args.reds for mode in args.modes
    )

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output_dir = output.parent / f"{output.stem}-parts"
    output_dir.mkdir(parents=True, exist_ok=True)
    runner = Path(__file__).with_name("run.py")
    outputs: dict[str, Path] = {}

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {
            pool.submit(
                run_condition,
                runner,
                output_dir,
                mode,
                red,
                args.episodes,
                args.steps,
                args.seed,
            ): f"{mode}__{red}"
            for mode, red in conditions
        }
        for future in as_completed(futures):
            key, condition_output, stdout = future.result()
            outputs[key] = condition_output
            print(stdout, flush=True)

    merged = {}
    for mode, red in conditions:
        key = f"{mode}__{red}"
        condition = json.loads(outputs[key].read_text(encoding="utf-8"))
        merged[key] = condition[key]
    output.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
