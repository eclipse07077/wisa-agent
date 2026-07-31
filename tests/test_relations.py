from wisa_agent.tc.relations import normalize_relation


def test_canonical_relations_are_preserved():
    assert normalize_relation("EVENT_EXECUTE", "file", "subject") == (
        "EVENT_EXECUTE"
    )


def test_optc_file_relations_use_canonical_semantics():
    assert normalize_relation("OPEN", "file", "subject") == "EVENT_OPEN"
    assert normalize_relation("READ", "file", "subject") == "EVENT_READ"
    assert normalize_relation("WRITE", "subject", "file") == "EVENT_WRITE"
    assert normalize_relation("MODIFY", "subject", "file") == "EVENT_WRITE"


def test_optc_create_uses_endpoint_types():
    assert normalize_relation("CREATE", "subject", "subject") == "EVENT_CLONE"
    assert normalize_relation("CREATE", "subject", "file") == "EVENT_WRITE"
    assert normalize_relation("CREATE", "subject", "netflow") == (
        "EVENT_CONNECT"
    )


def test_optc_start_uses_endpoint_types():
    assert normalize_relation("START", "netflow", "subject") == (
        "EVENT_CONNECT"
    )
    assert normalize_relation("START", "subject", "netflow") == (
        "EVENT_CONNECT"
    )
    assert normalize_relation("START", "subject", "subject") == (
        "EVENT_EXECUTE"
    )


def test_optc_message_uses_network_direction():
    assert normalize_relation("MESSAGE", "netflow", "subject") == (
        "EVENT_RECVMSG"
    )
    assert normalize_relation("MESSAGE", "subject", "netflow") == (
        "EVENT_SENDMSG"
    )


def test_ambiguous_optc_relations_remain_unmapped():
    assert normalize_relation("TERMINATE", "subject", "subject") is None
    assert normalize_relation("READ", "subject", "netflow") is None
