import itertools
import math

from wisa_agent.method import Chain, ChainEdge, Predicate, Stage
from wisa_agent.tc.bear import BearLedger, conformal_e_values


def predicate(
    name: str,
    stage: Stage,
    endpoints: tuple[str, ...],
) -> Predicate:
    return Predicate(
        predicate_id=name,
        stage=stage,
        target=endpoints[-1],
        layer="subject->file",
        relation=name,
        timestamp=float(len(name)),
        context=frozenset({name}),
        confidence=0.8,
        severity=0.8,
        mission_relevant=stage == Stage.MISSION_EFFECT,
        evidence_ids=(name,),
        details={
            "endpoints": endpoints,
            "endpoint_scores": tuple(
                (node, 0.8)
                for node in endpoints
            ),
        },
    )


def chain(
    name: str,
    left: tuple[str, ...],
    right: tuple[str, ...],
) -> Chain:
    return Chain(
        name,
        (
            predicate(f"{name}-left", Stage.TRUST_BREAK, left),
            predicate(f"{name}-right", Stage.MISSION_EFFECT, right),
        ),
        (
            ChainEdge(
                f"{name}-left",
                f"{name}-right",
                1.0,
                (),
            ),
        ),
        1.0,
    )


def test_conformal_e_values_preserve_strict_score_order():
    scores = {"a": 1.0, "b": 2.0, "c": 3.0}
    calibration = (0.0, 1.0, 2.0, 3.0)
    original = conformal_e_values(scores, calibration)
    mapped = conformal_e_values(
        {
            node: math.exp(score)
            for node, score in scores.items()
        },
        tuple(math.exp(value) for value in calibration),
    )
    assert original == mapped
    assert original["a"] < original["b"] < original["c"]


def test_intervention_loss_matches_direct_recomputation():
    item = chain("c", ("a", "b"), ("b", "c"))
    ledger = BearLedger(
        {"a": 3.0, "b": 2.0, "c": 1.0},
        (0.0, 1.0, 2.0),
        {"a"},
        (item,),
    )
    for node in ledger.candidates:
        expected = (
            ledger.direct_ledger()
            - ledger.direct_ledger(removed=node)
        )
        actual = ledger.local_loss[node] + ledger.chain_loss[node]
        assert math.isclose(actual, expected)


def test_serial_bottleneck_has_unit_chain_responsibility():
    item = chain("c", ("bridge",), ("bridge",))
    ledger = BearLedger(
        {"bridge": 2.0},
        (0.0, 1.0),
        {"bridge"},
        (item,),
    )
    selected = ledger.select(mode="chain")
    assert math.isclose(selected.values[0].responsibility, 1.0)
    assert math.isclose(
        ledger.chain_values[item.chain_id],
        ledger.e_values["bridge"],
    )


def test_equal_parallel_routes_split_responsibility():
    first = chain("c1", ("a",), ("a",))
    second = chain("c2", ("b",), ("b",))
    ledger = BearLedger(
        {"a": 2.0, "b": 2.0},
        (0.0, 1.0),
        {"a", "b"},
        (first, second),
    )
    selected = ledger.select(budget=2, mode="chain")
    values = {
        value.node: value.responsibility
        for value in selected.values
    }
    assert math.isclose(values["a"], 0.5)
    assert math.isclose(values["b"], 0.5)


def test_route_length_mass_is_normalized():
    items = (
        chain("c1", ("a",), ("a",)),
        chain("c2", ("b",), ("b",)),
    )
    ledger = BearLedger(
        {"a": 2.0, "b": 1.0},
        (0.0, 1.0),
        {"a"},
        items,
    )
    assert math.isclose(sum(ledger.length_mass.values()), 1.0)
    allocated = (
        ledger.route_prior[1] * len(ledger.candidates)
        + sum(
            ledger.route_prior[len(item.predicates)]
            for item in items
        )
    )
    assert math.isclose(allocated, 1.0)


def test_local_mode_recovers_top_calibrated_scores():
    scores = {
        "a": 4.0,
        "b": 3.0,
        "c": 2.0,
        "d": 1.0,
    }
    item = chain("c", ("a", "c"), ("c", "d"))
    ledger = BearLedger(
        scores,
        (0.0, 1.0, 2.0, 3.0),
        {"a", "b"},
        (item,),
    )
    selected = ledger.select(budget=2, mode="local")
    assert set(selected.nodes) == {"a", "b"}


def test_chain_ledger_matches_expanded_route_sum():
    item = chain("c", ("a", "b"), ("b", "c"))
    ledger = BearLedger(
        {"a": 3.0, "b": 2.0, "c": 1.0},
        (0.0, 1.0, 2.0),
        {"a"},
        (item,),
    )
    endpoints = ledger.chain_endpoints[item.chain_id]
    occurrences = ledger.chain_occurrences[item.chain_id]
    expanded = sum(
        math.prod(
            ledger.e_values[node] ** (1.0 / occurrences[node])
            for node in route
        )
        / math.prod(len(group) for group in endpoints)
        for route in itertools.product(*endpoints)
    )
    assert math.isclose(
        ledger.chain_values[item.chain_id],
        expanded,
    )


def test_unit_growth_is_expanded_geometric_route_mean():
    item = chain("c", ("a", "b"), ("b", "c"))
    ledger = BearLedger(
        {"a": 3.0, "b": 2.0, "c": 1.0},
        (0.0, 1.0, 2.0),
        {"a"},
        (item,),
        unit_growth=True,
    )
    endpoints = ledger.chain_endpoints[item.chain_id]
    occurrences = ledger.chain_occurrences[item.chain_id]
    length = len(item.predicates)
    expanded = sum(
        math.prod(
            ledger.e_values[node]
            ** (1.0 / (length * occurrences[node]))
            for node in route
        )
        / math.prod(len(group) for group in endpoints)
        for route in itertools.product(*endpoints)
    )
    assert math.isclose(
        ledger.chain_values[item.chain_id],
        expanded,
    )


def test_unit_growth_preserves_intervention_identity():
    item = chain("c", ("a", "b"), ("b", "c"))
    ledger = BearLedger(
        {"a": 3.0, "b": 2.0, "c": 1.0},
        (0.0, 1.0, 2.0),
        {"a"},
        (item,),
        unit_growth=True,
    )
    for node in ledger.candidates:
        expected = (
            ledger.direct_ledger()
            - ledger.direct_ledger(removed=node)
        )
        actual = ledger.local_loss[node] + ledger.chain_loss[node]
        assert math.isclose(actual, expected)


def test_unit_growth_keeps_serial_bottleneck_exact():
    item = chain("c", ("bridge",), ("bridge",))
    ledger = BearLedger(
        {"bridge": 2.0},
        (0.0, 1.0),
        {"bridge"},
        (item,),
        unit_growth=True,
    )
    selected = ledger.select(mode="chain")
    assert math.isclose(selected.values[0].responsibility, 1.0)
    assert math.isclose(
        ledger.chain_values[item.chain_id],
        ledger.e_values["bridge"] ** 0.5,
    )
