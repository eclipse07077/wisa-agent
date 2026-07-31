import itertools
import math

from wisa_agent.method import Chain, ChainEdge, Predicate, Stage
from wisa_agent.tc.flow import (
    FlowSelector,
    chain_reliability,
    conserved_flow,
    counterfactual_responsibility,
)


def predicate(
    name: str,
    stage: Stage,
    endpoints: tuple[str, ...],
    scores: tuple[float, ...],
) -> Predicate:
    return Predicate(
        predicate_id=name,
        stage=stage,
        target=endpoints[-1],
        layer="subject->file",
        relation=name,
        timestamp=float(len(name)),
        context=frozenset({name}),
        confidence=max(scores),
        severity=max(scores),
        mission_relevant=stage == Stage.MISSION_EFFECT,
        evidence_ids=(name,),
        details={
            "endpoints": endpoints,
            "endpoint_scores": tuple(zip(endpoints, scores)),
        },
    )


def sample_chain() -> Chain:
    predicates = (
        predicate(
            "p1",
            Stage.TRUST_BREAK,
            ("seed", "bridge", "leaf1"),
            (0.9, 0.7, 0.4),
        ),
        predicate(
            "p2",
            Stage.LIFECYCLE,
            ("bridge", "pivot", "leaf2"),
            (0.8, 0.6, 0.3),
        ),
        predicate(
            "p3",
            Stage.MISSION_EFFECT,
            ("pivot", "target"),
            (0.7, 0.95),
        ),
    )
    edges = (
        ChainEdge("p1", "p2", 0.8, ()),
        ChainEdge("p2", "p3", 0.9, ()),
    )
    return Chain("c1", predicates, edges, 0.85)


def reference_chain_reliability(
    chain: Chain,
    removed: str | None = None,
) -> float:
    endpoint_sets = [
        {
            node
            for node in predicate.details["endpoints"]
            if node != removed
        }
        for predicate in chain.predicates
    ]
    if any(not endpoints for endpoints in endpoint_sets):
        return 0.0
    if any(
        not (endpoint_sets[index] & endpoint_sets[index + 1])
        for index in range(len(endpoint_sets) - 1)
    ):
        return 0.0
    predicate_values = []
    for predicate in chain.predicates:
        endpoints = [
            node
            for node in predicate.details["endpoints"]
            if node != removed
        ]
        scores = dict(predicate.details.get("endpoint_scores", ()))
        complement = math.prod(
            1.0
            - min(
                max(
                    float(scores.get(node, predicate.confidence)),
                    0.0,
                ),
                1.0,
            )
            for node in endpoints
        )
        predicate_values.append(1.0 - complement)
    return (
        math.prod(predicate_values)
        * math.prod(edge.score for edge in chain.edges)
    )


def test_reliability_optimization_is_bit_identical():
    chain = sample_chain()
    nodes = {
        node
        for predicate in chain.predicates
        for node in predicate.details["endpoints"]
    }
    for removed in (None, *sorted(nodes)):
        assert chain_reliability(
            chain,
            removed,
        ) == reference_chain_reliability(
            chain,
            removed,
        )


def test_counterfactual_responsibility_is_bounded():
    chain = sample_chain()
    values = counterfactual_responsibility(chain)
    assert chain_reliability(chain) > 0.0
    assert all(0.0 <= value <= 1.0 for value in values.values())
    assert values["bridge"] == 1.0
    assert values["pivot"] == 1.0
    assert 0.0 < values["target"] < 1.0


def test_conserved_flow_sums_to_one():
    values = conserved_flow(sample_chain())
    assert math.isclose(sum(values.values()), 1.0)
    assert values["pivot"] > values["bridge"]


def test_conserved_flow_matches_local_evidence_ratio():
    chain = Chain(
        "ratio",
        (
            predicate(
                "left",
                Stage.TRUST_BREAK,
                ("u", "v"),
                (0.9, 0.4),
            ),
            predicate(
                "right",
                Stage.LIFECYCLE,
                ("u", "v"),
                (0.4, 0.1),
            ),
        ),
        (ChainEdge("left", "right", 0.8, ()),),
        0.8,
    )
    values = conserved_flow(chain)
    expected_ratio = math.sqrt(0.9 * 0.4) / math.sqrt(0.4 * 0.1)
    assert math.isclose(values["u"] / values["v"], expected_ratio)
    assert math.isclose(sum(values.values()), 1.0)


def test_flowsub_greedy_respects_budget_and_beats_bound():
    chain = sample_chain()
    scores = {
        "seed": 1.0,
        "bridge": 0.8,
        "pivot": 0.7,
        "leaf1": 0.6,
        "leaf2": 0.5,
        "target": 0.9,
    }
    selector = FlowSelector(scores, {"seed", "target"}, (chain,))
    selection = selector.select(budget=2)
    assert len(selection.nodes) == 2
    assert len(set(selection.nodes)) == 2

    candidates = sorted(selector.candidates)
    best = max(
        selector.objective(chosen, budget=2)
        for chosen in itertools.combinations(candidates, 2)
    )
    assert math.isclose(
        selection.objective,
        selector.objective(selection.nodes, budget=2),
    )
    assert selection.objective >= (1.0 - 1.0 / math.e) * best


def test_selection_is_invariant_to_strict_score_transform():
    chain = sample_chain()
    scores = {
        "seed": 1.0,
        "bridge": 0.8,
        "pivot": 0.7,
        "leaf1": 0.6,
        "leaf2": 0.5,
        "target": 0.9,
    }
    transformed = {
        node: math.exp(score)
        for node, score in scores.items()
    }
    original = FlowSelector(
        scores,
        {"seed", "target"},
        (chain,),
    ).select(budget=2)
    mapped = FlowSelector(
        transformed,
        {"seed", "target"},
        (chain,),
    ).select(budget=2)
    assert original.nodes == mapped.nodes
    assert original.gains == mapped.gains


def test_marginal_returns_diminish():
    chain = sample_chain()
    scores = {
        "seed": 1.0,
        "bridge": 0.8,
        "pivot": 0.7,
        "leaf1": 0.6,
        "leaf2": 0.5,
        "target": 0.9,
    }
    selector = FlowSelector(scores, {"seed", "target"}, (chain,))
    one = selector.select(budget=1)
    two = selector.select(budget=2)
    assert two.gains[1] <= one.gains[0]


def test_lazy_selection_matches_full_scan():
    chain = sample_chain()
    scores = {
        "seed": 1.0,
        "bridge": 0.8,
        "pivot": 0.7,
        "leaf1": 0.6,
        "leaf2": 0.5,
        "target": 0.9,
    }
    selector = FlowSelector(scores, {"seed", "target"}, (chain,))
    for mode in ("anomaly", "responsibility", "flow", "full"):
        for budget in range(1, len(selector.candidates) + 1):
            lazy = selector.select(
                budget=budget,
                mode=mode,
            )
            scan = selector.select(
                budget=budget,
                mode=mode,
                lazy=False,
            )
            assert lazy.nodes == scan.nodes
            assert lazy.gains == scan.gains
            assert lazy.objective == scan.objective


def test_lazy_selection_preserves_lexicographic_ties():
    selector = FlowSelector(
        {"a": 1.0, "b": 1.0, "c": 1.0},
        {"a", "b", "c"},
        (),
    )
    assert selector.select().nodes == ("c", "b", "a")
