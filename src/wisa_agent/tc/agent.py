from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from math import ceil

import numpy as np

from wisa_agent.method import AttackOrchestrator, Chain, ChainBuilder, Predicate, Stage


@dataclass(frozen=True)
class ProvenanceGraph:
    node_types: np.ndarray
    edges: np.ndarray
    edge_types: np.ndarray
    scores: np.ndarray
    evaluation_mask: np.ndarray


@dataclass(frozen=True)
class LayerModel:
    type_layers: dict[int, int]
    transition_probability: dict[tuple[int, int], float]
    transition_floor: float

    @classmethod
    def fit(
        cls,
        graphs: list[tuple[np.ndarray, np.ndarray]],
        max_layers: int = 5,
    ) -> "LayerModel":
        flow: Counter[int] = Counter()
        volume: Counter[int] = Counter()
        transitions: Counter[tuple[int, int]] = Counter()
        source_totals: Counter[int] = Counter()
        all_types: set[int] = set()
        for node_types, edges in graphs:
            all_types.update(int(value) for value in np.unique(node_types))
            for source, target in edges:
                source_type = int(node_types[source])
                target_type = int(node_types[target])
                flow[source_type] += 1
                flow[target_type] -= 1
                volume[source_type] += 1
                volume[target_type] += 1
                transitions[(source_type, target_type)] += 1
                source_totals[source_type] += 1
        ordered = sorted(
            all_types,
            key=lambda node_type: (
                flow[node_type] / max(volume[node_type], 1),
                flow[node_type],
                -node_type,
            ),
            reverse=True,
        )
        layer_count = min(max_layers, max(len(ordered), 1))
        type_layers = {
            node_type: min(index * layer_count // max(len(ordered), 1), layer_count - 1)
            for index, node_type in enumerate(ordered)
        }
        cardinality = max(len(all_types), 1)
        probabilities = {
            pair: (count + 1) / (source_totals[pair[0]] + cardinality)
            for pair, count in transitions.items()
        }
        floor = 1 / max(sum(source_totals.values()) + cardinality, 1)
        return cls(type_layers, probabilities, floor)

    def layer(self, node_type: int) -> int:
        return self.type_layers.get(int(node_type), 0)

    def surprise(self, source_type: int, target_type: int) -> float:
        probability = self.transition_probability.get(
            (int(source_type), int(target_type)),
            self.transition_floor,
        )
        floor = max(self.transition_floor, 1e-12)
        return min(
            max(np.log(max(probability, floor)) / np.log(floor), 0.0),
            1.0,
        )


@dataclass(frozen=True)
class AttackResult:
    base_scores: np.ndarray
    scores: np.ndarray
    chains: tuple[Chain, ...]
    chain_nodes: tuple[int, ...]
    predicates: tuple[Predicate, ...]
    layers: dict[int, int]


class ProvenanceAttackAgent:
    def __init__(
        self,
        layer_model: LayerModel,
        seed_fraction: float = 0.005,
        max_seeds: int = 2048,
        chain_limit: int = 48,
        balance_layers: bool = True,
    ):
        self.layer_model = layer_model
        self.seed_fraction = seed_fraction
        self.max_seeds = max_seeds
        self.chain_limit = chain_limit
        self.balance_layers = balance_layers
        self.orchestrator = AttackOrchestrator(
            ChainBuilder(edge_threshold=0.58, max_length=5, time_window=None)
        )

    def run(self, graph: ProvenanceGraph) -> AttackResult:
        base = np.asarray(graph.scores, dtype=float)
        mask_indices = np.flatnonzero(graph.evaluation_mask)
        candidate_count = min(
            self.max_seeds,
            max(32, ceil(len(mask_indices) * self.seed_fraction)),
        )
        seeds = self._select_seeds(graph, base, mask_indices, candidate_count)
        adjacency, edge_surprise, edge_context = self._adjacency(graph)
        reverse: dict[int, set[int]] = defaultdict(set)
        for source, targets in adjacency.items():
            for target in targets:
                reverse[target].add(source)
        expanded = set(seeds)
        for seed in tuple(seeds):
            candidates = {
                node: edge_surprise.get((seed, node), 0.0)
                for node in adjacency.get(seed, ())
            }
            candidates.update(
                {
                    node: edge_surprise.get((node, seed), 0.0)
                    for node in reverse.get(seed, ())
                }
            )
            neighbors = sorted(
                candidates,
                key=lambda node: (
                    base[node],
                    candidates[node],
                ),
                reverse=True,
            )[:2]
            expanded.update(neighbors)
        predicates = self._predicates(
            graph,
            expanded,
            adjacency,
            edge_surprise,
            edge_context,
        )
        connected = {
            (str(source), str(target))
            for source, targets in adjacency.items()
            for target in targets
            if source in expanded and target in expanded
        }
        chains = self.orchestrator.discover(
            predicates,
            limit=self.chain_limit,
            compatible=lambda left, right: (
                (left.target, right.target) in connected
                or (right.target, left.target) in connected
            ),
            context_score=lambda left, right: 1.0,
        )
        chain_bonus = np.zeros_like(base, dtype=float)
        for chain in chains:
            for predicate in chain.predicates:
                node_id = int(predicate.target)
                chain_bonus[node_id] = max(chain_bonus[node_id], chain.score)
        normalized = self._percentile(base, graph.evaluation_mask)
        scores = normalized.copy()
        positive = chain_bonus > 0
        scores[positive] += chain_bonus[positive] * 1e-6
        chain_nodes = tuple(
            sorted(
                {
                    int(predicate.target)
                    for chain in chains
                    for predicate in chain.predicates
                }
            )
        )
        return AttackResult(
            base_scores=base,
            scores=scores,
            chains=tuple(chains),
            chain_nodes=chain_nodes,
            predicates=tuple(predicates),
            layers=dict(self.layer_model.type_layers),
        )

    def _select_seeds(
        self,
        graph: ProvenanceGraph,
        scores: np.ndarray,
        candidates: np.ndarray,
        count: int,
    ) -> set[int]:
        ranked = candidates[
            np.argsort(scores[candidates], kind="stable")[::-1]
        ]
        if not self.balance_layers:
            return set(int(value) for value in ranked[:count])
        by_layer: dict[int, list[int]] = defaultdict(list)
        for node in ranked:
            layer = self.layer_model.layer(int(graph.node_types[node]))
            by_layer[layer].append(int(node))
        layers = sorted(by_layer)
        quota = max(count // max(len(layers), 1), 1)
        selected = [
            node
            for layer in layers
            for node in by_layer[layer][:quota]
        ]
        selected_set = set(selected)
        for node in ranked:
            value = int(node)
            if len(selected) >= count:
                break
            if value not in selected_set:
                selected.append(value)
                selected_set.add(value)
        return set(selected)

    def _predicates(
        self,
        graph: ProvenanceGraph,
        nodes: set[int],
        adjacency: dict[int, set[int]],
        edge_surprise: dict[tuple[int, int], float],
        edge_context: dict[tuple[int, int], str],
    ) -> list[Predicate]:
        confidence = self._percentile(graph.scores, graph.evaluation_mask)
        reverse: dict[int, set[int]] = defaultdict(set)
        for source, targets in adjacency.items():
            for target in targets:
                reverse[target].add(source)
        predicates = []
        max_layer = max(self.layer_model.type_layers.values(), default=0)
        for node in sorted(nodes):
            node_type = int(graph.node_types[node])
            layer = self.layer_model.layer(node_type)
            stage = self._stage(layer, max_layer)
            incident = [
                edge_surprise.get((node, target), 0.0)
                for target in adjacency.get(node, ())
            ] + [
                edge_surprise.get((source, node), 0.0)
                for source in reverse.get(node, ())
            ]
            surprise = max(incident, default=0.0)
            context = {f"layer:{layer}", f"type:{node_type}"}
            for target in adjacency.get(node, ()):
                if target in nodes:
                    context.add(f"edge:{node}:{target}")
                    context.add(edge_context[(node, target)])
            for source in reverse.get(node, ()):
                if source in nodes:
                    context.add(f"edge:{source}:{node}")
                    context.add(edge_context[(source, node)])
            predicate_id = f"node:{node}"
            predicates.append(
                Predicate(
                    predicate_id=predicate_id,
                    stage=stage,
                    target=str(node),
                    layer=f"latent-{layer}",
                    relation="rare_provenance_transition",
                    timestamp=None,
                    context=frozenset(context),
                    confidence=float(confidence[node]),
                    severity=float(0.75 * confidence[node] + 0.25 * surprise),
                    mission_relevant=None,
                    evidence_ids=(predicate_id,),
                    details={
                        "node_type": node_type,
                        "transition_surprise": surprise,
                    },
                )
            )
        return predicates

    def _adjacency(
        self,
        graph: ProvenanceGraph,
    ) -> tuple[
        dict[int, set[int]],
        dict[tuple[int, int], float],
        dict[tuple[int, int], str],
    ]:
        adjacency: dict[int, set[int]] = defaultdict(set)
        surprise: dict[tuple[int, int], float] = {}
        context: dict[tuple[int, int], str] = {}
        for (source, target), edge_type in zip(graph.edges, graph.edge_types):
            source = int(source)
            target = int(target)
            adjacency[source].add(target)
            source_type = int(graph.node_types[source])
            target_type = int(graph.node_types[target])
            value = self.layer_model.surprise(
                source_type,
                target_type,
            )
            surprise[(source, target)] = value
            context[(source, target)] = (
                f"transition:{source_type}:{int(edge_type)}:{target_type}"
            )
        return adjacency, surprise, context

    @staticmethod
    def _stage(layer: int, max_layer: int) -> Stage:
        if max_layer <= 0:
            return Stage.TRUST_BREAK
        ratio = layer / max_layer
        if ratio <= 0.20:
            return Stage.INGRESS
        if ratio <= 0.45:
            return Stage.TRUST_BREAK
        if ratio <= 0.75:
            return Stage.LIFECYCLE
        return Stage.MISSION_EFFECT

    @staticmethod
    def _percentile(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
        values = np.asarray(values, dtype=float)
        selected = np.asarray(values[mask], dtype=float)
        order = np.argsort(selected, kind="stable")
        sorted_values = selected[order]
        unique, first, counts = np.unique(
            sorted_values,
            return_index=True,
            return_counts=True,
        )
        average_rank = first + (counts - 1) / 2
        percent = average_rank / max(len(selected) - 1, 1)
        mapped = dict(zip(unique.tolist(), percent.tolist()))
        return np.array([mapped.get(float(value), 0.0) for value in values])
