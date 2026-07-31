from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            value.update(block)
    return value.hexdigest()


def freeze(paths: list[Path]) -> dict:
    resolved = sorted(
        (path.resolve() for path in paths),
        key=lambda path: path.name,
    )
    if len({path.name for path in resolved}) != len(resolved):
        raise ValueError("frozen filenames must be unique")
    for path in resolved:
        if not path.is_file():
            raise FileNotFoundError(path)
    return {
        "schema": 1,
        "files": [
            {
                "name": path.name,
                "bytes": path.stat().st_size,
                "sha256": digest(path),
            }
            for path in resolved
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("paths", type=Path, nargs="+")
    args = parser.parse_args()
    payload = freeze(args.paths)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
