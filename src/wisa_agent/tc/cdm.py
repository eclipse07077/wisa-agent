from __future__ import annotations

import bisect
import gzip
import json
import sqlite3
import tarfile
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator
from zoneinfo import ZoneInfo

from wisa_agent.tc.relations import REVERSED_RELATIONS, TRACKED_RELATIONS


@dataclass(frozen=True)
class CDMNode:
    uuid: str
    kind: str
    name: str


@dataclass(frozen=True)
class CDMEvent:
    timestamp: int
    day: int
    source: str
    target: str
    relation: str
    path: str


def unwrap(value):
    while True:
        if (
            isinstance(value, tuple)
            and len(value) == 2
            and isinstance(value[0], str)
        ):
            value = value[1]
            continue
        if isinstance(value, dict) and len(value) == 1:
            value = next(iter(value.values()))
            continue
        break
    return value


def uuid_text(value) -> str:
    value = unwrap(value)
    if isinstance(value, bytes) and len(value) == 16:
        return str(uuid.UUID(bytes=value)).upper()
    return str(value or "").upper()


def datum_record(record: dict):
    value = record.get("datum", record)
    if (
        isinstance(value, tuple)
        and len(value) == 2
        and isinstance(value[0], str)
    ):
        return value[0].rsplit(".", 1)[-1], value[1]
    if not isinstance(value, dict) or len(value) != 1:
        return "", {}
    key, payload = next(iter(value.items()))
    return key.rsplit(".", 1)[-1], payload


def datum(line: bytes, loader: Callable[[bytes], dict] = json.loads):
    return datum_record(loader(line))


def node_record(kind: str, payload: dict) -> CDMNode | None:
    if kind not in {"Subject", "FileObject", "NetFlowObject"}:
        return None
    node_uuid = uuid_text(payload.get("uuid"))
    if not node_uuid:
        return None
    if kind == "Subject":
        name = str(unwrap(payload.get("cmdLine")) or payload.get("type") or "")
        node_kind = "subject"
    elif kind == "FileObject":
        name = str(payload.get("type") or "")
        node_kind = "file"
    else:
        address = str(unwrap(payload.get("remoteAddress")) or "")
        port = str(unwrap(payload.get("remotePort")) or "")
        name = ":".join(value for value in (address, port) if value)
        node_kind = "netflow"
    return CDMNode(node_uuid, node_kind, name)


def event_record(
    kind: str,
    payload: dict,
    boundaries: tuple[int, ...],
    day_offset: int = 0,
) -> CDMEvent | None:
    if kind != "Event":
        return None
    relation = str(payload.get("type") or "")
    if relation not in TRACKED_RELATIONS:
        return None
    source = uuid_text(payload.get("subject"))
    target = uuid_text(payload.get("predicateObject"))
    timestamp = int(payload.get("timestampNanos") or 0)
    if not source or not target or timestamp <= 0:
        return None
    day = day_offset + bisect.bisect_right(boundaries, timestamp)
    if relation in REVERSED_RELATIONS:
        source, target = target, source
    path = str(unwrap(payload.get("predicateObjectPath")) or "")
    return CDMEvent(timestamp, day, source, target, relation, path)


def day_boundaries(
    year: int = 2018,
    month: int = 4,
    start_day: int = 1,
    end_day: int = 15,
) -> tuple[int, ...]:
    zone = ZoneInfo("America/New_York")
    return tuple(
        int(datetime(year, month, day, tzinfo=zone).timestamp() * 1e9)
        for day in range(start_day, end_day + 1)
    )


def archive_lines(path: Path) -> Iterator[bytes]:
    if tarfile.is_tarfile(path):
        with tarfile.open(path, "r|gz") as archive:
            for member in archive:
                if not member.isfile():
                    continue
                handle = archive.extractfile(member)
                if handle is None:
                    continue
                yield from handle
        return
    with gzip.open(path, "rb") as handle:
        yield from handle


def archive_records(
    path: Path,
    loader: Callable[[bytes], dict],
) -> Iterator[tuple[str, dict]]:
    if tarfile.is_tarfile(path):
        for line in archive_lines(path):
            yield datum(line, loader)
        return
    with gzip.open(path, "rb") as handle:
        magic = handle.read(4)
        handle.seek(0)
        if magic == b"Obj\x01":
            try:
                from fastavro import reader
            except ImportError as error:
                raise RuntimeError(
                    "fastavro is required for Avro Object Container input"
                ) from error
            for record in reader(handle, return_record_name=True):
                yield datum_record(record)
            return
        for line in handle:
            yield datum(line, loader)


def build_index(
    archives: list[Path],
    output: Path,
    loader: Callable[[bytes], dict] = json.loads,
    progress: Callable[[int, int], None] | None = None,
    year: int = 2018,
    month: int = 4,
    start_day: int = 1,
    end_day: int = 15,
) -> dict[str, int]:
    partial = output.with_suffix(output.suffix + ".partial")
    if output.exists():
        with sqlite3.connect(output) as connection:
            row = connection.execute(
                "select value from metadata where key = 'complete'"
            ).fetchone()
            if row and row[0] == "1":
                counts = connection.execute(
                    "select key, value from metadata where key != 'complete'"
                ).fetchall()
                return {key: int(value) for key, value in counts}
    partial.parent.mkdir(parents=True, exist_ok=True)
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
        "create table events(timestamp integer, day integer, "
        "source text, target text, relation text, path text)"
    )
    connection.execute(
        "create table metadata(key text primary key, value text)"
    )
    boundaries = day_boundaries(year, month, start_day, end_day)
    day_offset = start_day - 1
    node_batch: list[tuple[str, str, str]] = []
    event_batch: list[tuple[int, int, str, str, str, str]] = []
    records = 0
    nodes = 0
    events = 0
    for archive_index, archive in enumerate(archives):
        for kind, payload in archive_records(archive, loader):
            records += 1
            node = node_record(kind, payload)
            if node is not None:
                node_batch.append((node.uuid, node.kind, node.name))
                nodes += 1
            event = event_record(kind, payload, boundaries, day_offset)
            if event is not None:
                event_batch.append(
                    (
                        event.timestamp,
                        event.day,
                        event.source,
                        event.target,
                        event.relation,
                        event.path,
                    )
                )
                events += 1
            if len(node_batch) >= 50000:
                connection.executemany(
                    "insert into nodes values(?, ?, ?) "
                    "on conflict(uuid) do update set "
                    "kind=excluded.kind, "
                    "name=case when excluded.name != '' "
                    "then excluded.name else nodes.name end",
                    node_batch,
                )
                node_batch.clear()
            if len(event_batch) >= 50000:
                connection.executemany(
                    "insert into events values(?, ?, ?, ?, ?, ?)",
                    event_batch,
                )
                event_batch.clear()
            if progress is not None and records % 1000000 == 0:
                progress(records, archive_index)
        connection.commit()
    if node_batch:
        connection.executemany(
            "insert into nodes values(?, ?, ?) "
            "on conflict(uuid) do update set "
            "kind=excluded.kind, "
            "name=case when excluded.name != '' "
            "then excluded.name else nodes.name end",
            node_batch,
        )
    if event_batch:
        connection.executemany(
            "insert into events values(?, ?, ?, ?, ?, ?)",
            event_batch,
        )
    connection.execute("create index events_day_time on events(day, timestamp)")
    unique_nodes = int(
        connection.execute("select count(*) from nodes").fetchone()[0]
    )
    counts = {
        "records": records,
        "node_records": nodes,
        "nodes": unique_nodes,
        "events": events,
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
