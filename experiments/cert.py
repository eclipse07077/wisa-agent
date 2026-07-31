from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from dataclasses import asdict
from pathlib import Path

from bear import calibration_node_maxima, deserialize_chain
from wisa_agent.tc.cert import certify_graph
from wisa_agent.tc.ravel import (
    TransportEdge,
    TransportSelection,
)
from wisa_agent.tc.transport import ExactTransport
from wisa_agent.tc.transport import certify_transport


def load(path: Path) -> tuple[dict, str]:
    content = path.read_bytes()
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle), hashlib.sha256(content).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument(
        "--validation-losses",
        type=Path,
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest, manifest_sha256 = load(args.manifest)
    source, source_sha256 = load(args.source)
    if source["method"] != "ravel_v6":
        raise ValueError("ravel_v6 source is required")
    if source["input_manifest_sha256"] != manifest_sha256:
        raise ValueError("source input manifest mismatch")
    values = tuple(
        TransportEdge(**value)
        for value in source["selections"]["full"]["values"]
    )
    source_selection = TransportSelection(
        mode="full",
        nodes=tuple(
            source["selections"]["full"]["nodes"]
        ),
        ledger=float(
            source["selections"]["full"]["ledger"]
        ),
        candidates=int(
            source["selections"]["full"]["candidates"]
        ),
        budget=int(source["selections"]["full"]["budget"]),
        values=values,
        mass=float(source["selections"]["full"]["mass"]),
        expanded=int(
            source["selections"]["full"]["expanded"]
        ),
    )
    chains = tuple(
        deserialize_chain(item)
        for item in source["chains"]
    )
    scored = {
        str(node)
        for node, _ in manifest["official_scores"]
    }
    official_scores = {
        str(node): float(score)
        for node, score in manifest["official_scores"]
    }
    calibration, calibration_sha256, calibration_files = (
        calibration_node_maxima(args.validation_losses)
    )
    if (
        calibration_sha256 != source["calibration_sha256"]
        or calibration_files != int(source["calibration_files"])
        or not math.isclose(
            max(calibration),
            float(source["calibration_maximum"]),
        )
    ):
        raise ValueError("source calibration mismatch")
    transport = ExactTransport(
        official_scores,
        calibration,
        set(manifest["seeds"]),
        chains,
    )
    source_certificate = certify_transport(
        source_selection.values,
        transport.seeds,
        optimal=True,
    )
    if (
        tuple(edge.node for edge in source_selection.values)
        != source_selection.nodes
        or asdict(source_certificate) != source["certificate"]
    ):
        raise ValueError("source exact certificate is inconsistent")
    result = certify_graph(
        transport.edges,
        transport.seeds,
        transport.ledger.chains,
        scored,
        source_selection,
    )
    payload = {
        "method": "ravel_cert_v4",
        "dataset": source["dataset"],
        "input_manifest_sha256": manifest_sha256,
        "source_sha256": source_sha256,
        "source_method": source["method"],
        "route_manifest_sha256": source[
            "route_manifest_sha256"
        ],
        "calibration_sha256": calibration_sha256,
        "calibration_files": calibration_files,
        "rule": "lexicographic_certificate_projection",
        "budget": result.selection.budget,
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
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.output, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    print(
        json.dumps(
            {
                "dataset": payload["dataset"],
                "budget": payload["budget"],
                "candidate_transports": result.candidate_transports,
                "certified_candidates": result.certified_candidates,
                "source_transports": result.source_transports,
                "certified_transports": result.certified_transports,
                "changed_from_source": result.changed_from_source,
            }
        )
    )


if __name__ == "__main__":
    main()
