from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from wisa_agent.method import Chain
from wisa_agent.tc.ravel import (
    TransportEdge,
    TransportSelection,
)
from wisa_agent.tc.transport import (
    TransportCertificate,
    certify_transport,
    exact_transport,
)


@dataclass(frozen=True)
class CertResult:
    selection: TransportSelection
    certificate: TransportCertificate
    witnesses: tuple[CutWitness, ...]
    source_transports: int
    certified_transports: int
    reverted_transports: int


@dataclass(frozen=True)
class RouteWitness:
    chain_id: str
    clauses: tuple[int, ...]


@dataclass(frozen=True)
class CutWitness:
    root: str
    node: str
    routes: tuple[RouteWitness, ...]


@dataclass(frozen=True)
class GraphCertResult:
    selection: TransportSelection
    certificate: TransportCertificate
    witnesses: tuple[CutWitness, ...]
    candidate_transports: int
    certified_candidates: int
    source_transports: int
    source_certified_transports: int
    certified_transports: int
    changed_from_source: int
    selected_e_value: float
    maximum_e_value: float
    secondary_objective: float
    source_agreement: int
    source_distance: int


@dataclass(frozen=True)
class _CutIndexEntry:
    routes: tuple[tuple[Chain, tuple[frozenset[str], ...]], ...]
    nodes: frozenset[str]


def groups(
    chain: Chain,
    scored: set[str],
) -> tuple[frozenset[str], ...]:
    endpoints = tuple(
        frozenset(
            node
            for node in predicate.details["endpoints"]
            if node in scored
        )
        for predicate in chain.predicates
    )
    bridges = tuple(
        left & right
        for left, right in zip(endpoints, endpoints[1:])
    )
    return (*endpoints, *bridges)


def _cut_index(
    chains: Iterable[Chain],
    scored: set[str],
) -> dict[str, _CutIndexEntry]:
    route_map: dict[
        str,
        list[tuple[Chain, tuple[frozenset[str], ...]]],
    ] = {}
    node_map: dict[str, set[str]] = {}
    for chain in chains:
        grouped = groups(chain, scored)
        roots = set().union(
            *grouped[:len(chain.predicates)]
        )
        singletons = {
            next(iter(group))
            for group in grouped
            if len(group) == 1
        }
        for root in roots:
            route_map.setdefault(root, []).append(
                (chain, grouped)
            )
            if root not in node_map:
                node_map[root] = set(singletons)
            else:
                node_map[root].intersection_update(
                    singletons
                )
    return {
        root: _CutIndexEntry(
            routes=tuple(routes),
            nodes=frozenset(node_map[root]),
        )
        for root, routes in route_map.items()
    }


def _indexed_witness(
    root: str,
    node: str,
    entry: _CutIndexEntry,
) -> CutWitness | None:
    if node not in entry.nodes:
        return None
    return CutWitness(
        root=root,
        node=node,
        routes=tuple(
            RouteWitness(
                chain_id=chain.chain_id,
                clauses=tuple(
                    index
                    for index, group in enumerate(grouped)
                    if group == {node}
                ),
            )
            for chain, grouped in entry.routes
        ),
    )


def _lexicographic_transport(
    edges: Iterable[TransportEdge],
    roots: set[str],
    source: TransportSelection,
) -> tuple[tuple[TransportEdge, ...], float, float]:
    values = tuple(edges)
    if any(
        not math.isfinite(edge.e_value)
        or edge.e_value < 0.0
        for edge in values
    ):
        raise ValueError("transport e-value must be finite and nonnegative")
    maximum = max(
        (edge.e_value for edge in values),
        default=0.0,
    )
    source_map = {
        edge.root: edge.node
        for edge in source.values
    }
    if set(source_map) != roots:
        raise ValueError("source roots do not match transport roots")
    agreement_scale = len(roots) + 1.0
    primary_scale = agreement_scale ** 2
    ranked = tuple(
        TransportEdge(
            root=edge.root,
            node=edge.node,
            utility=(
                primary_scale
                if edge.kind == "proof"
                else 0.0
            )
            + (
                agreement_scale
                if source_map[edge.root] == edge.node
                else 0.0
            )
            + (
                edge.e_value / maximum
                if maximum > 0.0
                else 0.0
            ),
            e_value=edge.e_value,
            routes=edge.routes,
            kind=edge.kind,
        )
        for edge in values
    )
    selected_keys = {
        (edge.root, edge.node)
        for edge in exact_transport(ranked, roots)
    }
    selected = tuple(
        sorted(
            (
                edge
                for edge in values
                if (edge.root, edge.node) in selected_keys
            ),
            key=lambda edge: edge.root,
        )
    )
    secondary = (
        sum(edge.e_value for edge in selected) / maximum
        if maximum > 0.0
        else 0.0
    )
    return selected, maximum, secondary


def cut_witness(
    root: str,
    node: str,
    chains: Iterable[Chain],
    scored: set[str],
) -> CutWitness | None:
    entry = _cut_index(chains, scored).get(root)
    if entry is None:
        return None
    return _indexed_witness(root, node, entry)


def universal_cut(
    root: str,
    node: str,
    chains: Iterable[Chain],
    scored: set[str],
) -> bool:
    return cut_witness(root, node, chains, scored) is not None


def certify_selection(
    source: TransportSelection,
    chains: Iterable[Chain],
    scored: set[str],
) -> CertResult:
    chain_values = tuple(chains)
    values = []
    witnesses = []
    source_transports = 0
    certified_transports = 0
    for edge in source.values:
        if edge.kind == "proof":
            source_transports += 1
        witness = (
            cut_witness(
                edge.root,
                edge.node,
                chain_values,
                scored,
            )
            if edge.kind == "proof"
            else None
        )
        if (
            witness is not None
            and len(witness.routes) == edge.routes
        ):
            values.append(
                TransportEdge(
                    root=edge.root,
                    node=edge.node,
                    utility=1.0,
                    e_value=edge.e_value,
                    routes=edge.routes,
                    kind="proof",
                )
            )
            witnesses.append(witness)
            certified_transports += 1
        else:
            values.append(
                TransportEdge(
                    root=edge.root,
                    node=edge.root,
                    utility=0.0,
                    e_value=0.0,
                    routes=edge.routes,
                    kind="local",
                )
            )
    roots = tuple(edge.root for edge in values)
    selection = TransportSelection(
        mode="certified",
        nodes=tuple(edge.node for edge in values),
        ledger=float(certified_transports),
        candidates=source.candidates,
        budget=source.budget,
        values=tuple(values),
        mass=source.mass,
        expanded=certified_transports,
    )
    certificate = certify_transport(
        selection.values,
        roots,
        optimal=False,
    )
    if (
        certificate.root_degree_min != 1
        or certificate.root_degree_max != 1
        or certificate.node_degree_max > 1
        or certificate.budget != source.budget
        or len(set(selection.nodes)) != source.budget
    ):
        raise RuntimeError("certified transport certificate failed")
    return CertResult(
        selection=selection,
        certificate=certificate,
        witnesses=tuple(witnesses),
        source_transports=source_transports,
        certified_transports=certified_transports,
        reverted_transports=source_transports - certified_transports,
    )


def certify_graph(
    edges: Iterable[TransportEdge],
    roots: Iterable[str],
    chains: Iterable[Chain],
    scored: set[str],
    source: TransportSelection,
) -> GraphCertResult:
    edge_values = tuple(edges)
    root_values = set(roots)
    chain_values = tuple(chains)
    index = _cut_index(chain_values, scored)
    admitted = []
    witness_map = {}
    candidate_transports = 0
    for edge in edge_values:
        if edge.kind == "local":
            admitted.append(
                TransportEdge(
                    root=edge.root,
                    node=edge.node,
                    utility=0.0,
                    e_value=edge.e_value,
                    routes=edge.routes,
                    kind="local",
                )
            )
            continue
        if edge.kind != "proof":
            raise ValueError("unknown transport edge kind")
        candidate_transports += 1
        entry = index.get(edge.root)
        if (
            entry is None
            or edge.node not in entry.nodes
            or len(entry.routes) != edge.routes
        ):
            continue
        certified = TransportEdge(
            root=edge.root,
            node=edge.node,
            utility=1.0,
            e_value=edge.e_value,
            routes=edge.routes,
            kind="proof",
        )
        admitted.append(certified)
        witness_map[(edge.root, edge.node)] = entry
    selected, maximum_e_value, secondary_objective = (
        _lexicographic_transport(
            admitted,
            root_values,
            source,
        )
    )
    nodes = tuple(edge.node for edge in selected)
    certified_transports = sum(
        edge.kind == "proof"
        for edge in selected
    )
    selection = TransportSelection(
        mode="certified_graph",
        nodes=nodes,
        ledger=float(certified_transports),
        candidates=len({edge.node for edge in admitted}),
        budget=len(root_values),
        values=selected,
        mass=1.0 if root_values else 0.0,
        expanded=certified_transports,
    )
    certificate = certify_transport(
        selected,
        root_values,
        optimal=True,
    )
    if (
        certificate.root_degree_min != 1
        or certificate.root_degree_max != 1
        or certificate.node_degree_max > 1
        or certificate.budget != len(root_values)
        or len(set(selection.nodes)) != len(root_values)
    ):
        raise RuntimeError("certified graph certificate failed")
    source_map = {
        edge.root: edge
        for edge in source.values
    }
    selected_map = {
        edge.root: edge
        for edge in selected
    }
    if set(source_map) != root_values or set(selected_map) != root_values:
        raise ValueError("source and certified roots must match")
    witnesses = tuple(
        _indexed_witness(
            edge.root,
            edge.node,
            witness_map[(edge.root, edge.node)],
        )
        for edge in selected
        if edge.kind == "proof"
    )
    if any(witness is None for witness in witnesses):
        raise RuntimeError("indexed cut witness failed")
    source_proofs = tuple(
        edge
        for edge in source.values
        if edge.kind == "proof"
    )
    return GraphCertResult(
        selection=selection,
        certificate=certificate,
        witnesses=witnesses,
        candidate_transports=candidate_transports,
        certified_candidates=len(witness_map),
        source_transports=len(source_proofs),
        source_certified_transports=sum(
            (edge.root, edge.node) in witness_map
            for edge in source_proofs
        ),
        certified_transports=certified_transports,
        changed_from_source=sum(
            source_map[root].node != selected_map[root].node
            for root in root_values
        ),
        selected_e_value=sum(
            edge.e_value
            for edge in selected
        ),
        maximum_e_value=maximum_e_value,
        secondary_objective=secondary_objective,
        source_agreement=sum(
            source_map[root].node == selected_map[root].node
            for root in root_values
        ),
        source_distance=sum(
            source_map[root].node != selected_map[root].node
            for root in root_values
        ),
    )
