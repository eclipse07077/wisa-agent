from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from typing import Iterable

from wisa_agent.method import Chain
from wisa_agent.tc.ravel import (
    RavelTransport,
    TransportEdge,
    TransportSelection,
)


@dataclass
class _Arc:
    target: int
    reverse: int
    capacity: int
    cost: float


@dataclass(frozen=True)
class TransportCertificate:
    roots: int
    nodes: int
    budget: int
    root_degree_min: int
    root_degree_max: int
    node_degree_max: int
    mass: float
    objective: float
    optimal: bool


def _add_arc(
    graph: list[list[_Arc]],
    source: int,
    target: int,
    capacity: int,
    cost: float,
) -> int:
    forward = len(graph[source])
    reverse = len(graph[target])
    graph[source].append(_Arc(target, reverse, capacity, cost))
    graph[target].append(_Arc(source, forward, 0, -cost))
    return forward


def exact_transport(
    edges: Iterable[TransportEdge],
    roots: Iterable[str],
) -> tuple[TransportEdge, ...]:
    root_order = tuple(sorted(set(roots)))
    if not root_order:
        return ()
    root_set = set(root_order)
    edge_order = tuple(
        sorted(
            edges,
            key=lambda edge: (
                edge.root,
                edge.node,
                -edge.utility,
                -edge.e_value,
            ),
        )
    )
    pairs = set()
    coverage = set()
    for edge in edge_order:
        if edge.utility < 0.0:
            raise ValueError("transport utility must be nonnegative")
        if edge.root not in root_set:
            raise ValueError("transport edge has an unknown root")
        pair = (edge.root, edge.node)
        if pair in pairs:
            raise ValueError("transport edge is duplicated")
        pairs.add(pair)
        coverage.add(edge.root)
    if coverage != root_set:
        raise ValueError("transport graph does not cover every root")

    node_order = tuple(sorted({edge.node for edge in edge_order}))
    root_index = {
        root: index + 1
        for index, root in enumerate(root_order)
    }
    node_offset = 1 + len(root_order)
    node_index = {
        node: node_offset + index
        for index, node in enumerate(node_order)
    }
    source = 0
    sink = node_offset + len(node_order)
    graph = [[] for _ in range(sink + 1)]
    ceiling = max(edge.utility for edge in edge_order)

    for root in root_order:
        _add_arc(graph, source, root_index[root], 1, 0.0)
    for node in node_order:
        _add_arc(graph, node_index[node], sink, 1, 0.0)

    references = {}
    for edge in edge_order:
        index = _add_arc(
            graph,
            root_index[edge.root],
            node_index[edge.node],
            1,
            ceiling - edge.utility,
        )
        references[(edge.root, edge.node)] = (
            root_index[edge.root],
            index,
            edge,
        )

    potential = [0.0] * len(graph)
    for _ in root_order:
        distance = [math.inf] * len(graph)
        previous = [(-1, -1)] * len(graph)
        distance[source] = 0.0
        queue = [(0.0, source)]
        while queue:
            current, vertex = heapq.heappop(queue)
            if current > distance[vertex] + 1e-15:
                continue
            for index, arc in enumerate(graph[vertex]):
                if arc.capacity == 0:
                    continue
                reduced = (
                    arc.cost
                    + potential[vertex]
                    - potential[arc.target]
                )
                if -1e-12 < reduced < 0.0:
                    reduced = 0.0
                candidate = current + reduced
                if candidate + 1e-15 < distance[arc.target]:
                    distance[arc.target] = candidate
                    previous[arc.target] = (vertex, index)
                    heapq.heappush(
                        queue,
                        (candidate, arc.target),
                    )
        if not math.isfinite(distance[sink]):
            raise ValueError("transport graph has no full matching")
        for vertex, value in enumerate(distance):
            if math.isfinite(value):
                potential[vertex] += value
        vertex = sink
        while vertex != source:
            parent, index = previous[vertex]
            if parent < 0:
                raise RuntimeError("transport augmenting path is incomplete")
            arc = graph[parent][index]
            arc.capacity -= 1
            graph[vertex][arc.reverse].capacity += 1
            vertex = parent

    selected = [
        edge
        for root_index_value, arc_index, edge in references.values()
        if graph[root_index_value][arc_index].capacity == 0
    ]
    return tuple(
        sorted(
            selected,
            key=lambda edge: edge.root,
        )
    )


def certify_transport(
    selected: Iterable[TransportEdge],
    roots: Iterable[str],
    optimal: bool,
) -> TransportCertificate:
    values = tuple(selected)
    root_order = tuple(sorted(set(roots)))
    root_degrees = {
        root: sum(edge.root == root for edge in values)
        for root in root_order
    }
    node_degrees = {
        node: sum(edge.node == node for edge in values)
        for node in {edge.node for edge in values}
    }
    budget = len(root_order)
    return TransportCertificate(
        roots=budget,
        nodes=len(node_degrees),
        budget=len(values),
        root_degree_min=min(root_degrees.values(), default=0),
        root_degree_max=max(root_degrees.values(), default=0),
        node_degree_max=max(node_degrees.values(), default=0),
        mass=1.0 if budget and len(values) == budget else 0.0,
        objective=sum(edge.utility for edge in values),
        optimal=optimal,
    )


class ExactTransport:
    def __init__(
        self,
        official_scores: dict[str, float],
        calibration: Iterable[float],
        seeds: set[str],
        chains: Iterable[Chain],
    ):
        self.transport = RavelTransport(
            official_scores,
            calibration,
            seeds,
            chains,
            conditional_hold=True,
        )
        self.ledger = self.transport.ledger
        self.edges = self.transport.edges
        self.seeds = self.transport.seeds

    def select(
        self,
    ) -> tuple[TransportSelection, TransportCertificate]:
        values = exact_transport(self.edges, self.seeds)
        nodes = tuple(edge.node for edge in values)
        budget = len(self.seeds)
        selection = TransportSelection(
            mode="full",
            nodes=nodes,
            ledger=sum(edge.utility for edge in values),
            candidates=len(self.transport.candidates),
            budget=budget,
            values=values,
            mass=1.0 if budget else 0.0,
            expanded=sum(edge.kind == "proof" for edge in values),
        )
        certificate = certify_transport(
            values,
            self.seeds,
            optimal=True,
        )
        if (
            certificate.root_degree_min != 1
            or certificate.root_degree_max != 1
            or certificate.node_degree_max > 1
            or certificate.budget != budget
        ):
            raise RuntimeError("exact transport certificate failed")
        return selection, certificate
