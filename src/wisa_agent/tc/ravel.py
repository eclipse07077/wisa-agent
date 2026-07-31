from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from wisa_agent.method import Chain
from wisa_agent.tc.bear import conformal_e_values


@dataclass(frozen=True)
class RavelNodeValue:
    node: str
    e_value: float
    loss: float
    responsibility: float
    accounts: int


@dataclass(frozen=True)
class RavelSelection:
    mode: str
    nodes: tuple[str, ...]
    ledger: float
    candidates: int
    budget: int
    values: tuple[RavelNodeValue, ...]


@dataclass(frozen=True)
class TransportEdge:
    root: str
    node: str
    utility: float
    e_value: float
    routes: int
    kind: str


@dataclass(frozen=True)
class TransportSelection:
    mode: str
    nodes: tuple[str, ...]
    ledger: float
    candidates: int
    budget: int
    values: tuple[TransportEdge, ...]
    mass: float
    expanded: int


def greedy_transport(
    edges: Iterable[TransportEdge],
    roots: Iterable[str],
) -> tuple[TransportEdge, ...]:
    roots = set(roots)
    ordered = sorted(
        edges,
        key=lambda edge: (
            edge.utility,
            edge.e_value,
            edge.root,
            edge.node,
        ),
        reverse=True,
    )
    assigned_roots = set()
    assigned_nodes = set()
    selected = []
    for edge in ordered:
        if edge.utility < 0.0:
            raise ValueError("transport utility must be nonnegative")
        if edge.root not in roots:
            raise ValueError("transport edge has an unknown root")
        if edge.root in assigned_roots or edge.node in assigned_nodes:
            continue
        assigned_roots.add(edge.root)
        assigned_nodes.add(edge.node)
        selected.append(edge)
    if assigned_roots != roots:
        raise ValueError("transport graph does not cover every root")
    return tuple(selected)


class RavelLedger:
    def __init__(
        self,
        official_scores: dict[str, float],
        calibration: Iterable[float],
        seeds: set[str],
        chains: Iterable[Chain],
        conditioned: bool = False,
        conserved: bool = False,
        compute_losses: bool = True,
        compute_memberships: bool = True,
    ):
        self.official_scores = official_scores
        self.seeds = set(seeds)
        self.conditioned = conditioned
        self.conserved = conserved
        self.e_values = conformal_e_values(
            official_scores,
            calibration,
        )
        self.chain_endpoints = {}
        self.chain_bridges = {}
        retained = []
        for chain in chains:
            endpoints = tuple(
                tuple(
                    node
                    for node in predicate.details["endpoints"]
                    if node in official_scores
                )
                for predicate in chain.predicates
            )
            bridges = tuple(
                tuple(sorted(set(left) & set(right)))
                for left, right in zip(endpoints, endpoints[1:])
            )
            members = {
                node
                for group in endpoints
                for node in group
            }
            if (
                not members & self.seeds
                or any(not group for group in endpoints)
                or any(not group for group in bridges)
            ):
                continue
            retained.append(chain)
            self.chain_endpoints[chain.chain_id] = endpoints
            self.chain_bridges[chain.chain_id] = bridges
        self.chains = tuple(retained)
        self.candidates = set(self.seeds)
        for groups in self.chain_endpoints.values():
            self.candidates.update(
                node
                for group in groups
                for node in group
            )
        self.accounts = {
            seed: tuple(
                chain
                for chain in self.chains
                if any(
                    seed in group
                    for group in self.chain_endpoints[chain.chain_id]
                )
            )
            for seed in self.seeds
        }
        self.active_seeds = {
            seed
            for seed, chains_for_seed in self.accounts.items()
            if chains_for_seed
        }
        self.route_values = {
            (seed, chain.chain_id): self._route_value(seed, chain)
            for seed, chains_for_seed in self.accounts.items()
            for chain in chains_for_seed
        }
        if compute_memberships:
            self.memberships = {
                node: sum(
                    1
                    for seed, chains_for_seed in self.accounts.items()
                    for chain in chains_for_seed
                    if any(
                        node in group
                        for group in self._groups(seed, chain)
                    )
                )
                for node in self.candidates
            }
        else:
            self.memberships = {}
        self.ledgers = {
            mode: self.direct_ledger(mode=mode)
            for mode in ("local", "chain")
        }
        self.ledgers["full"] = (
            self.ledgers["chain"]
            if self.conditioned and not self.conserved
            else self.direct_ledger(mode="full")
        )
        if compute_losses:
            computed_modes = (
                ("local", "chain")
                if self.conditioned and not self.conserved
                else ("local", "chain", "full")
            )
            self.losses = {
                mode: {
                    node: max(
                        self.ledgers[mode]
                        - self.direct_ledger(removed=node, mode=mode),
                        0.0,
                    )
                    for node in self.candidates
                }
                for mode in computed_modes
            }
            if self.conditioned and not self.conserved:
                self.losses["full"] = self.losses["chain"].copy()
        else:
            self.losses = {}

    def _groups(
        self,
        seed: str,
        chain: Chain,
    ) -> tuple[tuple[str, ...], ...]:
        return (
            (seed,),
            *self.chain_endpoints[chain.chain_id],
            *self.chain_bridges[chain.chain_id],
        )

    def _route_value(
        self,
        seed: str,
        chain: Chain,
        removed: str | None = None,
    ) -> float:
        groups = self._groups(seed, chain)
        length = len(groups) - (1 if self.conditioned else 0)
        occurrences = Counter(
            node
            for group in (
                groups[1:]
                if self.conditioned
                else groups
            )
            for node in set(group)
            if node != seed or not self.conditioned
        )
        factors = []
        for index, group in enumerate(groups):
            if self.conditioned and index == 0:
                if seed == removed:
                    return 0.0
                factors.append(1.0)
                continue
            value = sum(
                (
                    1.0
                    if self.conditioned and node == seed
                    else self.e_values[node]
                    ** (1.0 / (length * occurrences[node]))
                )
                for node in group
                if node != removed
            ) / len(group)
            if value <= 0.0:
                return 0.0
            factors.append(value)
        edge_value = math.prod(
            edge.score
            for edge in chain.edges
        )
        return math.prod(factors) * edge_value ** (1.0 / length)

    def _account_value(
        self,
        seed: str,
        removed: str | None,
        mode: str,
    ) -> float:
        chains = self.accounts[seed]
        local = self.e_values[seed] if seed != removed else 0.0
        routes = [
            self._route_value(seed, chain, removed)
            for chain in chains
        ]
        if mode == "local":
            return local
        if mode == "chain":
            return sum(routes) / len(routes) if routes else 0.0
        if mode == "full":
            if self.conditioned:
                return sum(routes) / len(routes) if routes else 0.0
            return (local + sum(routes)) / (1 + len(routes))
        raise ValueError(mode)

    def direct_ledger(
        self,
        removed: str | None = None,
        mode: str = "full",
    ) -> float:
        if not self.seeds:
            return 0.0
        if self.conserved and mode == "full":
            retained = 0.0
            for seed in self.seeds:
                routes = self.accounts[seed]
                base = 1.0 + sum(
                    self.route_values[(seed, chain.chain_id)]
                    for chain in routes
                )
                if seed == removed:
                    continue
                value = 1.0 + sum(
                    self._route_value(seed, chain, removed)
                    for chain in routes
                )
                retained += value / base
            return retained / len(self.seeds)
        account_seeds = (
            self.active_seeds
            if self.conditioned and mode != "local"
            else self.seeds
        )
        if not account_seeds:
            return 0.0
        return sum(
            self._account_value(seed, removed, mode)
            for seed in account_seeds
        ) / len(account_seeds)

    def select(
        self,
        budget: int | None = None,
        mode: str = "full",
    ) -> RavelSelection:
        if mode not in self.losses:
            raise ValueError(mode)
        if budget is None:
            budget = len(self.seeds)
        budget = min(max(budget, 0), len(self.candidates))
        ledger = self.ledgers[mode]
        ordered = sorted(
            self.candidates,
            key=lambda node: (
                self.losses[mode][node],
                self.e_values[node],
                node,
            ),
            reverse=True,
        )
        selected = ordered[:budget]
        values = tuple(
            RavelNodeValue(
                node=node,
                e_value=self.e_values[node],
                loss=self.losses[mode][node],
                responsibility=(
                    self.losses[mode][node] / ledger
                    if ledger > 0.0
                    else 0.0
                ),
                accounts=self.memberships[node],
            )
            for node in selected
        )
        return RavelSelection(
            mode=mode,
            nodes=tuple(selected),
            ledger=ledger,
            candidates=len(self.candidates),
            budget=budget,
            values=values,
        )


class RavelTransport:
    def __init__(
        self,
        official_scores: dict[str, float],
        calibration: Iterable[float],
        seeds: set[str],
        chains: Iterable[Chain],
        conditional_hold: bool = False,
    ):
        self.ledger = RavelLedger(
            official_scores,
            calibration,
            seeds,
            chains,
            conditioned=True,
            compute_losses=False,
            compute_memberships=False,
        )
        self.official_scores = self.ledger.official_scores
        self.e_values = self.ledger.e_values
        self.seeds = self.ledger.seeds
        self.chains = self.ledger.chains
        self.accounts = self.ledger.accounts
        self.candidates = self.ledger.candidates
        self.conditional_hold = conditional_hold
        self.edges = self._edges()

    def _edges(self) -> tuple[TransportEdge, ...]:
        edges = []
        for seed in sorted(self.seeds):
            routes = self.accounts[seed]
            route_nodes = {
                chain.chain_id: {
                    node
                    for group in self.ledger._groups(seed, chain)
                    for node in group
                }
                for chain in routes
            }
            denominator = 1 + len(routes)
            route_total = sum(
                self.ledger.route_values[(seed, chain.chain_id)]
                for chain in routes
            )
            edges.append(
                TransportEdge(
                    root=seed,
                    node=seed,
                    utility=(
                        0.0
                        if self.conditional_hold
                        else self.e_values[seed] / denominator
                    ),
                    e_value=self.e_values[seed],
                    routes=len(routes),
                    kind="local",
                )
            )
            candidates = {
                node
                for chain in routes
                for group in self.ledger._groups(seed, chain)
                for node in group
                if node not in self.seeds
            }
            for node in sorted(candidates):
                loss = sum(
                    max(
                        self.ledger.route_values[
                            (seed, chain.chain_id)
                        ]
                        - self.ledger._route_value(
                            seed,
                            chain,
                            node,
                        ),
                        0.0,
                    )
                    for chain in routes
                    if node in route_nodes[chain.chain_id]
                )
                utility = (
                    loss / route_total
                    if self.conditional_hold and route_total > 0.0
                    else loss / denominator
                )
                if utility <= 0.0:
                    continue
                edges.append(
                    TransportEdge(
                        root=seed,
                        node=node,
                        utility=utility,
                        e_value=self.e_values[node],
                        routes=len(routes),
                        kind="proof",
                    )
                )
        return tuple(edges)

    def select(self) -> TransportSelection:
        selected = greedy_transport(self.edges, self.seeds)
        nodes = tuple(edge.node for edge in selected)
        budget = len(self.seeds)
        return TransportSelection(
            mode="full",
            nodes=nodes,
            ledger=sum(edge.utility for edge in selected),
            candidates=len(self.candidates),
            budget=budget,
            values=selected,
            mass=1.0 if budget else 0.0,
            expanded=sum(edge.kind == "proof" for edge in selected),
        )
