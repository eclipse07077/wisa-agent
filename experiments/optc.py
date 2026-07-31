from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import time
from collections import Counter
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator

from wisa_agent.tc.relations import OPTC_RELATIONS, normalize_relation


KINDS = {
    "FILE": "file",
    "FLOW": "netflow",
    "PROCESS": "subject",
}
STAMP = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"
    r"(?:\.(\d{1,9}))?(Z|[+-]\d{2}:\d{2})$"
)


@dataclass(frozen=True)
class Node:
    uuid: str
    kind: str
    index: int
    path: str = ""
    command: str = ""
    source_address: str = ""
    source_port: str = ""
    destination_address: str = ""
    destination_port: str = ""


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    source_kind: str
    target_kind: str
    relation: str
    canonical: str | None
    event_uuid: str
    timestamp: int


def timestamp_nanos(value: str) -> int:
    match = STAMP.fullmatch(value)
    if match is None:
        raise ValueError(f"invalid timestamp: {value}")
    base, fraction, zone = match.groups()
    suffix = "+00:00" if zone == "Z" else zone
    seconds = int(datetime.fromisoformat(base + suffix).timestamp())
    nanos = int((fraction or "").ljust(9, "0") or "0")
    return seconds * 1_000_000_000 + nanos


def text_value(value) -> str:
    return str(value or "").replace("\x00", "")


def node_from_event(
    payload: dict,
    uuid: str,
    kind: str,
    index: int,
    actor: bool,
) -> Node:
    properties = payload.get("properties") or {}
    if kind == "subject":
        path = text_value(properties.get("image_path"))
        command = text_value(properties.get("command_line") or path)
        return Node(uuid, kind, index, path, command)
    if kind == "file":
        return Node(
            uuid,
            kind,
            index,
            text_value(properties.get("file_path")),
        )
    return Node(
        uuid,
        kind,
        index,
        source_address=text_value(properties.get("src_ip")),
        source_port=text_value(properties.get("src_port")),
        destination_address=text_value(properties.get("dest_ip")),
        destination_port=text_value(properties.get("dest_port")),
    )


def merge_node(current: Node, incoming: Node) -> Node:
    if current.kind != incoming.kind or current.index != incoming.index:
        raise ValueError("node identity conflict")
    values = {
        field: getattr(current, field) or getattr(incoming, field)
        for field in (
            "path",
            "command",
            "source_address",
            "source_port",
            "destination_address",
            "destination_port",
        )
    }
    return replace(current, **values)


def project_event(
    payload: dict,
    actor_index: int,
    object_index: int,
) -> tuple[Node, Node, Edge] | None:
    action = str(payload.get("action") or "")
    object_type = str(payload.get("object") or "")
    if action not in OPTC_RELATIONS or object_type not in KINDS:
        return None
    actor_uuid = str(payload.get("actorID") or "").upper()
    object_uuid = str(payload.get("objectID") or "").upper()
    event_uuid = str(payload.get("id") or "").upper()
    if not actor_uuid or not object_uuid or not event_uuid:
        return None
    actor_node = node_from_event(
        payload,
        actor_uuid,
        "subject",
        actor_index,
        True,
    )
    object_node = node_from_event(
        payload,
        object_uuid,
        KINDS[object_type],
        object_index,
        False,
    )
    reverse = action == "READ"
    if object_type == "FLOW":
        direction = str(
            (payload.get("properties") or {}).get("direction") or ""
        ).lower()
        reverse = direction == "inbound"
    source, target = (
        (object_node, actor_node)
        if reverse
        else (actor_node, object_node)
    )
    edge = Edge(
        source.uuid,
        target.uuid,
        source.kind,
        target.kind,
        action,
        normalize_relation(action, source.kind, target.kind),
        event_uuid,
        timestamp_nanos(str(payload["timestamp"])),
    )
    return actor_node, object_node, edge


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            value.update(block)
    return value.hexdigest()


def table_setup(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "create table if not exists event_table("
            "src_node varchar, src_index_id varchar, operation varchar, "
            "dst_node varchar, dst_index_id varchar, event_uuid varchar not null, "
            "timestamp_rec bigint, _id bigserial primary key)"
        )
        cursor.execute(
            "create table if not exists file_node_table("
            "node_uuid varchar not null, hash_id varchar not null, path varchar, "
            "index_id bigint, primary key(node_uuid, hash_id))"
        )
        cursor.execute(
            "create table if not exists netflow_node_table("
            "node_uuid varchar not null, hash_id varchar not null, "
            "src_addr varchar, src_port varchar, dst_addr varchar, "
            "dst_port varchar, index_id bigint, "
            "primary key(node_uuid, hash_id))"
        )
        cursor.execute(
            "create table if not exists subject_node_table("
            "node_uuid varchar, hash_id varchar, path varchar, cmd varchar, "
            "index_id bigint, primary key(node_uuid, hash_id))"
        )
        cursor.execute(
            "create table if not exists optc_projection("
            "key varchar primary key, value text not null)"
        )
        cursor.execute(
            "create table if not exists optc_source("
            "filename varchar primary key, sha256 varchar not null, "
            "day integer not null, events bigint not null, stats jsonb not null)"
        )
    connection.commit()


def load_nodes(connection) -> dict[str, Node]:
    specifications = (
        (
            "subject_node_table",
            "subject",
            "node_uuid, index_id, path, cmd",
        ),
        (
            "file_node_table",
            "file",
            "node_uuid, index_id, path, ''",
        ),
        (
            "netflow_node_table",
            "netflow",
            "node_uuid, index_id, '', '', "
            "src_addr, src_port, dst_addr, dst_port",
        ),
    )
    nodes = {}
    with connection.cursor() as cursor:
        for table, kind, columns in specifications:
            cursor.execute(f"select {columns} from {table}")
            for row in cursor:
                values = list(row) + [""] * (8 - len(row))
                nodes[str(values[0]).upper()] = Node(
                    str(values[0]).upper(),
                    kind,
                    int(values[1]),
                    *(str(value or "") for value in values[2:8]),
                )
    return nodes


def hash_id(uuid: str) -> str:
    return hashlib.sha256(uuid.lower().encode("utf-8")).hexdigest()


def node_rows(nodes: Iterable[Node]) -> dict[str, list[tuple]]:
    rows = {"subject": [], "file": [], "netflow": []}
    for node in nodes:
        uuid = node.uuid.lower()
        hashed = hash_id(node.uuid)
        if node.kind == "subject":
            rows[node.kind].append(
                (uuid, hashed, node.path, node.command, node.index)
            )
        elif node.kind == "file":
            rows[node.kind].append(
                (uuid, hashed, node.path, node.index)
            )
        else:
            rows[node.kind].append(
                (
                    uuid,
                    hashed,
                    node.source_address,
                    node.source_port,
                    node.destination_address,
                    node.destination_port,
                    node.index,
                )
            )
    return rows


def flush(
    connection,
    nodes: Iterable[Node],
    edges: list[tuple],
) -> None:
    from psycopg2.extras import execute_values

    rows = node_rows(nodes)
    with connection.cursor() as cursor:
        if rows["subject"]:
            execute_values(
                cursor,
                "insert into subject_node_table values %s "
                "on conflict(node_uuid, hash_id) do update set "
                "path=coalesce(nullif(subject_node_table.path, ''), excluded.path), "
                "cmd=coalesce(nullif(subject_node_table.cmd, ''), excluded.cmd)",
                rows["subject"],
                page_size=10000,
            )
        if rows["file"]:
            execute_values(
                cursor,
                "insert into file_node_table values %s "
                "on conflict(node_uuid, hash_id) do update set "
                "path=coalesce(nullif(file_node_table.path, ''), excluded.path)",
                rows["file"],
                page_size=10000,
            )
        if rows["netflow"]:
            execute_values(
                cursor,
                "insert into netflow_node_table values %s "
                "on conflict(node_uuid, hash_id) do nothing",
                rows["netflow"],
                page_size=10000,
            )
        if edges:
            buffer = io.StringIO()
            writer = csv.writer(buffer, lineterminator="\n")
            writer.writerows(edges)
            buffer.seek(0)
            cursor.copy_expert(
                "copy event_table("
                "src_node, src_index_id, operation, dst_node, dst_index_id, "
                "event_uuid, timestamp_rec) from stdin with(format csv)",
                buffer,
            )
    connection.commit()


def source_files(
    index: Path,
    directory: Path,
    host: str,
    wait: bool = False,
) -> Iterator[dict]:
    payload = json.loads(index.read_text(encoding="utf-8"))
    downloads = {
        Path(item["path"]).name: item
        for item in payload.get("downloads", ())
    }
    count = 0
    for member in payload["members"]:
        if f"sysclient{host}.json.gz" not in member["name"]:
            continue
        filename = f"{member['day']}-{host}.json.gz"
        path = directory / filename
        while wait and (
            not path.is_file()
            or path.stat().st_size != int(member["size"])
        ):
            time.sleep(10)
        if not path.is_file() or path.stat().st_size != int(member["size"]):
            raise FileNotFoundError(path)
        item = downloads.get(filename)
        sha256 = (
            str(item["sha256"])
            if item is not None
            else digest(path)
        )
        count += 1
        yield {
            "day": int(member["day"]),
            "path": path,
            "sha256": sha256,
            "size": int(member["size"]),
        }
    if count != 7:
        raise ValueError("expected seven host files")


def day_bounds(day: int) -> tuple[int, int]:
    start = timestamp_nanos(f"2019-09-{day:02d}T00:00:00-04:00")
    stop = timestamp_nanos(f"2019-09-{day + 1:02d}T00:00:00-04:00")
    return start, stop


def ingest_file(
    connection,
    source: dict,
    nodes: dict[str, Node],
    batch_size: int,
) -> dict:
    path = source["path"]
    day = int(source["day"])
    with connection.cursor() as cursor:
        cursor.execute(
            "select sha256 from optc_source where filename=%s",
            (path.name,),
        )
        row = cursor.fetchone()
        if row is not None:
            if row[0] != source["sha256"]:
                raise ValueError("completed source hash changed")
            return {"skipped": True}
        start, stop = day_bounds(day)
        cursor.execute(
            "delete from event_table "
            "where timestamp_rec >= %s and timestamp_rec < %s",
            (start, stop),
        )
    connection.commit()
    counts = Counter()
    relations = Counter()
    dirty: dict[str, Node] = {}
    edges = []
    next_index = max((node.index for node in nodes.values()), default=-1) + 1
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            counts["records"] += 1
            try:
                payload = json.loads(line)
                object_type = str(payload.get("object") or "")
                action = str(payload.get("action") or "")
                if object_type not in KINDS:
                    counts[f"dropped_object:{object_type or '<empty>'}"] += 1
                    continue
                if action not in OPTC_RELATIONS:
                    counts[f"dropped_action:{action or '<empty>'}"] += 1
                    continue
                actor_uuid = str(payload.get("actorID") or "").upper()
                object_uuid = str(payload.get("objectID") or "").upper()
                actor_index = (
                    nodes[actor_uuid].index
                    if actor_uuid in nodes
                    else next_index
                )
                if actor_uuid not in nodes:
                    next_index += 1
                object_index = (
                    nodes[object_uuid].index
                    if object_uuid in nodes
                    else (
                        actor_index
                        if object_uuid == actor_uuid
                        else next_index
                    )
                )
                if object_uuid not in nodes and object_uuid != actor_uuid:
                    next_index += 1
                projected = project_event(
                    payload,
                    actor_index,
                    object_index,
                )
                if projected is None:
                    counts["malformed"] += 1
                    continue
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                counts["malformed"] += 1
                continue
            actor_node, object_node, edge = projected
            for incoming in (actor_node, object_node):
                current = nodes.get(incoming.uuid)
                merged = (
                    incoming
                    if current is None
                    else merge_node(current, incoming)
                )
                if current != merged:
                    nodes[incoming.uuid] = merged
                    dirty[incoming.uuid] = merged
            source_node = nodes[edge.source]
            target_node = nodes[edge.target]
            edges.append(
                (
                    hash_id(source_node.uuid),
                    source_node.index,
                    edge.relation,
                    hash_id(target_node.uuid),
                    target_node.index,
                    edge.event_uuid.lower(),
                    edge.timestamp,
                )
            )
            relations[
                (
                    edge.relation,
                    edge.source_kind,
                    edge.target_kind,
                    edge.canonical or "",
                )
            ] += 1
            counts["events"] += 1
            if len(edges) >= batch_size:
                flush(connection, dirty.values(), edges)
                dirty.clear()
                edges.clear()
    flush(connection, dirty.values(), edges)
    stats = {
        "counts": dict(sorted(counts.items())),
        "relations": [
            {
                "raw": key[0],
                "source_kind": key[1],
                "target_kind": key[2],
                "canonical": key[3] or None,
                "count": value,
            }
            for key, value in sorted(relations.items())
        ],
    }
    with connection.cursor() as cursor:
        cursor.execute(
            "insert into optc_source values(%s, %s, %s, %s, %s)",
            (
                path.name,
                source["sha256"],
                day,
                counts["events"],
                json.dumps(stats),
            ),
        )
    connection.commit()
    return stats


def ingest(
    index: Path,
    directory: Path,
    host: str,
    dsn: str,
    output: Path,
    batch_size: int = 50000,
    wait: bool = False,
) -> dict:
    import psycopg2

    source_stream = source_files(index, directory, host, wait)
    sources = []
    started = time.perf_counter()
    with psycopg2.connect(dsn) as connection:
        table_setup(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                "select value from optc_projection where key='identity'"
            )
            row = cursor.fetchone()
            identity = f"corrected_optc_sysclient{host}_v1"
            if row is not None and row[0] != identity:
                raise ValueError("database projection identity mismatch")
            cursor.execute(
                "insert into optc_projection values('identity', %s) "
                "on conflict(key) do nothing",
                (identity,),
            )
        connection.commit()
        nodes = load_nodes(connection)
        results = []
        for source in source_stream:
            sources.append(source)
            results.append(
                {
                    "day": source["day"],
                    "result": ingest_file(
                        connection,
                        source,
                        nodes,
                        batch_size,
                    ),
                }
            )
        with connection.cursor() as cursor:
            cursor.execute(
                "create index if not exists event_table_timestamp "
                "on event_table(timestamp_rec)"
            )
            cursor.execute("analyze")
            cursor.execute("select count(*) from event_table")
            events = int(cursor.fetchone()[0])
            table_counts = {}
            for table in (
                "subject_node_table",
                "file_node_table",
                "netflow_node_table",
            ):
                cursor.execute(f"select count(*) from {table}")
                table_counts[table] = int(cursor.fetchone()[0])
            cursor.execute(
                "select filename, sha256, day, events, stats "
                "from optc_source order by day"
            )
            completed = [
                {
                    "filename": row[0],
                    "sha256": row[1],
                    "day": row[2],
                    "events": row[3],
                    "stats": row[4],
                }
                for row in cursor
            ]
        connection.commit()
    payload = {
        "method": "corrected_optc_projection_v1",
        "label_free": True,
        "source": "doi:10.57745/UXCWOC",
        "host": host,
        "split": {
            "train": [19, 20, 21],
            "validation": [22],
            "test": [23, 24, 25],
        },
        "index_sha256": digest(index),
        "sources": [
            {
                **{key: value for key, value in item.items() if key != "path"},
                "filename": item["path"].name,
            }
            for item in sources
        ],
        "events": events,
        "nodes": table_counts,
        "completed": completed,
        "runtime_seconds": time.perf_counter() - started,
        "runs": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--host", choices=("0201", "0501"), required=True)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=50000)
    parser.add_argument("--wait", action="store_true")
    args = parser.parse_args()
    result = ingest(
        args.index,
        args.input,
        args.host,
        args.dsn,
        args.output,
        args.batch_size,
        args.wait,
    )
    print(
        json.dumps(
            {
                "host": result["host"],
                "events": result["events"],
                "nodes": result["nodes"],
                "runtime_seconds": result["runtime_seconds"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
