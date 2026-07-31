from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path


def adapter_manifest(
    connection: sqlite3.Connection,
    source: bytes,
    dump_sha256: str,
) -> dict:
    metadata = dict(
        connection.execute(
            "select key, value from metadata order by key"
        )
    )
    relation_rows = [
        {
            "raw": raw,
            "source_kind": source_kind,
            "target_kind": target_kind,
            "canonical": canonical or None,
            "count": count,
        }
        for raw, source_kind, target_kind, canonical, count
        in connection.execute(
            "select raw, source_kind, target_kind, canonical, count "
            "from relation_map "
            "order by raw, source_kind, target_kind, canonical"
        )
    ]
    day_rows = [
        {
            "day": day,
            "canonical": canonical,
            "count": count,
        }
        for day, canonical, count in connection.execute(
            "select day, relation, count(*) from events "
            "group by day, relation order by day, relation"
        )
    ]
    relation_payload = json.dumps(
        relation_rows,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "method": "optc_adapter_v1",
        "dataset": "optc_h051",
        "label_free": True,
        "dump_sha256": dump_sha256,
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "mapping_sha256": hashlib.sha256(relation_payload).hexdigest(),
        "split": {
            "train": [19, 20, 21],
            "validation": [22],
            "test": [23, 24, 25],
        },
        "metadata": metadata,
        "relations": relation_rows,
        "events_by_day": day_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--dump-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    connection = sqlite3.connect(
        f"file:{args.database}?mode=ro",
        uri=True,
    )
    payload = adapter_manifest(
        connection,
        args.source.read_bytes(),
        args.dump_sha256,
    )
    connection.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "mapping_sha256": payload["mapping_sha256"],
                "events": payload["metadata"]["events"],
                "unmapped_events": payload["metadata"]["unmapped_events"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
