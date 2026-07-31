import numpy as np

from wisa_agent.tc import LayerModel, ProvenanceAttackAgent, ProvenanceGraph


def test_layer_discovery_and_chain():
    node_types = np.array([0, 1, 2, 3, 4], dtype=np.int64)
    edges = np.array([[0, 1], [1, 2], [2, 3], [3, 4]], dtype=np.int64)
    model = LayerModel.fit([(node_types, edges)])
    graph = ProvenanceGraph(
        node_types=node_types,
        edges=edges,
        edge_types=np.zeros(len(edges), dtype=np.int64),
        scores=np.array([0.9, 0.8, 0.7, 0.6, 0.5]),
        evaluation_mask=np.ones(len(node_types), dtype=bool),
    )
    result = ProvenanceAttackAgent(
        model,
        seed_fraction=1.0,
        max_seeds=5,
    ).run(graph)
    assert len(result.layers) == 5
    assert result.predicates
    assert result.chains


def test_tied_percentiles_are_equal():
    values = np.array([1.0, 1.0, 2.0, 3.0])
    mask = np.ones(4, dtype=bool)
    percentiles = ProvenanceAttackAgent._percentile(values, mask)
    assert percentiles[0] == percentiles[1]
    assert percentiles[-1] == 1.0
