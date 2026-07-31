import json

from experiments.optc import (
    merge_node,
    node_from_event,
    project_event,
    timestamp_nanos,
)


def event(action: str, kind: str, direction: str = "") -> dict:
    return {
        "action": action,
        "actorID": "00000000-0000-0000-0000-000000000001",
        "id": "00000000-0000-0000-0000-000000000003",
        "object": kind,
        "objectID": "00000000-0000-0000-0000-000000000002",
        "properties": {
            "command_line": "child --run",
            "dest_ip": "10.0.0.2",
            "dest_port": "443",
            "direction": direction,
            "file_path": "C:\\sample.txt",
            "image_path": "C:\\sample.exe",
            "src_ip": "10.0.0.1",
            "src_port": "50000",
        },
        "timestamp": "2019-09-23T11:23:00.123456789-04:00",
    }


def test_timestamp_preserves_nanoseconds():
    assert timestamp_nanos("1970-01-01T00:00:00.000000007Z") == 7
    assert (
        timestamp_nanos("2019-09-23T11:23:00.123456789-04:00")
        % 1_000_000_000
        == 123456789
    )


def test_flow_direction_controls_orientation():
    inbound = project_event(event("MESSAGE", "FLOW", "inbound"), 1, 2)
    outbound = project_event(event("MESSAGE", "FLOW", "outbound"), 1, 2)
    assert inbound is not None and outbound is not None
    assert inbound[2].source_kind == "netflow"
    assert inbound[2].target_kind == "subject"
    assert inbound[2].canonical == "EVENT_RECVMSG"
    assert outbound[2].source_kind == "subject"
    assert outbound[2].target_kind == "netflow"
    assert outbound[2].canonical == "EVENT_SENDMSG"


def test_read_reverses_and_write_does_not():
    read = project_event(event("READ", "FILE"), 1, 2)
    write = project_event(event("WRITE", "FILE"), 1, 2)
    assert read is not None and write is not None
    assert (read[2].source_kind, read[2].target_kind) == (
        "file",
        "subject",
    )
    assert (write[2].source_kind, write[2].target_kind) == (
        "subject",
        "file",
    )
    assert read[2].canonical == "EVENT_READ"
    assert write[2].canonical == "EVENT_WRITE"


def test_process_is_subject_and_unsupported_object_is_dropped():
    process = project_event(event("CREATE", "PROCESS"), 1, 2)
    assert process is not None
    assert process[1].kind == "subject"
    assert process[2].canonical == "EVENT_CLONE"
    assert project_event(event("LOAD", "MODULE"), 1, 2) is None


def test_node_merge_keeps_first_nonempty_features():
    payload = event("CREATE", "PROCESS")
    first = node_from_event(payload, payload["objectID"], "subject", 2, False)
    payload = json.loads(json.dumps(payload))
    payload["properties"]["image_path"] = ""
    payload["properties"]["command_line"] = ""
    blank = node_from_event(payload, payload["objectID"], "subject", 2, False)
    assert merge_node(first, blank) == first
