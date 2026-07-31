from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from dataclasses import asdict
from pathlib import Path

from bear import calibration_node_maxima, deserialize_chain
from frozen_check import check_frozen
from wisa_agent.tc.cert import certify_graph
from wisa_agent.tc.ravel import (
    TransportEdge,
    TransportSelection,
)
from wisa_agent.tc.transport import ExactTransport, TransportCertificate


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            value.update(block)
    return value.hexdigest()


def read(path: Path) -> dict:
    if path.name.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(path.read_text(encoding="utf-8"))


def unique(values: list[str], budget: int, name: str) -> set[str]:
    nodes = {str(value).upper() for value in values}
    if len(values) != budget or len(nodes) != budget:
        raise ValueError(f"{name} is not a unique exact-budget selection")
    return nodes


def source_selection(payload: dict) -> TransportSelection:
    current = payload["selections"]["full"]
    return TransportSelection(
        mode="full",
        nodes=tuple(current["nodes"]),
        ledger=float(current["ledger"]),
        candidates=int(current["candidates"]),
        budget=int(current["budget"]),
        values=tuple(
            TransportEdge(**value)
            for value in current["values"]
        ),
        mass=float(current["mass"]),
        expanded=int(current["expanded"]),
    )


def audit(
    frozen_path: Path,
    directory: Path,
    repository: Path,
    validation_losses: Path,
) -> dict:
    files = check_frozen(frozen_path, directory)
    required = {
        "score-051.json.gz",
        "route-051.json.gz",
        "v6-051.json.gz",
        "cert-051.json.gz",
        "cert-plan.json",
    }
    if required - set(files):
        raise ValueError("certified bundle is incomplete")
    score_path = files["score-051.json.gz"]
    route_path = files["route-051.json.gz"]
    source_path = files["v6-051.json.gz"]
    cert_path = files["cert-051.json.gz"]
    plan_path = files["cert-plan.json"]
    score = read(score_path)
    route = read(route_path)
    source = read(source_path)
    cert = read(cert_path)
    plan = read(plan_path)
    if any(
        value != "optc_h051"
        for value in (
            score["dataset"],
            route["dataset"],
            source["dataset"],
            cert["dataset"],
        )
    ):
        raise ValueError("unregistered dataset")
    if source["method"] != "ravel_v6":
        raise ValueError("ravel_v6 source is required")
    if route["method"] != "flowsub_v1":
        raise ValueError("FlowSub route result is required")
    if cert["method"] != "ravel_cert_v4":
        raise ValueError("certified result is required")
    if plan["label_opened"] is not False:
        raise ValueError("label barrier is not closed")
    expected_method = {
        "source": "ravel_v6_candidate_graph_and_comparator",
        "certifier": "global_uuid_universal_cut_iff_full_fracture",
        "allocation": "exact_lexicographic_matching",
        "primary_objective": "maximum_certified_transport_count",
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
    }
    if plan["method"] != expected_method:
        raise ValueError("registered method mismatch")
    if plan["comparators"] != [
        "official_velox_top_512",
        "flowsub_full_top_512",
        "ravel_v6_top_512",
    ]:
        raise ValueError("registered comparator mismatch")
    if plan["endpoints"] != {
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
    }:
        raise ValueError("registered endpoint mismatch")
    for name, expected in plan["code_sha256"].items():
        if digest(repository / name) != expected:
            raise ValueError(f"code digest mismatch: {name}")
    budget = int(plan["budget"])
    if budget != 512 or int(score["root_budget"]) != budget:
        raise ValueError("registered capacity mismatch")
    universe_rows = score["official_scores"]
    universe = {str(node).upper() for node, _ in universe_rows}
    if len(universe) != len(universe_rows):
        raise ValueError("score universe contains duplicates")
    roots = unique(score["seeds"], budget, "roots")
    expected_roots = {
        str(node).upper()
        for node, _ in sorted(
            universe_rows,
            key=lambda item: (-float(item[1]), str(item[0])),
        )[:budget]
    }
    if roots != expected_roots:
        raise ValueError("roots are not deterministic top-capacity scores")
    score_sha256 = digest(score_path)
    route_sha256 = digest(route_path)
    source_sha256 = digest(source_path)
    if route["input_manifest_sha256"] != score_sha256:
        raise ValueError("route input digest mismatch")
    if source["input_manifest_sha256"] != score_sha256:
        raise ValueError("source input digest mismatch")
    if source["route_manifest_sha256"] != route_sha256:
        raise ValueError("source route digest mismatch")
    if cert["input_manifest_sha256"] != score_sha256:
        raise ValueError("cert input digest mismatch")
    if cert["source_sha256"] != source_sha256:
        raise ValueError("cert source digest mismatch")
    if cert["route_manifest_sha256"] != route_sha256:
        raise ValueError("cert route digest mismatch")
    source_nodes = unique(
        source["selections"]["full"]["nodes"],
        budget,
        "source",
    )
    flow_nodes = unique(
        route["selections"]["full"]["nodes"],
        budget,
        "FlowSub",
    )
    cert_nodes = unique(
        cert["selections"]["full"]["nodes"],
        budget,
        "certified",
    )
    if (
        not source_nodes <= universe
        or not flow_nodes <= universe
        or not cert_nodes <= universe
    ):
        raise ValueError("selection leaves the score universe")
    exact = source["certificate"]
    if (
        exact["optimal"] is not True
        or int(exact["roots"]) != budget
        or int(exact["nodes"]) != budget
        or int(exact["budget"]) != budget
        or int(exact["root_degree_min"]) != 1
        or int(exact["root_degree_max"]) != 1
        or int(exact["node_degree_max"]) > 1
        or not math.isclose(float(exact["mass"]), 1.0)
        or not math.isclose(
            float(exact["objective"]),
            float(source["selections"]["full"]["ledger"]),
        )
    ):
        raise ValueError("source exact certificate failed")
    chains = tuple(
        deserialize_chain(item)
        for item in source["chains"]
    )
    calibration, calibration_sha256, calibration_files = (
        calibration_node_maxima(validation_losses)
    )
    if (
        calibration_sha256 != source["calibration_sha256"]
        or calibration_sha256 != cert["calibration_sha256"]
        or calibration_files != int(source["calibration_files"])
        or calibration_files != int(cert["calibration_files"])
        or not math.isclose(
            max(calibration),
            float(source["calibration_maximum"]),
        )
    ):
        raise ValueError("calibration lineage mismatch")
    transport = ExactTransport(
        {
            str(node): float(score)
            for node, score in universe_rows
        },
        calibration,
        set(score["seeds"]),
        chains,
    )
    original = source_selection(source)
    reproduced_source, reproduced_certificate = transport.select()
    if (
        reproduced_source.nodes != original.nodes
        or not math.isclose(
            reproduced_source.ledger,
            original.ledger,
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
        or reproduced_certificate != TransportCertificate(**exact)
    ):
        raise ValueError("source exact selection is not reproducible")
    recomputed = certify_graph(
        transport.edges,
        transport.seeds,
        transport.ledger.chains,
        {str(node) for node, _ in universe_rows},
        original,
    )
    expected_selection = {
        "nodes": list(recomputed.selection.nodes),
        "ledger": recomputed.selection.ledger,
        "candidates": recomputed.selection.candidates,
        "budget": recomputed.selection.budget,
        "mass": recomputed.selection.mass,
        "expanded": recomputed.selection.expanded,
        "values": [
            asdict(value)
            for value in recomputed.selection.values
        ],
    }
    if cert["selections"]["full"] != expected_selection:
        raise ValueError("certified selection is not reproducible")
    feasibility = cert["certificate"]
    if (
        feasibility != asdict(recomputed.certificate)
        or feasibility["optimal"] is not True
        or int(feasibility["roots"]) != budget
        or int(feasibility["nodes"]) != budget
        or int(feasibility["budget"]) != budget
        or int(feasibility["root_degree_min"]) != 1
        or int(feasibility["root_degree_max"]) != 1
        or int(feasibility["node_degree_max"]) > 1
        or not math.isclose(float(feasibility["mass"]), 1.0)
        or not math.isclose(
            float(feasibility["objective"]),
            float(cert["selections"]["full"]["ledger"]),
        )
    ):
        raise ValueError("feasibility certificate mismatch")
    expected_witnesses = json.loads(
        json.dumps(
            [
                asdict(witness)
                for witness in recomputed.witnesses
            ]
        )
    )
    if cert["witnesses"] != expected_witnesses:
        raise ValueError("cut witness mismatch")
    if any(
        int(cert[key]) != value
        for key, value in (
            ("candidate_transports", recomputed.candidate_transports),
            ("certified_candidates", recomputed.certified_candidates),
            ("source_transports", recomputed.source_transports),
            (
                "source_certified_transports",
                recomputed.source_certified_transports,
            ),
            ("certified_transports", recomputed.certified_transports),
            ("changed_from_source", recomputed.changed_from_source),
            ("source_agreement", recomputed.source_agreement),
            ("source_distance", recomputed.source_distance),
        )
    ):
        raise ValueError("transport count mismatch")
    for key, value in (
        ("selected_e_value", recomputed.selected_e_value),
        ("maximum_e_value", recomputed.maximum_e_value),
        ("secondary_objective", recomputed.secondary_objective),
    ):
        if not math.isclose(
            float(cert[key]),
            value,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ValueError("transport objective mismatch")
    if recomputed.certified_transports < 1:
        raise ValueError("certified method did not activate")
    return {
        "method": "certified_label_barrier_audit_v4",
        "frozen_sha256": digest(frozen_path),
        "score_universe": len(universe),
        "budget": budget,
        "flowsub_nodes": len(flow_nodes),
        "candidate_transports": recomputed.candidate_transports,
        "certified_candidates": recomputed.certified_candidates,
        "source_transports": recomputed.source_transports,
        "source_certified_transports": (
            recomputed.source_certified_transports
        ),
        "certified_transports": recomputed.certified_transports,
        "changed_from_source": recomputed.changed_from_source,
        "selected_e_value": recomputed.selected_e_value,
        "maximum_e_value": recomputed.maximum_e_value,
        "secondary_objective": recomputed.secondary_objective,
        "source_agreement": recomputed.source_agreement,
        "source_distance": recomputed.source_distance,
        "witnessed_routes": sum(
            len(witness.routes)
            for witness in recomputed.witnesses
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--repository", type=Path, default=Path("."))
    parser.add_argument(
        "--validation-losses",
        type=Path,
        required=True,
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(
        args.frozen,
        args.directory,
        args.repository.resolve(),
        args.validation_losses,
    )
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
