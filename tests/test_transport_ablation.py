import math

from experiments.transport_ablation import (
    ablation_edges,
    selection_payload,
)
from wisa_agent.tc.ravel import TransportEdge


def edges() -> tuple[TransportEdge, ...]:
    return (
        TransportEdge("a", "a", 0.0, 2.0, 0, "local"),
        TransportEdge("a", "x", 0.4, 1.0, 1, "proof"),
        TransportEdge("a", "y", 0.3, 2.0, 1, "proof"),
        TransportEdge("b", "b", 0.0, 1.0, 0, "local"),
        TransportEdge("b", "x", 0.5, 1.0, 1, "proof"),
    )


def test_topology_ablation_discards_proof_weights():
    values = ablation_edges(edges(), "topology")
    assert {
        edge.utility
        for edge in values
        if edge.kind == "proof"
    } == {1.0}
    assert {
        edge.utility
        for edge in values
        if edge.kind == "local"
    } == {0.0}


def test_rank_ablation_is_bounded_and_monotone():
    values = ablation_edges(edges(), "rank")
    utilities = {
        edge.e_value: edge.utility
        for edge in values
        if edge.kind == "proof"
    }
    assert math.isclose(utilities[1.0], 0.75)
    assert math.isclose(utilities[2.0], 0.9375)
    assert 0.0 <= utilities[1.0] < utilities[2.0] <= 1.0


def test_ablation_selection_preserves_budget_and_uniqueness():
    payload = selection_payload(
        ablation_edges(edges(), "rank"),
        {"a", "b"},
    )
    assert len(payload["nodes"]) == 2
    assert len(set(payload["nodes"])) == 2
    assert payload["certificate"]["root_degree_min"] == 1
    assert payload["certificate"]["root_degree_max"] == 1
    assert payload["certificate"]["node_degree_max"] == 1
