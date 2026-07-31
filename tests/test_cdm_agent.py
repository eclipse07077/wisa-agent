from wisa_agent.tc.cdm_agent import (
    CDMAttackAgent,
    NormalProfile,
    ProvenanceEvent,
    validation_threshold,
)


def event(
    timestamp: int,
    source: str,
    target: str,
    relation: str,
) -> ProvenanceEvent:
    return ProvenanceEvent(
        timestamp=timestamp,
        source=source,
        target=target,
        relation=relation,
        path="",
        source_kind="subject",
        target_kind="file",
    )


def test_raw_chain_reaches_mission_effect():
    normal = [
        event(1, "a", "b", "EVENT_OPEN"),
        event(2, "a", "b", "EVENT_READ"),
    ]
    profile = NormalProfile()
    profile.fit(normal)
    attack = [
        event(10_000_000_000, "n", "p", "EVENT_CONNECT"),
        event(11_000_000_000, "p", "q", "EVENT_EXECUTE"),
        event(12_000_000_000, "q", "r", "EVENT_OPEN"),
        event(13_000_000_000, "r", "s", "EVENT_WRITE"),
    ]
    result = CDMAttackAgent(
        profile,
        threshold=0.0,
        candidate_limit=32,
    ).run(attack)
    assert result.chains


def test_validation_threshold_uses_only_scores():
    profile = NormalProfile()
    events = [
        event(1, "a", "b", "EVENT_OPEN"),
        event(2, "a", "b", "EVENT_READ"),
    ]
    profile.fit(events)
    threshold = validation_threshold(profile, events)
    assert 0.0 <= threshold <= 1.0


def test_semantic_predicates_aggregate_subject_session():
    profile = NormalProfile()
    profile.fit([event(1, "a", "b", "EVENT_READ")])
    attack = [
        ProvenanceEvent(
            10_000_000_000,
            "process",
            "flow",
            "EVENT_CONNECT",
            "",
            "subject",
            "netflow",
        ),
        ProvenanceEvent(
            11_000_000_000,
            "binary",
            "process",
            "EVENT_EXECUTE",
            "",
            "file",
            "subject",
        ),
        ProvenanceEvent(
            12_000_000_000,
            "config",
            "process",
            "EVENT_OPEN",
            "",
            "file",
            "subject",
        ),
        ProvenanceEvent(
            13_000_000_000,
            "process",
            "output",
            "EVENT_WRITE",
            "",
            "subject",
            "file",
        ),
    ]
    result = CDMAttackAgent(
        profile,
        threshold=0.0,
        candidate_limit=32,
        predicate_mode="semantic",
    ).run(attack)
    assert len(result.predicates) == 4
    assert result.chains
    assert max(result.chain_scores.values()) <= result.chains[0].score
    assert {plan.group for plan in result.plans} >= {
        "baseline",
        "negative",
        "combined",
    }


def test_trace_predicates_keep_normal_context_around_seed():
    profile = NormalProfile()
    normal = [
        ProvenanceEvent(
            index,
            "process",
            "flow",
            "EVENT_CONNECT",
            "",
            "subject",
            "netflow",
        )
        for index in range(1, 6)
    ]
    profile.fit(normal)
    trace = [
        normal[0],
        ProvenanceEvent(
            2,
            "binary",
            "process",
            "EVENT_EXECUTE",
            "",
            "file",
            "subject",
        ),
        ProvenanceEvent(
            3,
            "config",
            "process",
            "EVENT_OPEN",
            "",
            "file",
            "subject",
        ),
        ProvenanceEvent(
            4,
            "process",
            "output",
            "EVENT_WRITE",
            "",
            "subject",
            "file",
        ),
    ]
    result = CDMAttackAgent(
        profile,
        threshold=0.1,
        candidate_limit=32,
        predicate_mode="trace",
    ).run(trace)
    assert len(result.predicates) == 4
    assert result.chains


def test_missing_path_is_marginalized():
    profile = NormalProfile(marginalize_missing=True)
    normal = [
        event(1, "a", "b", "EVENT_OPEN"),
        event(2, "a", "b", "EVENT_READ"),
    ]
    profile.fit(normal)
    assert not profile.paths
    assert 0.0 <= profile.score(normal[0], None).score <= 1.0


def test_missing_path_uses_presence_profile():
    profile = NormalProfile(missingness_aware=True)
    normal = [
        event(1, "a", "b", "EVENT_OPEN"),
        ProvenanceEvent(
            2,
            "a",
            "b",
            "EVENT_OPEN",
            "/usr/bin/tool",
            "subject",
            "file",
        ),
    ]
    profile.fit(normal)
    assert profile.path_presence[("EVENT_OPEN", False)] == 1
    assert profile.path_presence[("EVENT_OPEN", True)] == 1
    assert 0.0 <= profile.score(normal[0], None).path <= 1.0


def test_connector_attribution_excludes_single_stage_leaves():
    profile = NormalProfile(marginalize_missing=True)
    profile.fit([event(1, "a", "b", "EVENT_READ")])
    trace = [
        ProvenanceEvent(
            10_000_000_000,
            "process",
            "flow",
            "EVENT_CONNECT",
            "",
            "subject",
            "netflow",
        ),
        ProvenanceEvent(
            11_000_000_000,
            "binary",
            "process",
            "EVENT_EXECUTE",
            "",
            "file",
            "subject",
        ),
        ProvenanceEvent(
            12_000_000_000,
            "config",
            "process",
            "EVENT_OPEN",
            "",
            "file",
            "subject",
        ),
        ProvenanceEvent(
            13_000_000_000,
            "process",
            "output",
            "EVENT_WRITE",
            "",
            "subject",
            "file",
        ),
    ]
    result = CDMAttackAgent(
        profile,
        threshold=0.1,
        candidate_limit=32,
        predicate_mode="trace",
        attribution_mode="connectors",
    ).run(trace)
    assert result.chains
    assert set(result.chain_scores) == {"process"}
    cutset = CDMAttackAgent(
        profile,
        threshold=0.1,
        candidate_limit=32,
        predicate_mode="trace",
        attribution_mode="cutset",
    ).run(trace)
    assert cutset.chains
    assert set(cutset.chain_scores) == {"process"}
    core = CDMAttackAgent(
        profile,
        threshold=0.1,
        candidate_limit=32,
        predicate_mode="trace",
        attribution_mode="core",
    ).run(trace)
    assert core.chains
    assert set(core.chain_scores) == {"process"}


def test_grounded_attribution_preserves_local_node_order():
    profile = NormalProfile()
    profile.fit([event(1, "a", "b", "EVENT_READ")])
    trace = [
        ProvenanceEvent(
            10_000_000_000,
            "process",
            "flow",
            "EVENT_CONNECT",
            "",
            "subject",
            "netflow",
        ),
        ProvenanceEvent(
            11_000_000_000,
            "binary",
            "process",
            "EVENT_EXECUTE",
            "/tmp/tool",
            "file",
            "subject",
        ),
        ProvenanceEvent(
            12_000_000_000,
            "config",
            "process",
            "EVENT_OPEN",
            "/tmp/config",
            "file",
            "subject",
        ),
        ProvenanceEvent(
            13_000_000_000,
            "process",
            "output",
            "EVENT_WRITE",
            "/tmp/output",
            "subject",
            "file",
        ),
    ]
    result = CDMAttackAgent(
        profile,
        threshold=0.0,
        candidate_limit=32,
        predicate_mode="trace",
        attribution_mode="grounded",
    ).run(trace)
    assert result.chains
    assert set(result.chain_scores) == {
        "process",
        "flow",
        "binary",
        "config",
        "output",
    }
    assert all(
        result.chain_scores[node] <= result.node_scores[node]
        for node in result.chain_scores
    )
