from __future__ import annotations

import argparse
import bisect
import json
import sqlite3
import subprocess
from collections import Counter
from pathlib import Path
from typing import Iterable, Iterator

from wisa_agent.tc.cdm import day_boundaries
from wisa_agent.tc.relations import (
    OPTC_RELATIONS,
    TRACKED_RELATIONS,
    normalize_relation,
)


ESCAPES = {
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "v": "\v",
    "\\": "\\",
}


def copy_value(value: str) -> str | None:
    if value == r"\N":
        return None
    output = []
    index = 0
    while index < len(value):
        if value[index] != "\\" or index + 1 == len(value):
            output.append(value[index])
            index += 1
            continue
        index += 1
        marker = value[index]
        if marker in ESCAPES:
            output.append(ESCAPES[marker])
            index += 1
            continue
        if marker in "01234567":
            end = index + 1
            while end < min(index + 3, len(value)) and value[end] in "01234567":
                end += 1
            output.append(chr(int(value[index:end], 8)))
            index = end
            continue
        output.append(marker)
        index += 1
    return "".join(output)


def copy_rows(
    lines: Iterable[str],
    decode: bool = True,
) -> Iterator[list[str | None]]:
    active = False
    for raw in lines:
        line = raw.rstrip("\n")
        if not active:
            active = line.startswith("COPY ")
            continue
        if line == r"\.":
            return
        values = line.split("\t")
        yield (
            [copy_value(value) for value in values]
            if decode
            else values
        )


def restore_rows(
    pg_restore: Path,
    dump: Path,
    table: str,
    decode: bool = True,
) -> Iterator[list[str | None]]:
    process = subprocess.Popen(
        [
            str(pg_restore),
            "--data-only",
            f"--table={table}",
            "--file=-",
            str(dump),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if process.stdout is None or process.stderr is None:
        raise RuntimeError("pg_restore streams are unavailable")
    yield from copy_rows(process.stdout, decode)
    error = process.stderr.read()
    return_code = process.wait()
    if return_code:
        raise RuntimeError(error.strip() or f"pg_restore exited {return_code}")


def build_index(
    dump: Path,
    output: Path,
    pg_restore: Path,
    year: int = 2019,
    month: int = 5,
    start_day: int = 8,
    end_day: int = 18,
) -> dict[str, int]:
    partial = output.with_suffix(output.suffix + ".partial")
    if output.exists():
        with sqlite3.connect(output) as connection:
            row = connection.execute(
                "select value from metadata where key = 'complete'"
            ).fetchone()
            if row and row[0] == "1":
                values = connection.execute(
                    "select key, value from metadata where key != 'complete'"
                ).fetchall()
                return {key: int(value) for key, value in values}
    output.parent.mkdir(parents=True, exist_ok=True)
    if partial.exists():
        partial.unlink()
    connection = sqlite3.connect(partial)
    connection.execute("pragma journal_mode=off")
    connection.execute("pragma synchronous=off")
    connection.execute("pragma temp_store=memory")
    connection.execute(
        "create table nodes(uuid text primary key, kind text, name text)"
    )
    connection.execute(
        "create table node_index(index_id text primary key, uuid text)"
    )
    connection.execute(
        "create table events(timestamp integer, day integer, "
        "source text, target text, relation text, path text)"
    )
    connection.execute(
        "create table metadata(key text primary key, value text)"
    )
    connection.execute(
        "create table relation_map("
        "raw text, source_kind text, target_kind text, "
        "canonical text, count integer, "
        "primary key(raw, source_kind, target_kind, canonical))"
    )
    node_count = 0
    node_batch: list[tuple[str, str, str]] = []
    index_batch: list[tuple[str, str]] = []
    specifications = (
        ("file_node_table", "file", 3, (2,)),
        ("netflow_node_table", "netflow", 6, (4, 5)),
        ("subject_node_table", "subject", 4, (3, 2)),
    )
    for table, kind, index_column, name_columns in specifications:
        for row in restore_rows(pg_restore, dump, table):
            if len(row) <= index_column or row[0] is None or row[index_column] is None:
                continue
            node_uuid = row[0].upper()
            name = ":".join(
                str(row[column])
                for column in name_columns
                if column < len(row) and row[column]
            )
            node_batch.append((node_uuid, kind, name))
            index_batch.append((str(row[index_column]), node_uuid))
            node_count += 1
            if len(node_batch) >= 50000:
                connection.executemany(
                    "insert into nodes values(?, ?, ?) "
                    "on conflict(uuid) do update set "
                    "kind=excluded.kind, name=excluded.name",
                    node_batch,
                )
                connection.executemany(
                    "insert into node_index values(?, ?) "
                    "on conflict(index_id) do update set uuid=excluded.uuid",
                    index_batch,
                )
                node_batch.clear()
                index_batch.clear()
        connection.commit()
    if node_batch:
        connection.executemany(
            "insert into nodes values(?, ?, ?) "
            "on conflict(uuid) do update set "
            "kind=excluded.kind, name=excluded.name",
            node_batch,
        )
        connection.executemany(
            "insert into node_index values(?, ?) "
            "on conflict(index_id) do update set uuid=excluded.uuid",
            index_batch,
        )
        connection.commit()
    index_to_uuid = dict(
        connection.execute("select index_id, uuid from node_index")
    )
    uuid_to_kind = dict(connection.execute("select uuid, kind from nodes"))
    boundaries = day_boundaries(year, month, start_day, end_day)
    day_offset = start_day - 1
    event_rows = 0
    tracked_events = 0
    missing_nodes = 0
    unmapped_events = 0
    relation_counts: Counter[tuple[str, str, str, str]] = Counter()
    event_batch: list[tuple[int, int, str, str, str, str]] = []
    for row in restore_rows(pg_restore, dump, "event_table", decode=False):
        event_rows += 1
        if len(row) < 7:
            continue
        raw_relation = str(row[2])
        if (
            raw_relation not in TRACKED_RELATIONS
            and raw_relation not in OPTC_RELATIONS
        ):
            continue
        source = index_to_uuid.get(str(row[1]))
        target = index_to_uuid.get(str(row[4]))
        if source is None or target is None or row[6] is None:
            missing_nodes += 1
            continue
        source_kind = uuid_to_kind[source]
        target_kind = uuid_to_kind[target]
        relation = normalize_relation(
            raw_relation,
            source_kind,
            target_kind,
        )
        relation_counts[
            (
                raw_relation,
                source_kind,
                target_kind,
                relation or "",
            )
        ] += 1
        if relation is None:
            unmapped_events += 1
            continue
        timestamp = int(row[6])
        day = day_offset + bisect.bisect_right(boundaries, timestamp)
        event_batch.append((timestamp, day, source, target, relation, ""))
        tracked_events += 1
        if len(event_batch) >= 50000:
            connection.executemany(
                "insert into events values(?, ?, ?, ?, ?, ?)",
                event_batch,
            )
            event_batch.clear()
    if event_batch:
        connection.executemany(
            "insert into events values(?, ?, ?, ?, ?, ?)",
            event_batch,
        )
    connection.executemany(
        "insert into relation_map values(?, ?, ?, ?, ?)",
        [
            (*key, count)
            for key, count in sorted(relation_counts.items())
        ],
    )
    connection.execute("create index events_day_time on events(day, timestamp)")
    unique_nodes = int(
        connection.execute("select count(*) from nodes").fetchone()[0]
    )
    counts = {
        "node_records": node_count,
        "nodes": unique_nodes,
        "event_records": event_rows,
        "events": tracked_events,
        "missing_node_events": missing_nodes,
        "unmapped_events": unmapped_events,
    }
    connection.executemany(
        "insert into metadata values(?, ?)",
        [(key, str(value)) for key, value in counts.items()]
        + [("complete", "1")],
    )
    connection.commit()
    connection.close()
    partial.replace(output)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pg-restore", type=Path, required=True)
    parser.add_argument("--year", type=int, default=2019)
    parser.add_argument("--month", type=int, default=5)
    parser.add_argument("--start-day", type=int, default=8)
    parser.add_argument("--end-day", type=int, default=18)
    args = parser.parse_args()
    result = build_index(
        args.dump,
        args.output,
        args.pg_restore,
        args.year,
        args.month,
        args.start_day,
        args.end_day,
    )
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
