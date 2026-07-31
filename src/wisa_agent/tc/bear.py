from __future__ import annotations

import math
from bisect import bisect_left
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from wisa_agent.method import Chain


@dataclass(frozen=True)
class BearNodeValue:
    node: str
    e_value: float
    local_loss: float
    chain_loss: float
    total_loss: float
    responsibility: float


@dataclass(frozen=True)
class BearSelection:
    mode: str
    nodes: tuple[str, ...]
    ledger: float
    candidates: int
    budget: int
    values: tuple[BearNodeValue, ...]


def conformal_e_values(
    scores: dict[str, float],
    calibration: Iterable[float],
    kappa: float = 0.5,
) -> dict[str, float]:
    if not 0.0 < kappa < 1.0:
        raise ValueError("kappa must lie in (0, 1)")
    ordered = sorted(float(value) for value in calibration)
    size = len(ordered)
    if size == 0:
        raise ValueError("calibration is empty")
    return {
        node: (1.0 - kappa)
        * (
            (1 + size - bisect_left(ordered, float(score)))
            / (size + 1)
        )
        ** (-kappa)
        for node, score in scores.items()
    }


class BearLedger:
    def __init__(
        self,
        official_scores: dict[str, float],
        calibration: Iterable[float],
        seeds: set[str],
        chains: Iterable[Chain],
        unit_growth: bool = False,
    ):
        self.official_scores = official_scores
        self.seeds = seeds
        self.chains = tuple(chains)
        self.unit_growth = unit_growth
        self.e_values = conformal_e_values(
            official_scores,
            calibration,
        )
        self.candidates = set(seeds)
        for chain in self.chains:
            self.candidates.update(
                node
                for predicate in chain.predicates
                for node in predicate.details["endpoints"]
                if node in official_scores
            )
        self.chain_endpoints = {
            chain.chain_id: tuple(
                tuple(
                    node
                    for node in predicate.details["endpoints"]
                    if node in self.candidates
                )
                for predicate in chain.predicates
            )
            for chain in self.chains
        }
        self.chain_occurrences = {
            chain.chain_id: Counter(
                node
                for endpoints in self.chain_endpoints[chain.chain_id]
                for node in set(endpoints)
            )
            for chain in self.chains
        }
        self.route_counts: dict[int, int] = {1: len(self.candidates)}
        for chain in self.chains:
            length = len(chain.predicates)
            self.route_counts[length] = (
                self.route_counts.get(length, 0) + 1
            )
        raw_length = {
            length: 2.0 ** (-length)
            for length in self.route_counts
        }
        normalizer = sum(raw_length.values())
        self.length_mass = {
            length: value / normalizer
            for length, value in raw_length.items()
        }
        self.route_prior = {
            length: self.length_mass[length] / count
            for length, count in self.route_counts.items()
        }
        self.local_prior = self.route_prior[1]
        self.chain_values = {
            chain.chain_id: self._chain_value(chain)
            for chain in self.chains
        }
        self.local_ledger = sum(
            self.local_prior * self.e_values[node]
            for node in self.candidates
        )
        self.chain_ledger = sum(
            self.route_prior[len(chain.predicates)]
            * self.chain_values[chain.chain_id]
            for chain in self.chains
        )
        self.ledger = self.local_ledger + self.chain_ledger
        self.local_loss = {
            node: self.local_prior * self.e_values[node]
            for node in self.candidates
        }
        self.chain_loss = {
            node: self._chain_intervention(node)
            for node in self.candidates
        }

    def _chain_value(
        self,
        chain: Chain,
        removed: str | None = None,
    ) -> float:
        factors = []
        length = len(chain.predicates)
        for endpoints in self.chain_endpoints[chain.chain_id]:
            if not endpoints:
                return 0.0
            occurrences = self.chain_occurrences[chain.chain_id]
            value = sum(
                self.e_values[node]
                ** (
                    1.0
                    / (
                        occurrences[node]
                        * (length if self.unit_growth else 1)
                    )
                )
                for node in endpoints
                if node != removed
            ) / len(endpoints)
            factors.append(value)
        edge_value = math.prod(
            edge.score
            for edge in chain.edges
        )
        if self.unit_growth:
            edge_value **= 1.0 / length
        return math.prod(factors) * edge_value

    def _chain_intervention(self, node: str) -> float:
        loss = 0.0
        for chain in self.chains:
            endpoints = self.chain_endpoints[chain.chain_id]
            if not any(node in group for group in endpoints):
                continue
            base = self.chain_values[chain.chain_id]
            retained = self._chain_value(chain, node)
            prior = self.route_prior[len(chain.predicates)]
            loss += prior * max(base - retained, 0.0)
        return loss

    def direct_ledger(
        self,
        removed: str | None = None,
        mode: str = "full",
    ) -> float:
        if mode not in {"local", "chain", "full"}:
            raise ValueError(mode)
        local = 0.0
        if mode in {"local", "full"}:
            local = sum(
                self.local_prior * self.e_values[node]
                for node in self.candidates
                if node != removed
            )
        chain_value = 0.0
        if mode in {"chain", "full"}:
            chain_value = sum(
                self.route_prior[len(chain.predicates)]
                * self._chain_value(chain, removed)
                for chain in self.chains
            )
        return local + chain_value

    def _loss(self, node: str, mode: str) -> float:
        if mode == "local":
            return self.local_loss[node]
        if mode == "chain":
            return self.chain_loss[node]
        if mode == "full":
            return self.local_loss[node] + self.chain_loss[node]
        raise ValueError(mode)

    def select(
        self,
        budget: int | None = None,
        mode: str = "full",
    ) -> BearSelection:
        if budget is None:
            budget = len(self.seeds)
        budget = min(max(budget, 0), len(self.candidates))
        ledger = self.direct_ledger(mode=mode)
        ordered = sorted(
            self.candidates,
            key=lambda node: (
                self._loss(node, mode),
                node,
            ),
            reverse=True,
        )
        selected = ordered[:budget]
        values = tuple(
            BearNodeValue(
                node=node,
                e_value=self.e_values[node],
                local_loss=self.local_loss[node],
                chain_loss=self.chain_loss[node],
                total_loss=(
                    self.local_loss[node] + self.chain_loss[node]
                ),
                responsibility=(
                    self._loss(node, mode) / ledger
                    if ledger > 0.0
                    else 0.0
                ),
            )
            for node in selected
        )
        return BearSelection(
            mode=mode,
            nodes=tuple(selected),
            ledger=ledger,
            candidates=len(self.candidates),
            budget=budget,
            values=values,
        )
