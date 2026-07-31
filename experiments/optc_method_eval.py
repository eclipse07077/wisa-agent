from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.optc_eval import (
    digest,
    labels,
    load_manifest,
    load_segments,
    matched_disagreement,
    selection_metrics,
)


def evaluate_methods(
    manifest_path: Path,
    route_path: Path,
    v5_path: Path,
    v6_path: Path,
    events_path: Path,
    segments_path: Path,
    host: str,
) -> dict:
    manifest, manifest_sha256 = load_manifest(manifest_path)
    route, route_sha256 = load_manifest(route_path)
    v5, v5_sha256 = load_manifest(v5_path)
    v6, v6_sha256 = load_manifest(v6_path)
    if route["method"] != "flowsub_v1":
        raise ValueError("registered FlowSub result is required")
    if v5["method"] != "ravel_v5" or v6["method"] != "ravel_v6":
        raise ValueError("registered RAVEL results are required")
    if route["input_manifest_sha256"] != manifest_sha256:
        raise ValueError("FlowSub input manifest mismatch")
    for result in (v5, v6):
        if result["input_manifest_sha256"] != manifest_sha256:
            raise ValueError("RAVEL input manifest mismatch")
        if result["route_manifest_sha256"] != route_sha256:
            raise ValueError("RAVEL route manifest mismatch")
    if any(
        int(value) != 512
        for value in (
            manifest["root_budget"],
            route["budget"],
            v5["budget"],
            v6["budget"],
        )
    ):
        raise ValueError("registered budget mismatch")

    universe = {
        str(node).upper()
        for node, _ in manifest["official_scores"]
    }
    selections = {
        "velox": {str(node).upper() for node in manifest["seeds"]},
        "flowsub": {
            str(node).upper()
            for node in route["selections"]["full"]["nodes"]
        },
        "ravel_v5": {
            str(node).upper()
            for node in v5["selections"]["full"]["nodes"]
        },
        "ravel_v6": {
            str(node).upper()
            for node in v6["selections"]["full"]["nodes"]
        },
    }
    for name, selected in selections.items():
        if len(selected) != 512:
            raise ValueError(f"{name} must contain 512 unique nodes")
        if not selected <= universe:
            raise ValueError(f"{name} is outside the score universe")

    target = f"SysClient{host}.systemia.com"
    segment_rows = load_segments(segments_path, target)
    malicious, segment_labels, event_count = labels(
        events_path,
        segment_rows,
    )
    evaluated = {}
    for name, selected in selections.items():
        evaluated[name] = {
            **selection_metrics(selected, malicious, universe),
            "segments": [
                {
                    "id": segment.identifier,
                    "covered_malicious": len(
                        segment_labels[segment.identifier] & universe
                    ),
                    "recovered": len(
                        segment_labels[segment.identifier] & selected
                    ),
                }
                for segment in segment_rows
            ],
        }
    baseline = selections["velox"]
    comparisons = {
        f"velox_to_{name}": matched_disagreement(
            baseline,
            selections[name],
            malicious,
        )
        for name in ("flowsub", "ravel_v5", "ravel_v6")
    }
    comparisons["ravel_v5_to_ravel_v6"] = matched_disagreement(
        selections["ravel_v5"],
        selections["ravel_v6"],
        malicious,
    )
    return {
        "method": "corrected_optc_frozen_method_eval_v1",
        "host": host,
        "comparison_status": (
            "post_hoc_after_host_labels"
            if host == "0501"
            else "preregistered_before_host_labels"
        ),
        "manifest_sha256": manifest_sha256,
        "route_sha256": route_sha256,
        "v5_sha256": v5_sha256,
        "v6_sha256": v6_sha256,
        "events_sha256": digest(events_path),
        "segments_sha256": digest(segments_path),
        "label_events": event_count,
        "score_universe": len(universe),
        "selections": evaluated,
        "comparisons": comparisons,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--route", type=Path, required=True)
    parser.add_argument("--v5", type=Path, required=True)
    parser.add_argument("--v6", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--segments", type=Path, required=True)
    parser.add_argument("--host", choices=("0201", "0501"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate_methods(
        args.manifest,
        args.route,
        args.v5,
        args.v6,
        args.events,
        args.segments,
        args.host,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                name: values["recovered"]
                for name, values in result["selections"].items()
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
