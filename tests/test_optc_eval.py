import csv
import gzip
import hashlib
import json
from pathlib import Path

from experiments.optc_eval import (
    evaluate,
    hypergeometric_tail,
    hypergeometric_two_sided,
    matched_disagreement,
    selection_metrics,
)


def write_gzip(path: Path, payload: dict) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle)


def test_selection_metrics_uses_covered_recall():
    result = selection_metrics({"A", "B"}, {"B", "C"}, {"A", "B"})
    assert result["recovered"] == 1
    assert result["covered_malicious"] == 1
    assert result["covered_recall"] == 1.0
    assert result["mcc"] == 0.0
    assert result["random_budget"]["expected_recovered"] == 1.0


def test_hypergeometric_tail_matches_small_exact_distribution():
    assert abs(hypergeometric_tail(4, 2, 2, 2) - 1 / 6) < 1e-12
    assert abs(hypergeometric_tail(4, 2, 2, 1) - 5 / 6) < 1e-12


def test_two_sided_hypergeometric_matches_small_exact_distribution():
    assert abs(hypergeometric_two_sided(4, 2, 2, 2) - 1 / 3) < 1e-12
    assert abs(hypergeometric_two_sided(4, 2, 2, 1) - 1.0) < 1e-12


def test_matched_disagreement_conditions_on_changed_slots():
    result = matched_disagreement(
        {"A", "B", "C"},
        {"B", "C", "D"},
        {"D"},
    )
    assert result["changed_slots"] == 1
    assert result["baseline_only_malicious"] == 0
    assert result["candidate_only_malicious"] == 1
    assert result["recovered_delta"] == 1
    assert abs(
        result["conditional_null"]["p_candidate_at_least_observed"]
        - 0.5
    ) < 1e-12


def test_corrected_evaluator_applies_fixed_budget_and_segments(tmp_path):
    official = [f"N{index:03d}" for index in range(512)]
    selected = official[1:] + ["MALICIOUS"]
    manifest = {
        "root_budget": 512,
        "seeds": official,
        "official_scores": [
            [node, float(512 - index)]
            for index, node in enumerate(official + ["MALICIOUS"])
        ],
    }
    manifest_path = tmp_path / "manifest.json.gz"
    write_gzip(manifest_path, manifest)
    ravel = {
        "method": "ravel_v6",
        "input_manifest_sha256": hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest(),
        "budget": 512,
        "selections": {"full": {"nodes": selected}},
    }
    ravel_path = tmp_path / "ravel.json.gz"
    write_gzip(ravel_path, ravel)
    events_path = tmp_path / "corrected.json.gz"
    with gzip.open(events_path, "wt", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "actorID": "MALICIOUS",
                    "hostname": "SysClient0201.systemia.com",
                    "pid": 7,
                    "timestamp": "2019-09-23T11:23:00-04:00",
                }
            )
            + "\n"
        )
    segments_path = tmp_path / "corrected.csv"
    with segments_path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerow(
            [
                "SysClient0201.systemia.com",
                7,
                "2019-09-23T11:22:00-04:00",
                "2019-09-23T11:24:00-04:00",
            ]
        )
    result = evaluate(
        manifest_path,
        ravel_path,
        events_path,
        segments_path,
        "0201",
    )
    assert result["official"]["recovered"] == 0
    assert result["ravel_v6"]["recovered"] == 1
    assert result["matched_disagreement"]["recovered_delta"] == 1
    assert result["host_success"] is True
