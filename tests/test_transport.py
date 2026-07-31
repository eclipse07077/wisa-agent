import itertools
import math

from wisa_agent.method import Chain, ChainEdge, Predicate, Stage
from wisa_agent.tc.ravel import RavelTransport, TransportEdge
from wisa_agent.tc.transport import ExactTransport, exact_transport


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
        timestamp=0.0,
        context=frozenset(),
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


def test_exact_transport_matches_exhaustive_optimum():
    roots = ("a", "b", "c")
    nodes = ("x", "y", "z")
    for weights in itertools.product((0.0, 0.5, 1.0), repeat=6):
        pairs = (
            ("a", "x"),
            ("a", "y"),
            ("b", "x"),
            ("b", "z"),
            ("c", "y"),
            ("c", "z"),
        )
        proof = tuple(
            TransportEdge(
                root=root,
                node=node,
                utility=weight,
                e_value=1.0,
                routes=1,
                kind="proof",
            )
            for (root, node), weight in zip(pairs, weights)
        )
        holds = tuple(
            TransportEdge(
                root=root,
                node=root,
                utility=0.0,
                e_value=1.0,
                routes=0,
                kind="local",
            )
            for root in roots
        )
        edges = proof + holds
        selected = exact_transport(edges, roots)
        exact = sum(edge.utility for edge in selected)
        choices = {
            root: tuple(
                edge
                for edge in edges
                if edge.root == root
            )
            for root in roots
        }
        exhaustive = max(
            sum(edge.utility for edge in assignment)
            for assignment in itertools.product(
                *(choices[root] for root in roots)
            )
            if len({edge.node for edge in assignment}) == len(roots)
        )
        assert math.isclose(exact, exhaustive)
        assert len({edge.root for edge in selected}) == len(roots)
        assert len({edge.node for edge in selected}) == len(roots)


def test_exact_transport_improves_greedy_counterexample():
    roots = {"a", "b"}
    edges = (
        TransportEdge("a", "x", 1.0, 1.0, 1, "proof"),
        TransportEdge("a", "y", 0.9, 1.0, 1, "proof"),
        TransportEdge("b", "x", 0.9, 1.0, 1, "proof"),
        TransportEdge("a", "a", 0.0, 1.0, 0, "local"),
        TransportEdge("b", "b", 0.0, 1.0, 0, "local"),
    )
    selected = exact_transport(edges, roots)
    assert math.isclose(
        sum(edge.utility for edge in selected),
        1.8,
    )


def test_exact_transport_certificate_and_root_separated_invariance():
    chains = (
        chain("a", ("r1", "bridge"), ("bridge", "x")),
        chain("b", ("r2", "bridge"), ("bridge", "y")),
    )
    scores = {
        "r1": 3.0,
        "r2": 2.5,
        "bridge": 2.0,
        "x": 1.5,
        "y": 1.0,
    }
    calibration = (0.0, 1.0, 2.0, 3.0)
    selected, certificate = ExactTransport(
        scores,
        calibration,
        {"r1", "r2"},
        chains,
    ).select()
    transformed, transformed_certificate = ExactTransport(
        {
            **scores,
            "r1": 100.0,
            "r2": 99.0,
        },
        calibration,
        {"r1", "r2"},
        chains,
    ).select()
    assert selected.nodes == transformed.nodes
    assert math.isclose(
        selected.ledger,
        transformed.ledger,
    )
    assert certificate == transformed_certificate
    assert certificate.optimal is True
    assert certificate.root_degree_min == 1
    assert certificate.root_degree_max == 1
    assert certificate.node_degree_max == 1
    assert certificate.mass == 1.0


def test_exact_objective_never_below_greedy():
    chains = (
        chain("a", ("r1", "bridge"), ("bridge", "x")),
        chain("b", ("r2", "bridge"), ("bridge", "y")),
    )
    scores = {
        "r1": 3.0,
        "r2": 2.5,
        "bridge": 2.0,
        "x": 1.5,
        "y": 1.0,
    }
    calibration = (0.0, 1.0, 2.0, 3.0)
    greedy = RavelTransport(
        scores,
        calibration,
        {"r1", "r2"},
        chains,
        conditional_hold=True,
    ).select()
    exact, _ = ExactTransport(
        scores,
        calibration,
        {"r1", "r2"},
        chains,
    ).select()
    assert exact.ledger >= greedy.ledger
