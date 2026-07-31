import gzip
import io
import json
import sqlite3
import tarfile
import uuid

import pytest

from wisa_agent.tc.cdm import (
    build_index,
    datum,
    day_boundaries,
    event_record,
)


def line(kind: str, payload: dict, version: str = "cdm18") -> bytes:
    return json.dumps(
        {"datum": {f"com.bbn.tc.schema.avro.{version}.{kind}": payload}}
    ).encode()


def test_event_parsing_and_index(tmp_path):
    subject = line(
        "Subject",
        {"uuid": "source", "type": "SUBJECT_PROCESS"},
    )
    file_object = line(
        "FileObject",
        {"uuid": "target", "type": "FILE_OBJECT_FILE"},
    )
    timestamp = day_boundaries()[2] + 1
    event_line = line(
        "Event",
        {
            "type": "EVENT_WRITE",
            "subject": {"uuid": "source"},
            "predicateObject": {"uuid": "target"},
            "timestampNanos": timestamp,
        },
    )
    kind, payload = datum(event_line)
    event = event_record(kind, payload, day_boundaries())
    assert event is not None
    assert event.day == 3
    archive = tmp_path / "sample.tar.gz"
    content = b"\n".join((subject, file_object, event_line))
    with tarfile.open(archive, "w:gz") as handle:
        info = tarfile.TarInfo("sample.json")
        info.size = len(content)
        handle.addfile(info, io.BytesIO(content))
    output = tmp_path / "index.sqlite"
    counts = build_index([archive], output)
    assert counts["events"] == 1
    assert output.exists()


def test_cdm20_gzip_and_calendar_offset(tmp_path):
    timestamp = day_boundaries(2019, 5, 8, 18)[0] + 1
    rows = (
        line(
            "Subject",
            {"uuid": "source", "cmdLine": {"string": "proc"}},
            "cdm20",
        ),
        line(
            "FileObject",
            {"uuid": "target", "type": "FILE_OBJECT_FILE"},
            "cdm20",
        ),
        line(
            "Event",
            {
                "type": "EVENT_WRITE",
                "subject": {"uuid": "source"},
                "predicateObject": {"uuid": "target"},
                "timestampNanos": timestamp,
            },
            "cdm20",
        ),
    )
    path = tmp_path / "sample.bin.1.gz"
    with gzip.open(path, "wb") as handle:
        handle.write(b"\n".join(rows))
    output = tmp_path / "index.sqlite"
    counts = build_index(
        [path],
        output,
        year=2019,
        month=5,
        start_day=8,
        end_day=18,
    )
    assert counts["events"] == 1
    with sqlite3.connect(output) as connection:
        day = connection.execute("select day from events").fetchone()[0]
    assert day == 8


def test_avro_object_container_input(tmp_path):
    fastavro = pytest.importorskip("fastavro")
    namespace = "com.bbn.tc.schema.avro.cdm20"
    schema = {
        "type": "record",
        "name": "TCCDMDatum",
        "namespace": namespace,
        "fields": [
            {
                "name": "datum",
                "type": [
                    {
                        "type": "record",
                        "name": "Subject",
                        "fields": [
                            {"name": "uuid", "type": "bytes"},
                            {"name": "cmdLine", "type": ["null", "string"]},
                        ],
                    },
                    {
                        "type": "record",
                        "name": "FileObject",
                        "fields": [
                            {"name": "uuid", "type": "bytes"},
                            {"name": "type", "type": "string"},
                        ],
                    },
                    {
                        "type": "record",
                        "name": "Event",
                        "fields": [
                            {"name": "type", "type": "string"},
                            {"name": "subject", "type": "bytes"},
                            {"name": "predicateObject", "type": "bytes"},
                            {"name": "timestampNanos", "type": "long"},
                        ],
                    },
                ],
            }
        ],
    }
    source = uuid.UUID("00000000-0000-0000-0000-000000000001")
    target = uuid.UUID("00000000-0000-0000-0000-000000000002")
    timestamp = day_boundaries(2019, 5, 8, 18)[0] + 1
    records = [
        {
            "datum": (
                f"{namespace}.Subject",
                {"uuid": source.bytes, "cmdLine": "proc"},
            )
        },
        {
            "datum": (
                f"{namespace}.FileObject",
                {"uuid": target.bytes, "type": "FILE_OBJECT_FILE"},
            )
        },
        {
            "datum": (
                f"{namespace}.Event",
                {
                    "type": "EVENT_WRITE",
                    "subject": source.bytes,
                    "predicateObject": target.bytes,
                    "timestampNanos": timestamp,
                },
            )
        },
    ]
    path = tmp_path / "sample.avro.gz"
    with gzip.open(path, "wb") as handle:
        fastavro.writer(handle, schema, records)
    output = tmp_path / "index.sqlite"
    counts = build_index(
        [path],
        output,
        year=2019,
        month=5,
        start_day=8,
        end_day=18,
    )
    assert counts["events"] == 1
    with sqlite3.connect(output) as connection:
        row = connection.execute(
            "select source, target, day from events"
        ).fetchone()
    assert row == (str(source).upper(), str(target).upper(), 8)
