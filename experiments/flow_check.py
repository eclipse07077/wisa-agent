from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import time
from dataclasses import asdict
from pathlib import Path

from bear import deserialize_chain
from wisa_agent.tc.flow import FlowSelector


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            value.update(block)
    return value.hexdigest()


def load(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def compare(
    current: object,
    expected: object,
    tolerance: float,
) -> float:
    if isinstance(current, dict) and isinstance(expected, dict):
        if set(current) != set(expected):
            raise RuntimeError("mapping keys changed")
        return max(
            (
                compare(current[key], expected[key], tolerance)
                for key in current
            ),
            default=0.0,
        )
    if isinstance(current, (list, tuple)) and isinstance(
        expected,
        (list, tuple),
    ):
        if len(current) != len(expected):
            raise RuntimeError("sequence length changed")
        return max(
            (
                compare(left, right, tolerance)
                for left, right in zip(current, expected)
            ),
            default=0.0,
        )
    if isinstance(current, float) or isinstance(expected, float):
        difference = abs(float(current) - float(expected))
        if not math.isclose(
            float(current),
            float(expected),
            rel_tol=0.0,
            abs_tol=tolerance,
        ):
            raise RuntimeError("numeric value changed")
        return difference
    if current != expected:
        raise RuntimeError("discrete value changed")
    return 0.0


def check(score_path: Path, route_path: Path) -> dict:
    started = time.perf_counter()
    score = load(score_path)
    route = load(route_path)
    if route["input_manifest_sha256"] != digest(score_path):
        raise ValueError("route input digest mismatch")
    selector = FlowSelector(
        {
            str(node): float(value)
            for node, value in score["official_scores"]
        },
        {str(node) for node in score["seeds"]},
        tuple(
            deserialize_chain(chain)
            for chain in route["chains"]
        ),
    )
    modes = {}
    maximum_difference = 0.0
    for mode in ("anomaly", "responsibility", "flow", "full"):
        selection = selector.select(mode=mode)
        current = {
            "nodes": selection.nodes,
            "gains": selection.gains,
            "objective": selection.objective,
            "candidates": selection.candidates,
            "budget": selection.budget,
            "values": [
                asdict(value)
                for value in selection.values
            ],
        }
        maximum_difference = max(
            maximum_difference,
            compare(
                current,
                route["selections"][mode],
                1e-14,
            ),
        )
        modes[mode] = {
            "nodes": len(selection.nodes),
            "objective": selection.objective,
        }
    return {
        "method": "flowsub_execution_equivalence_v1",
        "score_sha256": digest(score_path),
        "route_sha256": digest(route_path),
        "modes": modes,
        "selection_equivalent": True,
        "absolute_tolerance": 1e-14,
        "maximum_absolute_difference": maximum_difference,
        "runtime_seconds": time.perf_counter() - started,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--score", type=Path, required=True)
    parser.add_argument("--route", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = check(args.score, args.route)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
