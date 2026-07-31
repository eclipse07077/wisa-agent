from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time
from dataclasses import asdict, replace
from pathlib import Path

from wisa_agent.tc.ravel import TransportEdge
from wisa_agent.tc.transport import (
    ExactTransport,
    certify_transport,
    exact_transport,
)


def ablation_edges(
    edges: tuple[TransportEdge, ...],
    method: str,
) -> tuple[TransportEdge, ...]:
    if method not in {"topology", "rank"}:
        raise ValueError("unknown transport ablation")
    values = []
    for edge in edges:
        if edge.kind == "local":
            utility = 0.0
        elif method == "topology":
            utility = 1.0
        else:
            utility = max(
                1.0 - 0.25 / (edge.e_value * edge.e_value),
                0.0,
            )
        values.append(replace(edge, utility=utility))
    return tuple(values)


def selection_payload(
    edges: tuple[TransportEdge, ...],
    roots: set[str],
) -> dict:
    selected = exact_transport(edges, roots)
    certificate = certify_transport(selected, roots, optimal=True)
    if (
        certificate.root_degree_min != 1
        or certificate.root_degree_max != 1
        or certificate.node_degree_max > 1
        or certificate.budget != len(roots)
    ):
        raise RuntimeError("ablation transport certificate failed")
    return {
        "nodes": [edge.node for edge in selected],
        "expanded": sum(edge.kind == "proof" for edge in selected),
        "certificate": asdict(certificate),
        "values": [asdict(edge) for edge in selected],
    }


def main() -> None:
    from bear import SPLITS, calibration_node_maxima, deserialize_chain

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
    parser.add_argument("--output", type=Path, required=True)
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
    if route_payload["input_manifest_sha256"] != input_sha256:
        raise ValueError("route input manifest mismatch")
    calibration, calibration_sha256, calibration_files = (
        calibration_node_maxima(args.validation_losses)
    )
    if max(calibration) != float(manifest["thresholds"]["velox"]):
        raise ValueError("validation maximum does not match manifest")
    official_scores = {
        str(node): float(score)
        for node, score in manifest["official_scores"]
    }
    roots = set(manifest["seeds"])
    chains = tuple(
        deserialize_chain(item)
        for item in route_payload["chains"]
    )
    transport = ExactTransport(
        official_scores,
        calibration,
        roots,
        chains,
    )
    selections = {
        method: selection_payload(
            ablation_edges(transport.edges, method),
            roots,
        )
        for method in ("topology", "rank")
    }
    dataset = SPLITS[args.dataset]
    payload = {
        "method": "ravel_transport_ablation_v1",
        "dataset": args.dataset,
        "input_manifest_sha256": input_sha256,
        "route_manifest_sha256": hashlib.sha256(
            route_bytes
        ).hexdigest(),
        "official_score_sha256": manifest["official_score_sha256"],
        "calibration_sha256": calibration_sha256,
        "calibration_files": calibration_files,
        "budget": len(roots),
        "split": {
            "train": dataset.train,
            "validation": dataset.validation,
            "test": dataset.test,
        },
        "candidate_edges": len(transport.edges),
        "chain_count": len(transport.ledger.chains),
        "account_count": len(transport.ledger.accounts),
        "selections": selections,
        "runtime_seconds": time.perf_counter() - started,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.output, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    print(
        json.dumps(
            {
                "dataset": args.dataset,
                "budget": len(roots),
                "topology": selections["topology"]["expanded"],
                "rank": selections["rank"]["expanded"],
                "runtime_seconds": payload["runtime_seconds"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
