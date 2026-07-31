import itertools
import math
from collections import Counter
from itertools import product

from wisa_agent.method import Chain, ChainEdge, Predicate, Stage
from wisa_agent.tc.ravel import (
    RavelLedger,
    RavelTransport,
    TransportEdge,
    greedy_transport,
)


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


def test_unanchored_and_disconnected_chains_have_no_account():
    anchored = chain("a", ("root", "bridge"), ("bridge", "x"))
    unanchored = chain("u", ("y", "bridge"), ("bridge", "z"))
    disconnected = chain("d", ("root",), ("z",))
    ledger = RavelLedger(
        {
            "root": 4.0,
            "bridge": 3.0,
            "x": 2.0,
            "y": 2.0,
            "z": 1.0,
        },
        (0.0, 1.0, 2.0, 3.0),
        {"root"},
        (anchored, unanchored, disconnected),
    )
    assert tuple(item.chain_id for item in ledger.chains) == ("a",)
    assert ledger.candidates == {"root", "bridge", "x"}


def test_direct_deletion_equals_propagated_loss():
    item = chain("a", ("root", "bridge"), ("bridge", "x"))
    ledger = RavelLedger(
        {"root": 4.0, "bridge": 3.0, "x": 2.0},
        (0.0, 1.0, 2.0, 3.0),
        {"root"},
        (item,),
    )
    for mode in ("local", "chain", "full"):
        for node in ledger.candidates:
            expected = (
                ledger.direct_ledger(mode=mode)
                - ledger.direct_ledger(removed=node, mode=mode)
            )
            assert math.isclose(
                ledger.losses[mode][node],
                expected,
            )


def test_factorized_route_equals_explicit_realization_sum():
    item = chain(
        "a",
        ("root", "bridge", "x"),
        ("bridge", "x", "y"),
    )
    ledger = RavelLedger(
        {
            "root": 5.0,
            "bridge": 4.0,
            "x": 3.0,
            "y": 2.0,
        },
        (0.0, 1.0, 2.0, 3.0, 4.0),
        {"root"},
        (item,),
        conditioned=True,
    )
    groups = ledger._groups("root", item)[1:]
    count = len(groups)
    occurrences = Counter(
        node
        for group in groups
        for node in set(group)
        if node != "root"
    )
    total = sum(
        math.prod(
            (
                1.0
                if node == "root"
                else ledger.e_values[node]
                ** (1.0 / (count * occurrences[node]))
            )
            for node in realization
        )
        for realization in product(*groups)
    )
    explicit = (
        total
        / math.prod(len(group) for group in groups)
        * math.prod(edge.score for edge in item.edges) ** (1.0 / count)
    )
    assert math.isclose(
        ledger.route_values[("root", item.chain_id)],
        explicit,
    )


def test_explicit_fracture_extension_is_submodular():
    item = chain(
        "a",
        ("root", "bridge", "x"),
        ("bridge", "x", "y"),
    )
    ledger = RavelLedger(
        {
            "root": 5.0,
            "bridge": 4.0,
            "x": 3.0,
            "y": 2.0,
        },
        (0.0, 1.0, 2.0, 3.0, 4.0),
        {"root"},
        (item,),
        conditioned=True,
    )
    groups = ledger._groups("root", item)[1:]
    count = len(groups)
    occurrences = Counter(
        node
        for group in groups
        for node in set(group)
        if node != "root"
    )
    realizations = [
        (
            frozenset(nodes) - {"root"},
            math.prod(
                (
                    1.0
                    if node == "root"
                    else ledger.e_values[node]
                    ** (1.0 / (count * occurrences[node]))
                )
                for node in nodes
            ),
        )
        for nodes in product(*groups)
    ]
    total = sum(weight for _, weight in realizations)

    def fracture(removed):
        return sum(
            weight
            for support, weight in realizations
            if support & removed
        ) / total

    nodes = ("bridge", "x", "y")
    subsets = [
        frozenset(
            nodes[index]
            for index in range(len(nodes))
            if mask & (1 << index)
        )
        for mask in range(1 << len(nodes))
    ]
    assert math.isclose(fracture(frozenset()), 0.0)
    for left in subsets:
        for right in subsets:
            if not left <= right:
                continue
            for node in set(nodes) - right:
                assert (
                    fracture(left | {node}) - fracture(left)
                    >= fracture(right | {node}) - fracture(right)
                    - 1e-12
                )


def test_root_owns_every_route_in_its_account():
    item = chain("a", ("root", "bridge"), ("bridge", "x"))
    ledger = RavelLedger(
        {"root": 4.0, "bridge": 3.0, "x": 2.0},
        (0.0, 1.0, 2.0, 3.0),
        {"root"},
        (item,),
    )
    chain_value = ledger.select(mode="chain")
    full_value = ledger.select(mode="full")
    assert math.isclose(
        chain_value.values[0].responsibility,
        1.0,
    )
    assert math.isclose(
        full_value.values[0].responsibility,
        1.0,
    )


def test_bridge_is_more_necessary_than_leaf_alternative():
    item = chain(
        "a",
        ("root", "bridge"),
        ("bridge", "x", "y"),
    )
    ledger = RavelLedger(
        {
            "root": 5.0,
            "bridge": 4.0,
            "x": 3.0,
            "y": 2.0,
        },
        (0.0, 1.0, 2.0, 3.0, 4.0),
        {"root"},
        (item,),
    )
    assert (
        ledger.losses["chain"]["bridge"]
        > ledger.losses["chain"]["x"]
    )
    assert (
        ledger.losses["chain"]["bridge"]
        > ledger.losses["chain"]["y"]
    )


def test_local_mode_is_calibrated_seed_order():
    ledger = RavelLedger(
        {"a": 4.0, "b": 3.0, "c": 2.0},
        (0.0, 1.0, 2.0, 3.0),
        {"a", "b"},
        (),
    )
    selected = ledger.select(budget=1, mode="local")
    assert selected.nodes == ("a",)


def test_conditioned_root_is_gate_not_reused_evidence():
    item = chain("a", ("root", "bridge"), ("bridge", "x"))
    low = RavelLedger(
        {"root": 2.0, "bridge": 3.0, "x": 2.0},
        (0.0, 1.0, 2.0, 3.0),
        {"root"},
        (item,),
        conditioned=True,
    )
    high = RavelLedger(
        {"root": 100.0, "bridge": 3.0, "x": 2.0},
        (0.0, 1.0, 2.0, 3.0),
        {"root"},
        (item,),
        conditioned=True,
    )
    assert math.isclose(
        low.ledgers["full"],
        high.ledgers["full"],
    )
    assert math.isclose(
        low.ledgers["chain"],
        low.ledgers["full"],
    )
    assert low.losses["chain"] == low.losses["full"]


def test_conditioned_zero_loss_tie_uses_local_evidence():
    ledger = RavelLedger(
        {"a": 4.0, "b": 3.0, "c": 2.0},
        (0.0, 1.0, 2.0, 3.0),
        {"a", "b", "c"},
        (),
        conditioned=True,
    )
    selected = ledger.select(budget=2, mode="full")
    assert selected.nodes == ("a", "b")


def test_skipping_unused_losses_preserves_transport_inputs():
    item = chain("a", ("root", "bridge"), ("bridge", "x"))
    values = {"root": 4.0, "bridge": 3.0, "x": 2.0}
    calibration = (0.0, 1.0, 2.0, 3.0)
    full = RavelLedger(
        values,
        calibration,
        {"root"},
        (item,),
        conditioned=True,
    )
    skipped = RavelLedger(
        values,
        calibration,
        {"root"},
        (item,),
        conditioned=True,
        compute_losses=False,
        compute_memberships=False,
    )
    assert skipped.losses == {}
    assert skipped.memberships == {}
    assert skipped.ledgers == full.ledgers
    assert skipped.route_values == full.route_values
    assert skipped.accounts == full.accounts
    assert skipped.e_values == full.e_values


def test_conserved_accounts_form_unit_ledger():
    item = chain("a", ("root", "bridge"), ("bridge", "x"))
    ledger = RavelLedger(
        {
            "root": 4.0,
            "other": 3.5,
            "bridge": 3.0,
            "x": 2.0,
        },
        (0.0, 1.0, 2.0, 3.0),
        {"root", "other"},
        (item,),
        conditioned=True,
        conserved=True,
    )
    assert math.isclose(ledger.ledgers["full"], 1.0)
    root_floor = 1.0 / len(ledger.seeds)
    assert ledger.losses["full"]["root"] >= root_floor
    assert math.isclose(
        ledger.losses["full"]["other"],
        root_floor,
    )


def test_conserved_unanchored_chain_is_invariant():
    anchored = chain("a", ("root", "bridge"), ("bridge", "x"))
    unanchored = chain("u", ("y", "bridge"), ("bridge", "z"))
    values = {
        "root": 4.0,
        "bridge": 3.0,
        "x": 2.0,
        "y": 2.0,
        "z": 1.0,
    }
    first = RavelLedger(
        values,
        (0.0, 1.0, 2.0, 3.0),
        {"root"},
        (anchored,),
        conditioned=True,
        conserved=True,
    )
    second = RavelLedger(
        values,
        (0.0, 1.0, 2.0, 3.0),
        {"root"},
        (anchored, unanchored),
        conditioned=True,
        conserved=True,
    )
    assert first.candidates == second.candidates
    assert first.losses["full"] == second.losses["full"]


def test_transport_conserves_slots_and_replaces_a_root():
    chains = (
        chain(
            "a1",
            ("r1", "bridge"),
            ("bridge", "x1"),
        ),
        chain(
            "a2",
            ("r1", "bridge"),
            ("bridge", "x2"),
        ),
        chain(
            "b1",
            ("r2", "bridge"),
            ("bridge", "y1"),
        ),
        chain(
            "b2",
            ("r2", "bridge"),
            ("bridge", "y2"),
        ),
    )
    transport = RavelTransport(
        {
            "r1": 2.0,
            "r2": 1.5,
            "bridge": 5.0,
            "x1": 4.0,
            "x2": 3.5,
            "y1": 3.0,
            "y2": 2.5,
        },
        (0.0, 1.0, 2.0, 3.0, 4.0),
        {"r1", "r2"},
        chains,
    )
    selected = transport.select()
    assert transport.ledger.losses == {}
    assert transport.ledger.memberships == {}
    assert selected.budget == 2
    assert len(selected.nodes) == 2
    assert len(set(selected.nodes)) == 2
    assert {edge.root for edge in selected.values} == {"r1", "r2"}
    assert selected.mass == 1.0
    assert selected.expanded >= 1
    assert all(
        sum(value.node == edge.node for value in selected.values) == 1
        for edge in selected.values
    )


def test_transport_falls_back_to_reserved_singletons():
    transport = RavelTransport(
        {"r1": 2.0, "r2": 1.0},
        (0.0, 1.0, 2.0),
        {"r1", "r2"},
        (),
    )
    selected = transport.select()
    assert set(selected.nodes) == {"r1", "r2"}
    assert selected.expanded == 0


def test_conditional_transport_uses_proof_before_hold():
    item = chain(
        "a",
        ("root", "bridge"),
        ("bridge", "x"),
    )
    selected = RavelTransport(
        {"root": 3.0, "bridge": 2.0, "x": 1.0},
        (0.0, 1.0, 2.0, 3.0),
        {"root"},
        (item,),
        conditional_hold=True,
    ).select()
    assert selected.nodes != ("root",)
    assert selected.expanded == 1
    assert 0.0 < selected.values[0].utility <= 1.0


def test_singleton_bridge_has_complete_fracture_certificate():
    transport = RavelTransport(
        {"root": 3.0, "bridge": 2.0, "x": 1.0},
        (0.0, 1.0, 2.0, 3.0),
        {"root"},
        (chain("a", ("root", "bridge"), ("bridge", "x")),),
        conditional_hold=True,
    )
    utilities = {
        edge.node: edge.utility
        for edge in transport.edges
        if edge.kind == "proof"
    }
    assert math.isclose(utilities["bridge"], 1.0)
    assert 0.0 < utilities["x"] < 1.0


def test_transport_skips_routes_that_do_not_contain_candidate():
    routes = (
        chain("a", ("root", "left"), ("left", "x")),
        chain("b", ("root", "right"), ("right", "y")),
    )
    transport = RavelTransport(
        {
            "root": 5.0,
            "left": 4.0,
            "right": 3.0,
            "x": 2.0,
            "y": 1.0,
        },
        (0.0, 1.0, 2.0, 3.0, 4.0),
        {"root"},
        routes,
        conditional_hold=True,
    )
    expected = transport.edges
    original = transport.ledger._route_value
    calls = []

    def checked(seed, item, removed=None):
        members = {
            node
            for group in transport.ledger._groups(seed, item)
            for node in group
        }
        assert removed in members
        calls.append((item.chain_id, removed))
        return original(seed, item, removed)

    transport.ledger._route_value = checked
    assert transport._edges() == expected
    assert len(calls) == 4


def test_conditional_transport_is_own_root_score_invariant():
    item = chain(
        "a",
        ("root", "bridge"),
        ("bridge", "x"),
    )
    low = RavelTransport(
        {"root": 1.5, "bridge": 3.0, "x": 2.0},
        (0.0, 1.0, 2.0, 3.0),
        {"root"},
        (item,),
        conditional_hold=True,
    ).select()
    high = RavelTransport(
        {"root": 100.0, "bridge": 3.0, "x": 2.0},
        (0.0, 1.0, 2.0, 3.0),
        {"root"},
        (item,),
        conditional_hold=True,
    ).select()
    assert low.nodes == high.nodes
    assert math.isclose(low.ledger, high.ledger)


def test_cross_account_root_remains_provenance_evidence():
    item = chain(
        "a",
        ("r1", "r2"),
        ("r2", "x"),
    )
    low = RavelTransport(
        {"r1": 3.0, "r2": 1.0, "x": 2.0},
        (0.0, 1.0, 2.0, 3.0),
        {"r1", "r2"},
        (item,),
        conditional_hold=True,
    )
    high = RavelTransport(
        {"r1": 3.0, "r2": 100.0, "x": 2.0},
        (0.0, 1.0, 2.0, 3.0),
        {"r1", "r2"},
        (item,),
        conditional_hold=True,
    )
    low_utility = next(
        edge.utility
        for edge in low.edges
        if edge.root == "r1" and edge.node == "x"
    )
    high_utility = next(
        edge.utility
        for edge in high.edges
        if edge.root == "r1" and edge.node == "x"
    )
    assert not math.isclose(low_utility, high_utility)


def test_transport_is_invariant_to_strict_score_transform():
    item = chain(
        "a",
        ("root", "bridge"),
        ("bridge", "x"),
    )
    scores = {"root": 3.0, "bridge": 2.0, "x": 1.0}
    calibration = (0.0, 1.0, 2.0, 3.0)
    original = RavelTransport(
        scores,
        calibration,
        {"root"},
        (item,),
    ).select()
    transformed = RavelTransport(
        {
            node: math.exp(value)
            for node, value in scores.items()
        },
        tuple(math.exp(value) for value in calibration),
        {"root"},
        (item,),
    ).select()
    assert original.nodes == transformed.nodes
    assert math.isclose(original.ledger, transformed.ledger)


def test_greedy_transport_meets_half_optimum_on_small_graphs():
    roots = ("a", "b")
    nodes = ("x", "y")
    for weights in itertools.product((0.25, 0.5, 1.0), repeat=4):
        edges = tuple(
            TransportEdge(
                root=root,
                node=node,
                utility=weight,
                e_value=1.0,
                routes=1,
                kind="proof",
            )
            for (root, node), weight in zip(
                itertools.product(roots, nodes),
                weights,
            )
        )
        greedy = sum(
            edge.utility
            for edge in greedy_transport(edges, roots)
        )
        exact = max(
            sum(
                next(
                    edge.utility
                    for edge in edges
                    if edge.root == root and edge.node == node
                )
                for root, node in zip(roots, assignment)
            )
            for assignment in itertools.permutations(nodes)
        )
        assert greedy >= 0.5 * exact
