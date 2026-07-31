from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from wisa_agent.evaluation import paired_result


def values(data: dict, mode: str, field: str) -> dict[int, float]:
    result = {}
    for run in data[mode]["runs"]:
        value = run["reward"] if field == "reward" else run["attack"][field]
        result[int(run["seed"])] = float(value)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--mode", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    fields = (
        "reward",
        "unique_privileged_hosts",
        "unique_impacted_hosts",
        "successful_impact_count",
    )
    result = {
        field: asdict(
            paired_result(
                values(reference, args.mode, field),
                values(candidate, args.mode, field),
            )
        )
        for field in fields
    }
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
