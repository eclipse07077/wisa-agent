from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from optc_eval import (
    digest,
    labels,
    load_segments,
    matched_disagreement,
    selection_metrics,
)


def load(path: Path) -> tuple[dict, str]:
    content = path.read_bytes()
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle), hashlib.sha256(content).hexdigest()


def evaluate(
    manifest_path: Path,
    candidate_path: Path,
    events_path: Path,
    segments_path: Path,
    host: str,
) -> dict:
    manifest, manifest_sha256 = load(manifest_path)
    candidate, candidate_sha256 = load(candidate_path)
    if candidate["method"] != "ravel_cert_v4":
        raise ValueError("certified transport result is required")
    if candidate["input_manifest_sha256"] != manifest_sha256:
        raise ValueError("candidate input manifest mismatch")
    official = {
        str(node).upper()
        for node in manifest["seeds"]
    }
    selected = {
        str(node).upper()
        for node in candidate["selections"]["full"]["nodes"]
    }
    if not official or len(official) != len(selected):
        raise ValueError("matched unique budgets are required")
    universe = {
        str(node).upper()
        for node, _ in manifest["official_scores"]
    }
    segment_rows = load_segments(
        segments_path,
        f"SysClient{host}.systemia.com",
    )
    malicious, segment_labels, event_count = labels(
        events_path,
        segment_rows,
    )
    official_metrics = selection_metrics(
        official,
        malicious,
        universe,
    )
    candidate_metrics = selection_metrics(
        selected,
        malicious,
        universe,
    )
    segments = []
    no_decline = True
    for segment in segment_rows:
        current = segment_labels[segment.identifier]
        baseline = len(official & current)
        recovered = len(selected & current)
        covered = len(current & universe)
        if covered and recovered < baseline:
            no_decline = False
        segments.append(
            {
                "id": segment.identifier,
                "covered_malicious": covered,
                "official": baseline,
                "certified": recovered,
            }
        )
    improvement = (
        candidate_metrics["recovered"]
        > official_metrics["recovered"]
    )
    return {
        "method": "ravel_cert_actor_eval_v1",
        "host": host,
        "manifest_sha256": manifest_sha256,
        "candidate_sha256": candidate_sha256,
        "events_sha256": digest(events_path),
        "segments_sha256": digest(segments_path),
        "label_events": event_count,
        "score_universe": len(universe),
        "official": official_metrics,
        "certified": candidate_metrics,
        "matched_disagreement": matched_disagreement(
            official,
            selected,
            malicious,
        ),
        "segments": segments,
        "aggregate_improvement": improvement,
        "segment_no_decline": no_decline,
        "host_success": improvement and no_decline,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--segments", type=Path, required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(
        args.manifest,
        args.candidate,
        args.events,
        args.segments,
        args.host,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "host": result["host"],
                "official": result["official"]["recovered"],
                "certified": result["certified"]["recovered"],
                "aggregate_improvement": result[
                    "aggregate_improvement"
                ],
                "segment_no_decline": result[
                    "segment_no_decline"
                ],
            }
        )
    )


if __name__ == "__main__":
    main()
