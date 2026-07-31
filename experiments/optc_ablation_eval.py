from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.optc_eval import (
    digest,
    labels,
    load_manifest,
    load_segments,
    selection_metrics,
)


def evaluate_ablation(
    manifest_path: Path,
    ablation_path: Path,
    events_path: Path,
    segments_path: Path,
    host: str,
) -> dict:
    manifest, manifest_sha256 = load_manifest(manifest_path)
    ablation, ablation_sha256 = load_manifest(ablation_path)
    if ablation["method"] != "ravel_transport_ablation_v1":
        raise ValueError("registered transport ablation is required")
    if ablation["input_manifest_sha256"] != manifest_sha256:
        raise ValueError("ablation input manifest mismatch")
    if (
        int(manifest["root_budget"]) != 512
        or int(ablation["budget"]) != 512
    ):
        raise ValueError("registered budget mismatch")
    universe = {
        str(node).upper()
        for node, _ in manifest["official_scores"]
    }
    target = f"SysClient{host}.systemia.com"
    segment_rows = load_segments(segments_path, target)
    malicious, segment_labels, event_count = labels(
        events_path,
        segment_rows,
    )
    results = {}
    for method in ("topology", "rank"):
        selected = {
            str(node).upper()
            for node in ablation["selections"][method]["nodes"]
        }
        if len(selected) != 512:
            raise ValueError("ablation must contain 512 unique nodes")
        results[method] = {
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
    return {
        "method": "corrected_optc_ablation_eval_v1",
        "host": host,
        "manifest_sha256": manifest_sha256,
        "ablation_sha256": ablation_sha256,
        "events_sha256": digest(events_path),
        "segments_sha256": digest(segments_path),
        "label_events": event_count,
        "score_universe": len(universe),
        "selections": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--ablation", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--segments", type=Path, required=True)
    parser.add_argument("--host", choices=("0201", "0501"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate_ablation(
        args.manifest,
        args.ablation,
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
                method: values["recovered"]
                for method, values in result["selections"].items()
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
