import sqlite3

from experiments.adapter import adapter_manifest


def test_adapter_manifest_is_label_free_and_deterministic():
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "create table metadata(key text primary key, value text)"
    )
    connection.execute(
        "create table relation_map("
        "raw text, source_kind text, target_kind text, "
        "canonical text, count integer)"
    )
    connection.execute(
        "create table events(day integer, relation text)"
    )
    connection.executemany(
        "insert into metadata values(?, ?)",
        (("complete", "1"), ("events", "2"), ("unmapped_events", "1")),
    )
    connection.execute(
        "insert into relation_map values(?, ?, ?, ?, ?)",
        ("START", "netflow", "subject", "EVENT_CONNECT", 2),
    )
    connection.executemany(
        "insert into events values(?, ?)",
        ((23, "EVENT_CONNECT"), (23, "EVENT_CONNECT")),
    )
    first = adapter_manifest(connection, b"source", "dump")
    second = adapter_manifest(connection, b"source", "dump")
    assert first == second
    assert first["label_free"] is True
    assert first["mapping_sha256"] == second["mapping_sha256"]
    assert first["events_by_day"] == [
        {"day": 23, "canonical": "EVENT_CONNECT", "count": 2}
    ]
