from wisa_agent.method import (
    AttackOrchestrator,
    Chain,
    ChainBuilder,
    DecisionContext,
    DefenseOrchestrator,
    Predicate,
    ResponsePlanner,
    Stage,
)


def predicate(
    predicate_id: str,
    stage: Stage,
    layer: str,
    timestamp: float,
    severity: float = 0.8,
) -> Predicate:
    return Predicate(
        predicate_id=predicate_id,
        stage=stage,
        target="host-1",
        layer=layer,
        relation=predicate_id,
        timestamp=timestamp,
        context=frozenset({"host-1", "zone-1"}),
        confidence=0.85,
        severity=severity,
        mission_relevant=stage == Stage.MISSION_EFFECT,
        evidence_ids=(predicate_id,),
    )


def test_report_chain_and_plan():
    predicates = [
        predicate("p1", Stage.INGRESS, "network", 1),
        predicate("p2", Stage.TRUST_BREAK, "identity", 2),
        predicate("p3", Stage.LIFECYCLE, "process", 3),
        predicate("p4", Stage.MISSION_EFFECT, "mission", 4),
    ]
    attack = AttackOrchestrator(ChainBuilder(time_window=18))
    chains = attack.discover(predicates)
    assert chains
    assert chains[0].score > 0.7
    groups = {plan.group for plan in attack.plan(chains)}
    assert {"baseline", "single", "pairwise", "combined", "negative", "high_risk"} <= groups


def test_defense_uses_dynamic_honeypot_band():
    finding = DefenseOrchestrator(
        ChainBuilder(time_window=18),
        use_chain=False,
    ).assess(
        [predicate("p1", Stage.INGRESS, "network", 1, severity=0.3)],
        {"host-1": 0.4},
    )[0]
    assert finding.action in {"monitor", "honeypot"}


def test_missing_time_is_renormalized():
    left = predicate("p1", Stage.INGRESS, "network", 1)
    right = predicate("p2", Stage.TRUST_BREAK, "identity", 2)
    left = Predicate(**{**left.__dict__, "timestamp": None})
    right = Predicate(**{**right.__dict__, "timestamp": None})
    edge = ChainBuilder().edge(left, right)
    assert edge is not None
    assert edge.score >= 0.58


def test_verified_relation_can_supply_pair_context():
    left = predicate("p1", Stage.INGRESS, "network", 1)
    right = predicate("p2", Stage.TRUST_BREAK, "identity", 2)
    terminal = predicate("p3", Stage.MISSION_EFFECT, "mission", 3)
    left = Predicate(
        **{**left.__dict__, "timestamp": None, "context": frozenset({"a"})}
    )
    right = Predicate(
        **{**right.__dict__, "timestamp": None, "context": frozenset({"b"})}
    )
    terminal = Predicate(
        **{
            **terminal.__dict__,
            "timestamp": None,
            "context": frozenset({"c"}),
        }
    )
    chains = ChainBuilder().build(
        [left, right, terminal],
        compatible=lambda first, second: True,
        context_score=lambda first, second: 1.0,
    )
    assert chains


def test_deviation_risk_uses_report_formula():
    item = predicate("p1", Stage.INGRESS, "network", 1)
    item = Predicate(
        **{
            **item.__dict__,
            "details": {"adjusted_anomaly_magnitude": 1.0},
        }
    )
    finding = DefenseOrchestrator(
        ChainBuilder(time_window=18),
        use_chain=False,
    ).assess([item], {"host-1": 0.5})[0]
    expected_correlation = 0.55 * 0 + 0.25 * 0.5 + 0.20 * (1 / 3)
    deviation = 0.50 + 0.30 * expected_correlation + 0.20 * 0.5
    predefined = (
        0.35 * item.confidence
        + 0.25 * item.severity
        + 0.25 * expected_correlation
        + 0.15 * 0.5
    )
    assert finding.risk == max(predefined, deviation)


def test_temporal_deviation_reaches_isolation_band():
    item = predicate("p1", Stage.LIFECYCLE, "process", 1)
    item = Predicate(
        **{
            **item.__dict__,
            "details": {
                "adjusted_anomaly_magnitude": 0.8,
                "temporal_correlation": 2 / 3,
            },
        }
    )
    finding = DefenseOrchestrator(
        ChainBuilder(time_window=18),
        use_chain=False,
    ).assess([item], {"host-1": 0.55})[0]
    assert 0.70 <= finding.risk < 0.85
    assert finding.action == "temporary_isolate"


def test_critical_asset_requires_three_independent_layers():
    predicates = [
        predicate("p1", Stage.INGRESS, "network", 1, severity=1.0),
        predicate("p2", Stage.LIFECYCLE, "network", 2, severity=1.0),
        predicate("p3", Stage.MISSION_EFFECT, "mission", 3, severity=1.0),
    ]
    finding = DefenseOrchestrator(
        ChainBuilder(time_window=18),
    ).assess(predicates, {"host-1": 1.0})[0]
    assert finding.risk >= 0.85
    assert finding.action == "temporary_isolate"
    unguarded = DefenseOrchestrator(
        ChainBuilder(time_window=18),
        use_guard=False,
    ).assess(predicates, {"host-1": 1.0})[0]
    assert unguarded.action == "restore"


def test_response_planner_uses_information_under_uncertainty():
    ranked = ResponsePlanner().rank(
        DecisionContext(
            belief=0.65,
            evidence=0.30,
            criticality=0.55,
            coverage_gap=1.0,
            mission_effect=False,
        )
    )
    assert ranked[0].name == "honeypot"
    assert not {
        "temporary_isolate",
        "restore",
        "block",
    } & {item.name for item in ranked}


def test_response_planner_restores_confirmed_mission_effect():
    ranked = ResponsePlanner().rank(
        DecisionContext(
            belief=0.90,
            evidence=1.0,
            criticality=0.95,
            coverage_gap=0.0,
            mission_effect=True,
        )
    )
    assert ranked[0].name == "restore"


def test_chain_selection_penalizes_redundant_footprints():
    first = Predicate(
        **{
            **predicate(
                "first",
                Stage.INGRESS,
                "network",
                1,
            ).__dict__,
            "target": "a",
            "details": {"endpoints": ("a", "b")},
        }
    )
    duplicate = Predicate(
        **{
            **predicate(
                "duplicate",
                Stage.INGRESS,
                "network",
                1,
            ).__dict__,
            "target": "a",
            "details": {"endpoints": ("a", "b")},
        }
    )
    diverse = Predicate(
        **{
            **predicate(
                "diverse",
                Stage.INGRESS,
                "network",
                1,
            ).__dict__,
            "target": "c",
            "details": {"endpoints": ("c", "d")},
        }
    )
    chains = [
        Chain("first", (first,), (), 0.90),
        Chain("duplicate", (duplicate,), (), 0.89),
        Chain("diverse", (diverse,), (), 0.80),
    ]
    selected = ChainBuilder._diverse(chains, 2, 0.25)
    assert [item.chain_id for item in selected] == ["first", "diverse"]
