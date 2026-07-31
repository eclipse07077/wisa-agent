from experiments.pg_events import provenance_event


def test_postgres_row_is_normalized_with_uuid_catalog():
    catalog = {
        "1": ("ACTOR", "subject"),
        "2": ("FLOW", "netflow"),
    }
    event = provenance_event((7, "2", "1", "MESSAGE"), catalog)
    assert event is not None
    assert event.timestamp == 7
    assert event.source == "FLOW"
    assert event.target == "ACTOR"
    assert event.relation == "EVENT_RECVMSG"
    assert event.source_kind == "netflow"
    assert event.target_kind == "subject"


def test_postgres_row_drops_unmapped_relation():
    catalog = {
        "1": ("ACTOR", "subject"),
        "2": ("PROCESS", "subject"),
    }
    assert provenance_event((7, "1", "2", "OPEN"), catalog) is None
    assert provenance_event((7, "1", "3", "CREATE"), catalog) is None
