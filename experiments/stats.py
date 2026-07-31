from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from wisa_agent.evaluation import paired_result


def values(data: dict, mode: str, field: str) -> dict[int, float]:
    result = {}
    for run in data[mode]["runs"]:
        if field == "reward":
            value = run["reward"]
        else:
            value = run["attack"][field]
        result[int(run["seed"])] = float(value)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", nargs="+", type=Path, required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--modes", nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = {}
    for path in args.input:
        data.update(json.loads(path.read_text(encoding="utf-8")))
    fields = (
        "reward",
        "unique_privileged_hosts",
        "unique_impacted_hosts",
        "successful_impact_count",
    )
    result = {}
    modes = args.modes if args.modes is not None else list(data)
    for mode in modes:
        if mode == args.reference:
            continue
        result[mode] = {}
        for field in fields:
            paired = paired_result(
                values(data, args.reference, field),
                values(data, mode, field),
            )
            result[mode][field] = asdict(paired)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
