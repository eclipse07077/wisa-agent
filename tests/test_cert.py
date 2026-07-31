import math

from wisa_agent.method import Chain, ChainEdge, Predicate, Stage
from wisa_agent.tc.cert import (
    _lexicographic_transport,
    certify_graph,
    certify_selection,
    cut_witness,
    groups,
    universal_cut,
)
from wisa_agent.tc.ravel import (
    RavelTransport,
    TransportEdge,
    TransportSelection,
)


def chain(
    identifier: str,
    groups: tuple[tuple[str, ...], ...],
) -> Chain:
    predicates = tuple(
        Predicate(
            predicate_id=f"{identifier}-{index}",
            stage=Stage.LIFECYCLE,
            layer="host",
            relation="relation",
            timestamp=float(index),
            context=frozenset(),
            confidence=1.0,
            severity=1.0,
            target=group[0],
            mission_relevant=False,
            evidence_ids=(),
            details={"endpoints": group},
        )
        for index, group in enumerate(groups)
    )
    edges = tuple(
        ChainEdge(
            source_id=left.predicate_id,
            target_id=right.predicate_id,
            score=1.0,
            factors=(),
        )
        for left, right in zip(predicates, predicates[1:])
    )
    return Chain(
        chain_id=identifier,
        predicates=predicates,
        edges=edges,
        score=1.0,
    )


def test_universal_cut_requires_every_route():
    values = (
        chain("a", (("r", "x"), ("x",))),
        chain("b", (("r", "x", "y"), ("x", "y"))),
    )
    assert not universal_cut(
        "r",
        "x",
        values,
        {"r", "x", "y"},
    )
    assert universal_cut(
        "r",
        "x",
        values[:1],
        {"r", "x", "y"},
    )
    witness = cut_witness(
        "r",
        "x",
        values[:1],
        {"r", "x", "y"},
    )
    assert witness is not None
    assert witness.root == "r"
    assert witness.node == "x"
    assert witness.routes[0].chain_id == "a"
    assert witness.routes[0].clauses == (1, 2)
    assert groups(values[0], {"r", "x", "y"}) == (
        frozenset({"r", "x"}),
        frozenset({"x"}),
        frozenset({"x"}),
    )


def test_certified_selection_reverts_uncertified_edges():
    values = (
        TransportEdge("r1", "x", 1.0, 3.0, 1, "proof"),
        TransportEdge("r2", "y", 0.4, 2.0, 1, "proof"),
        TransportEdge("r3", "r3", 0.0, 1.0, 0, "local"),
    )
    source = TransportSelection(
        mode="full",
        nodes=("x", "y", "r3"),
        ledger=1.4,
        candidates=6,
        budget=3,
        values=values,
        mass=1.0,
        expanded=2,
    )
    chains = (
        chain("a", (("r1", "x"), ("x",))),
        chain("b", (("r2", "y", "z"), ("y", "z"))),
    )
    result = certify_selection(
        source,
        chains,
        {"r1", "r2", "r3", "x", "y", "z"},
    )
    assert set(result.selection.nodes) == {"x", "r2", "r3"}
    assert result.source_transports == 2
    assert result.certified_transports == 1
    assert result.reverted_transports == 1
    assert len(result.witnesses) == 1
    assert result.witnesses[0].root == "r1"
    assert result.witnesses[0].node == "x"
    assert result.selection.ledger == 1.0
    assert result.certificate.budget == 3
    assert result.certificate.node_degree_max == 1


def test_universal_cut_is_equivalent_to_full_fracture():
    clauses = (
        ("r", "x"),
        ("r", "y"),
        ("r", "x", "y"),
        ("x",),
        ("y",),
        ("x", "y"),
    )
    scores = {"r": 4.0, "x": 3.0, "y": 2.0}
    checked = 0
    for left in clauses:
        for right in clauses:
            if "r" not in set(left) | set(right):
                continue
            if not set(left) & set(right):
                continue
            current = chain("route", (left, right))
            transport = RavelTransport(
                scores,
                (0.0, 1.0, 2.0),
                {"r"},
                (current,),
                conditional_hold=True,
            )
            for edge in transport.edges:
                if edge.kind != "proof":
                    continue
                assert universal_cut(
                    edge.root,
                    edge.node,
                    transport.chains,
                    set(scores),
                ) is math.isclose(
                    edge.utility,
                    1.0,
                    rel_tol=1e-12,
                    abs_tol=1e-12,
                )
                checked += 1
    assert checked > 0


def test_cut_index_matches_direct_route_scan():
    values = (
        chain("a", (("r", "x"), ("x",))),
        chain("b", (("r", "x", "y"), ("x", "y"))),
        chain("c", (("q", "y"), ("y",))),
    )
    scored = {"r", "q", "x", "y"}
    for root in scored:
        routes = tuple(
            value
            for value in values
            if any(
                root in group
                for group in groups(value, scored)[
                    :len(value.predicates)
                ]
            )
        )
        for node in scored:
            direct = bool(routes) and all(
                any(
                    group == {node}
                    for group in groups(value, scored)
                )
                for value in routes
            )
            assert universal_cut(
                root,
                node,
                values,
                scored,
            ) is direct


def test_certified_graph_recovers_cut_omitted_by_source_matching():
    chains = (
        chain("r1", (("r1", "x", "y"), ("x",))),
        chain("r2", (("r2", "x", "z"), ("x", "z"))),
    )
    edges = (
        TransportEdge("r1", "r1", 0.0, 3.0, 1, "local"),
        TransportEdge("r1", "x", 1.0, 2.0, 1, "proof"),
        TransportEdge("r1", "y", 0.9, 2.0, 1, "proof"),
        TransportEdge("r2", "r2", 0.0, 3.0, 1, "local"),
        TransportEdge("r2", "x", 0.9, 2.0, 1, "proof"),
    )
    source_values = (edges[2], edges[4])
    source = TransportSelection(
        mode="full",
        nodes=("y", "x"),
        ledger=1.8,
        candidates=5,
        budget=2,
        values=source_values,
        mass=1.0,
        expanded=2,
    )
    result = certify_graph(
        edges,
        {"r1", "r2"},
        chains,
        {"r1", "r2", "x", "y", "z"},
        source,
    )
    assert set(result.selection.nodes) == {"x", "r2"}
    assert result.candidate_transports == 3
    assert result.certified_candidates == 1
    assert result.source_transports == 2
    assert result.source_certified_transports == 0
    assert result.certified_transports == 1
    assert result.changed_from_source == 2
    assert result.certificate.optimal is True


def test_certified_graph_uses_evidence_only_after_cardinality():
    chains = (
        chain(
            "r1",
            (("r1", "x", "y"), ("x",), ("y",)),
        ),
    )
    edges = (
        TransportEdge("r1", "r1", 0.0, 100.0, 1, "local"),
        TransportEdge("r1", "x", 1.0, 1.0, 1, "proof"),
        TransportEdge("r1", "y", 1.0, 5.0, 1, "proof"),
        TransportEdge("r2", "r2", 0.0, 100.0, 0, "local"),
    )
    source = TransportSelection(
        mode="full",
        nodes=("r1", "r2"),
        ledger=0.0,
        candidates=4,
        budget=2,
        values=(edges[0], edges[3]),
        mass=1.0,
        expanded=0,
    )
    result = certify_graph(
        edges,
        {"r1", "r2"},
        chains,
        {"r1", "r2", "x", "y"},
        source,
    )
    assert set(result.selection.nodes) == {"y", "r2"}
    assert result.certified_transports == 1
    assert result.selected_e_value == 105.0
    assert result.maximum_e_value == 100.0
    assert math.isclose(result.secondary_objective, 1.05)


def test_certified_graph_preserves_source_before_evidence():
    chains = (
        chain(
            "r1",
            (("r1", "x", "y"), ("x",), ("y",)),
        ),
    )
    edges = (
        TransportEdge("r1", "r1", 0.0, 1.0, 1, "local"),
        TransportEdge("r1", "x", 1.0, 1.0, 1, "proof"),
        TransportEdge("r1", "y", 1.0, 100.0, 1, "proof"),
        TransportEdge("r2", "r2", 0.0, 1.0, 0, "local"),
    )
    source = TransportSelection(
        mode="full",
        nodes=("x", "r2"),
        ledger=1.0,
        candidates=4,
        budget=2,
        values=(edges[1], edges[3]),
        mass=1.0,
        expanded=1,
    )
    result = certify_graph(
        edges,
        {"r1", "r2"},
        chains,
        {"r1", "r2", "x", "y"},
        source,
    )
    assert set(result.selection.nodes) == {"x", "r2"}
    assert result.certified_transports == 1
    assert result.source_agreement == 2
    assert result.source_distance == 0


def test_lexicographic_transport_matches_tuple_oracle():
    roots = {"r1", "r2", "r3"}
    edges = tuple(
        TransportEdge(
            root=root,
            node=node,
            utility=0.0 if node == root else 1.0,
            e_value=float(
                1
                + index * 7
                + offset * 3
            ),
            routes=1,
            kind="local" if node == root else "proof",
        )
        for index, root in enumerate(sorted(roots))
        for offset, node in enumerate((root, "x", "y"))
    )
    source_values = tuple(
        next(
            edge
            for edge in edges
            if edge.root == root
            and edge.node == node
        )
        for root, node in (
            ("r1", "x"),
            ("r2", "r2"),
            ("r3", "y"),
        )
    )
    source = TransportSelection(
        mode="full",
        nodes=tuple(edge.node for edge in source_values),
        ledger=2.0,
        candidates=len(edges),
        budget=3,
        values=source_values,
        mass=1.0,
        expanded=2,
    )
    selected, maximum, _ = _lexicographic_transport(
        edges,
        roots,
        source,
    )
    source_map = {
        edge.root: edge.node
        for edge in source.values
    }
    options = {
        root: tuple(
            edge
            for edge in edges
            if edge.root == root
        )
        for root in roots
    }
    feasible = []
    for first in options["r1"]:
        for second in options["r2"]:
            for third in options["r3"]:
                values = (first, second, third)
                if len({edge.node for edge in values}) < 3:
                    continue
                feasible.append(
                    (
                        sum(edge.kind == "proof" for edge in values),
                        sum(
                            source_map[edge.root] == edge.node
                            for edge in values
                        ),
                        sum(edge.e_value for edge in values) / maximum,
                    )
                )
    observed = (
        sum(edge.kind == "proof" for edge in selected),
        sum(
            source_map[edge.root] == edge.node
            for edge in selected
        ),
        sum(edge.e_value for edge in selected) / maximum,
    )
    assert observed == max(feasible)
