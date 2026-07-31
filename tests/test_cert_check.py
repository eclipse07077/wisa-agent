import gzip
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from experiments.bear import calibration_node_maxima
from experiments.cert_check import audit
from experiments.flow import serialize_chain
from experiments.freeze import freeze
from wisa_agent.method import Chain, ChainEdge, Predicate, Stage
from wisa_agent.tc.cert import certify_graph
from wisa_agent.tc.transport import ExactTransport


def write_gzip(path: Path, payload: dict) -> str:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def proof_chain() -> Chain:
    predicates = tuple(
        Predicate(
            predicate_id=f"p{index}",
            stage=Stage.LIFECYCLE,
            layer="host",
            relation="relation",
            timestamp=float(index),
            context=frozenset(),
            confidence=1.0,
            severity=1.0,
            target=group[0],
            mission_relevant=False,
            evidence_ids=(),
            details={"endpoints": group},
        )
        for index, group in enumerate((("R000", "X"), ("X",)))
    )
    return Chain(
        chain_id="route",
        predicates=predicates,
        edges=(
            ChainEdge(
                source_id="p0",
                target_id="p1",
                score=1.0,
                factors=(),
            ),
        ),
        score=1.0,
    )


def test_certified_bundle_audit_recomputes_witness(tmp_path):
    roots = [f"R{index:03d}" for index in range(512)]
    universe = [
        [root, float(1000 - index)]
        for index, root in enumerate(roots)
    ] + [["X", -1.0]]
    score_path = tmp_path / "score-051.json.gz"
    route_path = tmp_path / "route-051.json.gz"
    source_path = tmp_path / "v6-051.json.gz"
    cert_path = tmp_path / "cert-051.json.gz"
    plan_path = tmp_path / "cert-plan.json"
    frozen_path = tmp_path / "frozen-051.json"
    validation_path = tmp_path / "validation"
    validation_path.mkdir()
    (validation_path / "loss.csv").write_text(
        "loss,srcnode,dstnode\n1.0,A,B\n2.0,B,C\n",
        encoding="utf-8",
    )
    calibration, calibration_sha256, calibration_files = (
        calibration_node_maxima(validation_path)
    )
    score_sha256 = write_gzip(
        score_path,
        {
            "dataset": "optc_h051",
            "root_budget": 512,
            "official_scores": universe,
            "seeds": roots,
        },
    )
    route_sha256 = write_gzip(
        route_path,
        {
            "method": "flowsub_v1",
            "dataset": "optc_h051",
            "input_manifest_sha256": score_sha256,
            "selections": {"full": {"nodes": roots}},
        },
    )
    chain = proof_chain()
    exact = ExactTransport(
        {str(node): float(score) for node, score in universe},
        calibration,
        set(roots),
        (chain,),
    )
    source_selection, source_certificate = exact.select()
    source_sha256 = write_gzip(
        source_path,
        {
            "method": "ravel_v6",
            "dataset": "optc_h051",
            "input_manifest_sha256": score_sha256,
            "route_manifest_sha256": route_sha256,
            "calibration_sha256": calibration_sha256,
            "calibration_files": calibration_files,
            "calibration_maximum": max(calibration),
            "chains": [serialize_chain(chain)],
            "certificate": asdict(source_certificate),
            "selections": {
                "full": {
                    "nodes": source_selection.nodes,
                    "ledger": source_selection.ledger,
                    "candidates": source_selection.candidates,
                    "budget": source_selection.budget,
                    "mass": source_selection.mass,
                    "expanded": source_selection.expanded,
                    "values": [
                        asdict(value)
                        for value in source_selection.values
                    ],
                }
            },
        },
    )
    result = certify_graph(
        exact.edges,
        exact.seeds,
        exact.ledger.chains,
        {str(node) for node, _ in universe},
        source_selection,
    )
    write_gzip(
        cert_path,
        {
            "method": "ravel_cert_v4",
            "dataset": "optc_h051",
            "input_manifest_sha256": score_sha256,
            "source_sha256": source_sha256,
            "route_manifest_sha256": route_sha256,
            "calibration_sha256": calibration_sha256,
            "calibration_files": calibration_files,
            "candidate_transports": result.candidate_transports,
            "certified_candidates": result.certified_candidates,
            "source_transports": result.source_transports,
            "source_certified_transports": (
                result.source_certified_transports
            ),
            "certified_transports": result.certified_transports,
            "changed_from_source": result.changed_from_source,
            "selected_e_value": result.selected_e_value,
            "maximum_e_value": result.maximum_e_value,
            "secondary_objective": result.secondary_objective,
            "source_agreement": result.source_agreement,
            "source_distance": result.source_distance,
            "witnesses": [
                asdict(witness)
                for witness in result.witnesses
            ],
            "certificate": asdict(result.certificate),
            "selections": {
                "full": {
                    "nodes": result.selection.nodes,
                    "ledger": result.selection.ledger,
                    "candidates": result.selection.candidates,
                    "budget": result.selection.budget,
                    "mass": result.selection.mass,
                    "expanded": result.selection.expanded,
                    "values": [
                        asdict(value)
                        for value in result.selection.values
                    ],
                }
            },
        },
    )
    plan_path.write_text(
        json.dumps(
            {
                "label_opened": False,
                "budget": 512,
                "method": {
                    "source": "ravel_v6_candidate_graph_and_comparator",
                    "certifier": (
                        "global_uuid_universal_cut_iff_full_fracture"
                    ),
                    "allocation": "exact_lexicographic_matching",
                    "primary_objective": (
                        "maximum_certified_transport_count"
                    ),
                    "secondary_objective": (
                        "maximum_ravel_v6_assignment_agreement_among_primary_optima"
                    ),
                    "tertiary_objective": (
                        "maximum_total_conformal_evidence_among_primary_secondary_optima"
                    ),
                    "dominance_scale": (
                        "budget_plus_one_squared_budget_plus_one_and_one"
                    ),
                    "fallback": "private_detector_root",
                    "thresholds": [],
                    "label_inputs": [],
                },
                "comparators": [
                    "official_velox_top_512",
                    "flowsub_full_top_512",
                    "ravel_v6_top_512",
                ],
                "endpoints": {
                    "primary_safety": (
                        "certified_transports_gt_0_and_certified_recovered_ge_official_recovered"
                    ),
                    "secondary_efficacy": (
                        "certified_transports_gt_0_and_certified_recovered_gt_official_recovered"
                    ),
                    "competitive_noninferiority": (
                        "certified_transports_gt_0_and_certified_recovered_ge_flowsub_recovered"
                    ),
                    "strict_all_comparators": (
                        "certified_transports_gt_0_and_certified_recovered_gt_max_official_flowsub_ravel_v6"
                    ),
                },
                "code_sha256": {},
            }
        ),
        encoding="utf-8",
    )
    frozen_path.write_text(
        json.dumps(
            freeze(
                [
                    score_path,
                    route_path,
                    source_path,
                    cert_path,
                    plan_path,
                ]
            )
        ),
        encoding="utf-8",
    )
    result = audit(
        frozen_path,
        tmp_path,
        Path.cwd(),
        validation_path,
    )
    assert result["certified_transports"] == 1
    assert result["witnessed_routes"] == 1
