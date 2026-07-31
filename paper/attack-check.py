from __future__ import annotations

import gzip
import hashlib
import json
import math
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def load_gzip(path: str) -> dict:
    with gzip.open(ROOT / path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def close(actual: float, expected: float) -> None:
    assert math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-12)


def check_development(path: str, official: int, certified: int, changes: int) -> None:
    result = load(path)
    assert result["official"]["budget"] == result["certified"]["budget"] == 512
    assert result["official"]["recovered"] == official
    assert result["certified"]["recovered"] == certified
    assert result["matched_disagreement"]["changed_slots"] == changes
    assert result["segment_no_decline"] is True
    assert all(
        row["certified"] >= row["official"]
        for row in result["segments"]
        if row["covered_malicious"] > 0
    )


def main() -> None:
    manifest = load("paper/attack.json")
    summary = load("results/ravel.json")
    assert manifest["schema"] == 3
    assert manifest["status"] == "complete_heldout_safety_falsified"
    assert manifest["method"] == summary["method"] == "ravel_cert_v4"
    assert summary["status"] == "heldout_actor_safety_falsified"
    for name, expected in manifest["sha256"].items():
        assert digest(ROOT / name) == expected, name

    plan = load("results/cert-plan.json")
    assert plan["label_opened"] is False
    assert plan["budget"] == 512
    assert plan["method"]["certifier"] == "global_uuid_universal_cut_iff_full_fracture"
    assert plan["method"]["allocation"] == "exact_lexicographic_matching"
    assert plan["method"]["thresholds"] == []
    assert plan["method"]["label_inputs"] == []
    assert set(plan["comparators"]) == {
        "official_velox_top_512",
        "flowsub_full_top_512",
        "ravel_v6_top_512",
    }
    assert len(plan["endpoints"]) == 4
    assert all(not row["label_opened"] for row in plan["amendments"])
    for name, expected in plan["code_sha256"].items():
        assert digest(ROOT / name) == expected, name

    frozen = load("results/frozen-051.json")
    frozen_files = {row["name"]: row for row in frozen["files"]}
    assert set(frozen_files) == {
        "cert-051.json.gz",
        "cert-plan.json",
        "route-051.json.gz",
        "score-051.json.gz",
        "v6-051.json.gz",
    }
    assert frozen_files["score-051.json.gz"]["bytes"] == 33246876
    for name in ("cert-051.json.gz", "cert-plan.json", "route-051.json.gz", "v6-051.json.gz"):
        assert digest(ROOT / "results" / name) == frozen_files[name]["sha256"]
    assert frozen_files["score-051.json.gz"]["sha256"] == summary["receipts"]["score_sha256"]
    assert digest(ROOT / "results/frozen-051.json") == summary["receipts"]["freeze_sha256"]

    audit = load("results/audit-051.json")
    assert digest(ROOT / "results/audit-051.json") == summary["receipts"]["audit_sha256"]
    assert audit["method"] == "certified_label_barrier_audit_v4"
    assert audit["frozen_sha256"] == summary["receipts"]["freeze_sha256"]
    assert [
        audit["budget"],
        audit["flowsub_nodes"],
        audit["candidate_transports"],
        audit["certified_candidates"],
        audit["source_transports"],
        audit["source_certified_transports"],
        audit["certified_transports"],
        audit["changed_from_source"],
        audit["source_agreement"],
        audit["source_distance"],
        audit["witnessed_routes"],
    ] == [512, 512, 113495, 4, 59, 4, 4, 55, 457, 55, 5]

    candidate = load_gzip("results/cert-051.json.gz")
    assert candidate["method"] == "ravel_cert_v4"
    assert candidate["rule"] == "lexicographic_certificate_projection"
    assert candidate["input_manifest_sha256"] == summary["receipts"]["score_sha256"]
    assert candidate["source_sha256"] == summary["receipts"]["source_sha256"]
    assert candidate["route_manifest_sha256"] == summary["receipts"]["routes_sha256"]
    assert [
        candidate["budget"],
        candidate["candidate_transports"],
        candidate["certified_candidates"],
        candidate["source_transports"],
        candidate["source_certified_transports"],
        candidate["certified_transports"],
        candidate["changed_from_source"],
        candidate["source_agreement"],
        candidate["source_distance"],
    ] == [512, 113495, 4, 59, 4, 4, 55, 457, 55]
    selection = candidate["selections"]["full"]
    certificate = candidate["certificate"]
    assert len(selection["nodes"]) == len(set(selection["nodes"])) == 512
    assert selection["budget"] == 512
    close(selection["mass"], 1.0)
    assert certificate == {
        "roots": 512,
        "nodes": 512,
        "budget": 512,
        "root_degree_min": 1,
        "root_degree_max": 1,
        "node_degree_max": 1,
        "mass": 1.0,
        "objective": 4.0,
        "optimal": True,
    }

    receipt = load("results/label-051.json")
    result = load("results/eval-cert-051.json")
    assert receipt["audit_completed_before_label_access"] is True
    assert receipt["method_locked_after_label_access"] is True
    assert receipt["label_access_authorized_at"] < receipt["evaluation_written_at"]
    receipt_keys = {
        "frozen": "freeze_sha256",
        "audit": "audit_sha256",
        "labels": "labels_sha256",
        "evaluation": "evaluation_sha256",
    }
    for name, summary_name in receipt_keys.items():
        assert receipt["sha256"][name] == summary["receipts"][summary_name]
    assert digest(ROOT / "results/eval-cert-051.json") == receipt["sha256"]["evaluation"]
    assert result["label_rows"] == result["metrics"]["official"]["malicious"] == 114
    assert result["score_universe"] == 1470624
    assert [
        result["metrics"][name]["budget"]
        for name in ("official", "flowsub", "ravel_v6", "certified")
    ] == [512, 512, 512, 512]
    assert [
        result["metrics"][name]["recovered"]
        for name in ("official", "flowsub", "ravel_v6", "certified")
    ] == [4, 8, 2, 3]
    assert result["certified_transports"] == 4
    assert result["activated"] is True
    assert result["comparisons"]["official"]["changed_slots"] == 4
    assert result["comparisons"]["official"]["baseline_only_malicious"] == 1
    assert result["comparisons"]["official"]["candidate_only_malicious"] == 0
    assert result["comparisons"]["ravel_v6"]["changed_slots"] == 55
    assert result["comparisons"]["ravel_v6"]["recovered_delta"] == 1
    for endpoint in (
        "primary_safety",
        "secondary_efficacy",
        "competitive_noninferiority",
        "strict_all_comparators",
    ):
        assert result[endpoint] is False
        assert receipt["results"][endpoint] is False
        assert summary["heldout"]["registered_endpoints"][endpoint] is False

    check_development("results/eval-cert-501.json", 7, 8, 7)
    check_development("results/eval-cert-201.json", 2, 2, 11)

    latex = (ROOT / "paper/attack.tex").read_text(encoding="utf-8")
    markdown = (ROOT / "paper/attack.md").read_text(encoding="utf-8")
    claims = (ROOT / "paper/claims.md").read_text(encoding="utf-8")
    assert latex.isascii()
    assert "genuinely held-out H051" in latex
    assert "All four registered success outcomes fail" in latex
    assert "not a new detector or state-of-the-art result" in latex
    assert "No method or endpoint changes follow this result" in latex
    assert "Velox roots & 4" in latex
    assert "FlowSub & 8" in latex
    assert "Fractional \\(M_6\\) & 2" in latex
    assert "\\ravelc & 3" in latex
    assert "모든 비교군 strict superiority는 전부 실패했다" in markdown
    assert "SOTA나 성능 우월성 논문이 아니다" in markdown
    assert "SOTA actor attribution" in claims
    assert "기각" in claims
    for forbidden in (
        "complete_external_hypothesis_rejected",
        "external_evaluation_pending",
        "RAVEL이 FlowSub보다 성능이 높다",
    ):
        assert forbidden not in latex + markdown

    pdf = (ROOT / "output/pdf/attack.pdf").read_bytes()
    pages = len(re.findall(rb"/Type\s*/Page(?!s)", pdf))
    assert pages == manifest["paper"]["pages"]
    assert pages <= 12
    print("attack paper evidence check passed")


if __name__ == "__main__":
    main()
