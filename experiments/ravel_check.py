from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path


def load(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            value.update(block)
    return value.hexdigest()


def check(reference: Path, candidate: Path) -> dict:
    expected = load(reference)
    observed = load(candidate)
    expected_runtime = float(expected.pop("runtime_seconds"))
    observed_runtime = float(observed.pop("runtime_seconds"))
    if expected != observed:
        raise ValueError("RAVEL outputs differ outside runtime_seconds")
    return {
        "method": "ravel_execution_equivalence_v1",
        "reference": reference.name,
        "reference_sha256": digest(reference),
        "candidate": candidate.name,
        "candidate_sha256": digest(candidate),
        "content_equal_except_runtime": True,
        "reference_runtime_seconds": expected_runtime,
        "candidate_runtime_seconds": observed_runtime,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = check(args.reference, args.candidate)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
