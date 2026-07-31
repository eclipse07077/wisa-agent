from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import re
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            value.update(block)
    return value.hexdigest()


def load(path: Path) -> dict:
    if path.name.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(path.read_text(encoding="utf-8"))


def check_frozen(path: Path, directory: Path) -> dict[str, Path]:
    payload = load(path)
    if payload.get("schema") != 1:
        raise ValueError("unknown frozen schema")
    rows = payload.get("files", ())
    names = [str(row["name"]) for row in rows]
    if len(names) != len(set(names)):
        raise ValueError("frozen names are duplicated")
    files = {}
    for row in rows:
        current = directory / str(row["name"])
        if not current.is_file():
            raise FileNotFoundError(current)
        if current.stat().st_size != int(row["bytes"]):
            raise ValueError(f"frozen size mismatch: {current.name}")
        if digest(current) != str(row["sha256"]):
            raise ValueError(f"frozen digest mismatch: {current.name}")
        files[current.name] = current
    return files


def unique_nodes(values: list[str], budget: int, name: str) -> set[str]:
    nodes = {str(value).upper() for value in values}
    if len(values) != budget or len(nodes) != budget:
        raise ValueError(f"{name} is not a unique exact-budget selection")
    return nodes


def check_bundle(
    files: dict[str, Path],
    stem: str,
    suffix: str,
) -> dict:
    names = {
        "score": f"score-{stem}{suffix}.json.gz",
        "route": f"route-{stem}{suffix}.json.gz",
        "v5": f"v5-{stem}{suffix}.json.gz",
        "v6": f"v6-{stem}{suffix}.json.gz",
        "ablation": f"ablation-{stem}{suffix}.json.gz",
    }
    missing = set(names.values()) - set(files)
    if missing:
        raise ValueError(f"bundle is incomplete: {sorted(missing)}")
    paths = {key: files[value] for key, value in names.items()}
    payloads = {key: load(value) for key, value in paths.items()}
    score = payloads["score"]
    route = payloads["route"]
    v5 = payloads["v5"]
    v6 = payloads["v6"]
    ablation = payloads["ablation"]
    dataset = score["dataset"]
    if any(value["dataset"] != dataset for value in payloads.values()):
        raise ValueError("bundle dataset mismatch")
    if score["method"] not in {
        "official_velox_seeded_chain_v1",
        "matched_tgn_seeded_chain_v1",
    }:
        raise ValueError("unknown score method")
    budget = int(score["root_budget"])
    if budget != 512:
        raise ValueError("registered corrected OpTC budget mismatch")
    universe_rows = score["official_scores"]
    universe = {str(node).upper() for node, _ in universe_rows}
    if len(universe) != len(universe_rows):
        raise ValueError("score universe contains duplicate nodes")
    seeds = unique_nodes(score["seeds"], budget, "score roots")
    if not seeds <= universe:
        raise ValueError("score roots leave the universe")
    score_hash = digest(paths["score"])
    route_hash = digest(paths["route"])
    if route["input_manifest_sha256"] != score_hash:
        raise ValueError("route input digest mismatch")
    for chain in route["chains"]:
        for predicate in chain["predicates"]:
            endpoints = [str(node).upper() for node in predicate["endpoints"]]
            if not endpoints or len(endpoints) != len(set(endpoints)):
                raise ValueError("route predicate endpoints are not a set")
    for key, method in (
        ("v5", "ravel_v5"),
        ("v6", "ravel_v6"),
        ("ablation", "ravel_transport_ablation_v1"),
    ):
        current = payloads[key]
        if current["method"] != method:
            raise ValueError(f"{key} method mismatch")
        if current["input_manifest_sha256"] != score_hash:
            raise ValueError(f"{key} input digest mismatch")
        if current["route_manifest_sha256"] != route_hash:
            raise ValueError(f"{key} route digest mismatch")
        if int(current["budget"]) != budget:
            raise ValueError(f"{key} budget mismatch")
    v5_nodes = unique_nodes(
        v5["selections"]["full"]["nodes"],
        budget,
        "v5",
    )
    v6_nodes = unique_nodes(
        v6["selections"]["full"]["nodes"],
        budget,
        "v6",
    )
    if not v5_nodes <= universe or not v6_nodes <= universe:
        raise ValueError("RAVEL selection leaves the score universe")
    certificate = v6["certificate"]
    expected = {
        "roots": budget,
        "nodes": budget,
        "budget": budget,
        "root_degree_min": 1,
        "root_degree_max": 1,
        "node_degree_max": 1,
    }
    if any(int(certificate[key]) != value for key, value in expected.items()):
        raise ValueError("exact transport certificate is invalid")
    if (
        certificate["optimal"] is not True
        or not math.isclose(float(certificate["mass"]), 1.0)
        or not math.isclose(
            float(certificate["objective"]),
            float(v6["selections"]["full"]["ledger"]),
        )
    ):
        raise ValueError("exact transport objective certificate mismatch")
    ablation_nodes = {}
    for method in ("topology", "rank"):
        nodes = unique_nodes(
            ablation["selections"][method]["nodes"],
            budget,
            f"ablation {method}",
        )
        if not nodes <= universe:
            raise ValueError("ablation selection leaves the score universe")
        ablation_nodes[method] = len(nodes)
    return {
        "dataset": dataset,
        "detector": score["detector"],
        "score_universe": len(universe),
        "budget": budget,
        "chains": len(route["chains"]),
        "v5_nodes": len(v5_nodes),
        "v6_nodes": len(v6_nodes),
        "proof_transports": int(v6["selections"]["full"]["expanded"]),
        "objective": float(certificate["objective"]),
        "ablations": ablation_nodes,
    }


def audit(path: Path, directory: Path) -> dict:
    files = check_frozen(path, directory)
    bundles = []
    pattern = re.compile(r"^score-(\d+)(-tgn)?\.json\.gz$")
    for name in sorted(files):
        match = pattern.match(name)
        if match is None:
            continue
        bundles.append(
            check_bundle(
                files,
                match.group(1),
                match.group(2) or "",
            )
        )
    if not bundles:
        raise ValueError("frozen manifest contains no score bundle")
    return {
        "method": "frozen_label_barrier_audit_v1",
        "frozen_sha256": digest(path),
        "files": len(files),
        "bundles": bundles,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.frozen, args.directory)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
