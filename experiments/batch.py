from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


CONDITIONS = tuple(
    (mode, red)
    for red in ("default", "chain")
    for mode in ("sleep", "reactive", "layerchain")
)


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
    args = parser.parse_args()

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
            for mode, red in CONDITIONS
        }
        for future in as_completed(futures):
            key, condition_output, stdout = future.result()
            outputs[key] = condition_output
            print(stdout, flush=True)

    merged = {}
    for mode, red in CONDITIONS:
        key = f"{mode}__{red}"
        condition = json.loads(outputs[key].read_text(encoding="utf-8"))
        merged[key] = condition[key]
    output.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
