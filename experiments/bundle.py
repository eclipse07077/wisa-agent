from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path

from bear import SPLITS, calibration_node_maxima, deserialize_chain
from flow import serialize_chain
from transport_ablation import (
    ablation_edges,
    selection_payload,
)
from wisa_agent.tc.ravel import (
    RavelTransport,
    TransportSelection,
)
from wisa_agent.tc.transport import (
    certify_transport,
    exact_transport,
)


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)


def selection_dict(selection: TransportSelection) -> dict:
    return {
        "nodes": selection.nodes,
        "ledger": selection.ledger,
        "candidates": selection.candidates,
        "budget": selection.budget,
        "mass": selection.mass,
        "expanded": selection.expanded,
        "values": [asdict(value) for value in selection.values],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--routes", type=Path, required=True)
    parser.add_argument(
        "--validation-losses",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--dataset",
        choices=tuple(SPLITS),
        required=True,
    )
    parser.add_argument("--v5", type=Path, required=True)
    parser.add_argument("--v6", type=Path, required=True)
    parser.add_argument("--ablation", type=Path, required=True)
    args = parser.parse_args()

    started = time.perf_counter()
    manifest_bytes = args.manifest.read_bytes()
    with gzip.open(args.manifest, "rt", encoding="utf-8") as handle:
        manifest = json.load(handle)
    route_bytes = args.routes.read_bytes()
    with gzip.open(args.routes, "rt", encoding="utf-8") as handle:
        route_payload = json.load(handle)
    if route_payload["dataset"] != args.dataset:
        raise ValueError("route dataset mismatch")
    input_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    route_sha256 = hashlib.sha256(route_bytes).hexdigest()
    if route_payload["input_manifest_sha256"] != input_sha256:
        raise ValueError("route input manifest mismatch")
    official_scores = {
        str(node): float(score)
        for node, score in manifest["official_scores"]
    }
    roots = set(manifest["seeds"])
    calibration, calibration_sha256, calibration_files = (
        calibration_node_maxima(args.validation_losses)
    )
    if max(calibration) != float(manifest["thresholds"]["velox"]):
        raise ValueError("validation maximum does not match manifest")
    chains = tuple(
        deserialize_chain(item)
        for item in route_payload["chains"]
    )
    transport = RavelTransport(
        official_scores,
        calibration,
        roots,
        chains,
        conditional_hold=True,
    )
    v5_selection = transport.select()
    exact_values = exact_transport(transport.edges, roots)
    v6_selection = TransportSelection(
        mode="full",
        nodes=tuple(edge.node for edge in exact_values),
        ledger=sum(edge.utility for edge in exact_values),
        candidates=len(transport.candidates),
        budget=len(roots),
        values=exact_values,
        mass=1.0 if roots else 0.0,
        expanded=sum(edge.kind == "proof" for edge in exact_values),
    )
    certificate = certify_transport(
        exact_values,
        roots,
        optimal=True,
    )
    if (
        certificate.root_degree_min != 1
        or certificate.root_degree_max != 1
        or certificate.node_degree_max > 1
        or certificate.budget != len(roots)
    ):
        raise RuntimeError("exact transport certificate failed")
    ablations = {
        method: selection_payload(
            ablation_edges(transport.edges, method),
            roots,
        )
        for method in ("topology", "rank")
    }
    dataset = SPLITS[args.dataset]
    split = {
        "train": dataset.train,
        "validation": dataset.validation,
        "test": dataset.test,
    }
    runtime = time.perf_counter() - started
    common = {
        "dataset": args.dataset,
        "input_manifest_sha256": input_sha256,
        "route_manifest_sha256": route_sha256,
        "official_score_sha256": manifest["official_score_sha256"],
        "calibration_sha256": calibration_sha256,
        "calibration_files": calibration_files,
        "split": split,
    }
    serialized_chains = [
        serialize_chain(chain)
        for chain in transport.ledger.chains
    ]
    v5 = {
        "method": "ravel_v5",
        **common,
        "calibration_nodes": len(calibration),
        "calibration_maximum": max(calibration),
        "kappa": 0.5,
        "conditioned": True,
        "conserved": False,
        "transport": True,
        "conditional_transport": True,
        "profile_threshold": route_payload["profile_threshold"],
        "budget": len(roots),
        "chain_count": len(transport.ledger.chains),
        "account_count": len(transport.ledger.accounts),
        "chains": serialized_chains,
        "ledgers": transport.ledger.ledgers,
        "selections": {"full": selection_dict(v5_selection)},
        "runtime_seconds": runtime,
    }
    v6 = {
        "method": "ravel_v6",
        **common,
        "calibration_nodes": len(calibration),
        "calibration_maximum": max(calibration),
        "kappa": 0.5,
        "conditioned": True,
        "transport": True,
        "conditional_transport": True,
        "exact_transport": True,
        "profile_threshold": route_payload["profile_threshold"],
        "budget": len(roots),
        "chain_count": len(transport.ledger.chains),
        "account_count": len(transport.ledger.accounts),
        "chains": serialized_chains,
        "certificate": asdict(certificate),
        "selections": {"full": selection_dict(v6_selection)},
        "runtime_seconds": runtime,
    }
    ablation = {
        "method": "ravel_transport_ablation_v1",
        **common,
        "budget": len(roots),
        "candidate_edges": len(transport.edges),
        "chain_count": len(transport.ledger.chains),
        "account_count": len(transport.ledger.accounts),
        "selections": ablations,
        "runtime_seconds": runtime,
    }
    write(args.v5, v5)
    write(args.v6, v6)
    write(args.ablation, ablation)
    print(
        json.dumps(
            {
                "dataset": args.dataset,
                "budget": len(roots),
                "v5": v5_selection.ledger,
                "v6": v6_selection.ledger,
                "topology": ablations["topology"]["expanded"],
                "rank": ablations["rank"]["expanded"],
                "runtime_seconds": runtime,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
