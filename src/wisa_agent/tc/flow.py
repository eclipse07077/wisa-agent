from __future__ import annotations

import heapq
import math
from bisect import bisect_right
from dataclasses import dataclass
from typing import Iterable

from wisa_agent.method import Chain


@dataclass(frozen=True)
class NodeValue:
    node: str
    anomaly: float
    responsibility: float
    flow: float
    causal: float
    chains: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class Selection:
    mode: str
    nodes: tuple[str, ...]
    gains: tuple[float, ...]
    objective: float
    candidates: int
    budget: int
    values: tuple[NodeValue, ...]


def empirical_percentiles(scores: dict[str, float]) -> dict[str, float]:
    ordered = sorted(scores.values())
    size = len(ordered)
    if size == 0:
        return {}
    return {
        node: bisect_right(ordered, score) / size
        for node, score in scores.items()
    }


def _endpoint_value(chain: Chain, index: int, node: str) -> float:
    predicate = chain.predicates[index]
    scores = dict(predicate.details.get("endpoint_scores", ()))
    value = float(scores.get(node, predicate.confidence))
    return min(max(value, 0.0), 1.0)


def _predicate_reliability(
    chain: Chain,
    index: int,
    removed: str | None = None,
) -> float:
    predicate = chain.predicates[index]
    endpoints = [
        node
        for node in predicate.details["endpoints"]
        if node != removed
    ]
    if not endpoints:
        return 0.0
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
    return 1.0 - complement


def chain_reliability(
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
    predicate_term = math.prod(
        _predicate_reliability(chain, index, removed)
        for index in range(len(chain.predicates))
    )
    edge_term = math.prod(edge.score for edge in chain.edges)
    return predicate_term * edge_term


def counterfactual_responsibility(chain: Chain) -> dict[str, float]:
    base = chain_reliability(chain)
    endpoints = {
        node
        for predicate in chain.predicates
        for node in predicate.details["endpoints"]
    }
    if base <= 0.0:
        return {node: 0.0 for node in endpoints}
    return {
        node: min(
            max(1.0 - chain_reliability(chain, node) / base, 0.0),
            1.0,
        )
        for node in endpoints
    }


def conserved_flow(chain: Chain) -> dict[str, float]:
    flow: dict[str, float] = {}
    total = sum(edge.score for edge in chain.edges)
    if total <= 0.0:
        return flow
    for index, edge in enumerate(chain.edges):
        left = set(chain.predicates[index].details["endpoints"])
        right = set(chain.predicates[index + 1].details["endpoints"])
        shared = left & right
        if not shared:
            continue
        weights = {
            node: math.sqrt(
                _endpoint_value(chain, index, node)
                * _endpoint_value(chain, index + 1, node)
            )
            for node in shared
        }
        denominator = sum(weights.values())
        if denominator <= 0.0:
            weights = {node: 1.0 for node in shared}
            denominator = len(shared)
        for node, weight in weights.items():
            flow[node] = (
                flow.get(node, 0.0)
                + edge.score * weight / denominator
            )
    return {
        node: value / total
        for node, value in flow.items()
    }


class FlowSelector:
    def __init__(
        self,
        official_scores: dict[str, float],
        seeds: set[str],
        chains: Iterable[Chain],
    ):
        self.official_scores = official_scores
        self.seeds = seeds
        self.chains = tuple(chains)
        self.percentiles = empirical_percentiles(official_scores)
        self.candidates = set(seeds)
        for chain in self.chains:
            self.candidates.update(
                node
                for predicate in chain.predicates
                for node in predicate.details["endpoints"]
                if node in official_scores
            )
        self.responsibility: dict[str, float] = {}
        self.flow: dict[str, float] = {}
        self.by_chain: dict[str, dict[str, tuple[float, float]]] = {}
        for chain in self.chains:
            responsibility = counterfactual_responsibility(chain)
            flow = conserved_flow(chain)
            values = {}
            for node in self.candidates:
                if node not in responsibility and node not in flow:
                    continue
                node_responsibility = responsibility.get(node, 0.0)
                node_flow = flow.get(node, 0.0)
                values[node] = (node_responsibility, node_flow)
                self.responsibility[node] = max(
                    self.responsibility.get(node, 0.0),
                    node_responsibility,
                )
                self.flow[node] = max(
                    self.flow.get(node, 0.0),
                    node_flow,
                )
            self.by_chain[chain.chain_id] = values

    def _utilities(self, mode: str) -> dict[str, dict[str, float]]:
        utilities = {}
        for chain in self.chains:
            chain_values = {}
            for node, (responsibility, flow) in self.by_chain[
                chain.chain_id
            ].items():
                anomaly = self.percentiles[node]
                if mode == "responsibility":
                    causal = responsibility
                elif mode == "flow":
                    causal = flow
                elif mode == "full":
                    causal = 1.0 - (
                        1.0 - responsibility
                    ) * (1.0 - flow)
                elif mode == "anomaly":
                    causal = 0.0
                else:
                    raise ValueError(mode)
                chain_values[node] = math.sqrt(anomaly * causal)
            utilities[chain.chain_id] = chain_values
        return utilities

    def objective(
        self,
        nodes: Iterable[str],
        budget: int | None = None,
        mode: str = "full",
    ) -> float:
        if budget is None:
            budget = len(self.seeds)
        budget = min(max(budget, 0), len(self.candidates))
        selected = set(nodes) & self.candidates
        utilities = self._utilities(mode)
        detector_denominator = sum(
            sorted(
                (
                    self.percentiles[node]
                    for node in self.candidates
                ),
                reverse=True,
            )[:budget]
        )
        detector = (
            sum(self.percentiles[node] for node in selected)
            / detector_denominator
            if detector_denominator
            else 0.0
        )
        active = []
        for chain in self.chains:
            total = sum(utilities[chain.chain_id].values())
            if total > 0.0:
                active.append((chain, total))
        weight_total = sum(chain.score for chain, _ in active)
        chain_value = 0.0
        for chain, total in active:
            covered = sum(
                utility
                for node, utility in utilities[chain.chain_id].items()
                if node in selected
            )
            chain_value += (
                chain.score
                / weight_total
                * (1.0 - math.exp(-covered))
                / (1.0 - math.exp(-total))
            )
        return detector + chain_value

    def select(
        self,
        budget: int | None = None,
        mode: str = "full",
        lazy: bool = True,
    ) -> Selection:
        if budget is None:
            budget = len(self.seeds)
        budget = min(max(budget, 0), len(self.candidates))
        utilities = self._utilities(mode)
        top_anomaly = sorted(
            (
                self.percentiles[node]
                for node in self.candidates
            ),
            reverse=True,
        )[:budget]
        detector_denominator = sum(top_anomaly)
        chain_total = {
            chain.chain_id: sum(
                utilities[chain.chain_id].values()
            )
            for chain in self.chains
        }
        active_chains = [
            chain
            for chain in self.chains
            if chain_total[chain.chain_id] > 0.0
        ]
        weight_total = sum(chain.score for chain in active_chains)
        chain_weights = {
            chain.chain_id: chain.score / weight_total
            for chain in active_chains
        } if weight_total else {}
        chain_denominators = {
            chain.chain_id: 1.0
            - math.exp(-chain_total[chain.chain_id])
            for chain in active_chains
        }
        current = {
            chain.chain_id: 0.0
            for chain in active_chains
        }
        memberships: dict[str, list[tuple[str, float]]] = {}
        for chain in active_chains:
            for node, utility in utilities[chain.chain_id].items():
                if utility > 0.0:
                    memberships.setdefault(node, []).append(
                        (chain.chain_id, utility)
                    )

        def marginal(node: str) -> float:
            value = (
                self.percentiles[node] / detector_denominator
                if detector_denominator
                else 0.0
            )
            for chain_id, utility in memberships.get(node, ()):
                before = 1.0 - math.exp(-current[chain_id])
                after = 1.0 - math.exp(
                    -(current[chain_id] + utility)
                )
                value += (
                    chain_weights[chain_id]
                    * (after - before)
                    / chain_denominators[chain_id]
                )
            return value

        remaining = set(self.candidates)
        selected = []
        gains = []
        objective = 0.0
        if lazy:
            rank = {
                node: index
                for index, node in enumerate(
                    sorted(remaining, reverse=True)
                )
            }
            current_gain = {
                node: marginal(node)
                for node in remaining
            }
            heap = [
                (-gain, rank[node], node)
                for node, gain in current_gain.items()
            ]
            heapq.heapify(heap)
            for _ in range(budget):
                while True:
                    negative, _, node = heapq.heappop(heap)
                    if (
                        node in remaining
                        and -negative == current_gain[node]
                    ):
                        break
                gain = current_gain[node]
                selected.append(node)
                gains.append(gain)
                objective += gain
                remaining.remove(node)
                changed = set()
                for chain_id, utility in memberships.get(node, ()):
                    current[chain_id] += utility
                    changed.add(chain_id)
                affected = {
                    candidate
                    for chain_id in changed
                    for candidate in utilities[chain_id]
                    if candidate in remaining
                }
                for candidate in affected:
                    value = marginal(candidate)
                    current_gain[candidate] = value
                    heapq.heappush(
                        heap,
                        (-value, rank[candidate], candidate),
                    )
        else:
            for _ in range(budget):
                node = max(
                    remaining,
                    key=lambda value: (
                        marginal(value),
                        value,
                    ),
                )
                gain = marginal(node)
                selected.append(node)
                gains.append(gain)
                objective += gain
                remaining.remove(node)
                for chain_id, utility in memberships.get(node, ()):
                    current[chain_id] += utility

        values = []
        for node in selected:
            chain_values = tuple(
                sorted(
                    (
                        chain_id,
                        utility,
                    )
                    for chain_id, utility in (
                        (
                            chain.chain_id,
                            utilities[chain.chain_id].get(node, 0.0),
                        )
                        for chain in self.chains
                    )
                    if utility > 0.0
                )
            )
            responsibility = self.responsibility.get(node, 0.0)
            flow = self.flow.get(node, 0.0)
            values.append(
                NodeValue(
                    node=node,
                    anomaly=self.percentiles[node],
                    responsibility=responsibility,
                    flow=flow,
                    causal=1.0
                    - (1.0 - responsibility) * (1.0 - flow),
                    chains=chain_values,
                )
            )
        return Selection(
            mode=mode,
            nodes=tuple(selected),
            gains=tuple(gains),
            objective=objective,
            candidates=len(self.candidates),
            budget=budget,
            values=tuple(values),
        )
