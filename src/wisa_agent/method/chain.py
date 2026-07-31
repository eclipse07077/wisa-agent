from __future__ import annotations

import hashlib
from collections import defaultdict
from heapq import heappop, heappush
from statistics import mean
from typing import Callable

from .config import (
    CHAIN_WEIGHTS,
    EDGE_THRESHOLD,
    EDGE_WEIGHTS,
    MAX_CHAIN_LENGTH,
    MAX_OUTGOING_EDGES,
    MIN_CHAIN_LENGTH,
    MIN_CHAIN_STAGES,
)
from .model import Chain, ChainEdge, Predicate, Stage


STAGE_ORDER = {
    Stage.INGRESS: 0,
    Stage.TRUST_BREAK: 1,
    Stage.LIFECYCLE: 2,
    Stage.MISSION_EFFECT: 3,
    Stage.RESPONSE: 4,
}


class ChainBuilder:
    def __init__(
        self,
        edge_threshold: float = EDGE_THRESHOLD,
        max_length: int = MAX_CHAIN_LENGTH,
        time_window: float | None = None,
        min_length: int = MIN_CHAIN_LENGTH,
        min_stages: int = MIN_CHAIN_STAGES,
        terminal_stages: frozenset[Stage] | None = frozenset(
            {Stage.MISSION_EFFECT, Stage.RESPONSE}
        ),
    ):
        self.edge_threshold = edge_threshold
        self.max_length = max_length
        self.time_window = time_window
        self.min_length = min_length
        self.min_stages = min_stages
        self.terminal_stages = terminal_stages

    def build(
        self,
        predicates: list[Predicate],
        limit: int = 32,
        compatible: Callable[[Predicate, Predicate], bool] | None = None,
        context_score: Callable[[Predicate, Predicate], float | None] | None = None,
        diversity_penalty: float = 0.0,
    ) -> list[Chain]:
        ordered = sorted(
            predicates,
            key=lambda item: (
                float("inf") if item.timestamp is None else item.timestamp,
                STAGE_ORDER[item.stage],
                item.predicate_id,
            ),
        )
        outgoing: dict[str, list[tuple[Predicate, ChainEdge]]] = defaultdict(list)
        by_id = {predicate.predicate_id: predicate for predicate in ordered}
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                if compatible is not None and not compatible(left, right):
                    continue
                context = (
                    context_score(left, right)
                    if context_score is not None
                    else None
                )
                edge = self.edge(left, right, context)
                if edge is not None and edge.score >= self.edge_threshold:
                    outgoing[left.predicate_id].append((right, edge))
        for predicate_id in outgoing:
            outgoing[predicate_id] = sorted(
                outgoing[predicate_id],
                key=lambda item: (item[1].score, item[0].confidence),
                reverse=True,
            )[:MAX_OUTGOING_EDGES]

        starts = [
            predicate
            for predicate in ordered
            if predicate.stage in {Stage.INGRESS, Stage.TRUST_BREAK}
        ]
        if not starts:
            starts = ordered

        max_candidates = max(limit * 16, 128)
        max_expansions = max(limit * 128, 1024)
        chains: dict[tuple[str, ...], Chain] = {}
        frontier: list[
            tuple[
                float,
                int,
                tuple[Predicate, ...],
                tuple[ChainEdge, ...],
            ]
        ] = []
        serial = 0
        for start in starts:
            priority = 0.6 * start.confidence + 0.4 * start.severity
            heappush(
                frontier,
                (-priority, serial, (start,), ()),
            )
            serial += 1
        expansions = 0
        while (
            frontier
            and len(chains) < max_candidates
            and expansions < max_expansions
        ):
            _, _, path, edges = heappop(frontier)
            current = path[-1]
            used = {item.predicate_id for item in path}
            for next_predicate, edge in outgoing.get(
                current.predicate_id,
                (),
            ):
                if next_predicate.predicate_id in used:
                    continue
                next_path = (*path, by_id[next_predicate.predicate_id])
                next_edges = (*edges, edge)
                expansions += 1
                key = tuple(item.predicate_id for item in next_path)
                chain = self._chain(list(next_path), list(next_edges))
                if self._valid(chain):
                    chains[key] = chain
                if len(next_path) < self.max_length:
                    heappush(
                        frontier,
                        (-chain.score, serial, next_path, next_edges),
                    )
                    serial += 1
                if len(chains) >= max_candidates:
                    break
        ranked = sorted(
            chains.values(),
            key=lambda chain: (chain.score, len(chain.predicates), chain.chain_id),
            reverse=True,
        )
        if diversity_penalty > 0:
            return self._diverse(ranked, limit, diversity_penalty)
        return ranked[:limit]

    @classmethod
    def _diverse(
        cls,
        ranked: list[Chain],
        limit: int,
        penalty: float,
    ) -> list[Chain]:
        selected: list[Chain] = []
        remaining = list(ranked)
        footprints = {
            chain.chain_id: cls._footprint(chain) for chain in remaining
        }
        while remaining and len(selected) < limit:
            choice = max(
                remaining,
                key=lambda chain: (
                    chain.score
                    - penalty
                    * max(
                        (
                            cls._jaccard(
                                footprints[chain.chain_id],
                                footprints[item.chain_id],
                            )
                            for item in selected
                        ),
                        default=0.0,
                    ),
                    chain.score,
                    chain.chain_id,
                ),
            )
            selected.append(choice)
            remaining.remove(choice)
        return selected

    @staticmethod
    def _footprint(chain: Chain) -> frozenset[str]:
        values = set(chain.targets)
        for predicate in chain.predicates:
            values.update(
                str(value)
                for value in predicate.details.get("endpoints", ())
            )
        return frozenset(values)

    @staticmethod
    def _jaccard(
        left: frozenset[str],
        right: frozenset[str],
    ) -> float:
        union = left | right
        if not union:
            return 0.0
        return len(left & right) / len(union)

    def _valid(self, chain: Chain) -> bool:
        stages = {item.stage for item in chain.predicates}
        if len(chain.predicates) < self.min_length:
            return False
        if len(stages) < self.min_stages:
            return False
        if (
            self.terminal_stages is not None
            and chain.predicates[-1].stage not in self.terminal_stages
        ):
            return False
        return True

    def edge(
        self,
        left: Predicate,
        right: Predicate,
        context_score: float | None = None,
    ) -> ChainEdge | None:
        if left.predicate_id == right.predicate_id:
            return None
        if (
            left.timestamp is not None
            and right.timestamp is not None
            and right.timestamp < left.timestamp
        ):
            return None

        factors = {
            "time": self._time(left, right),
            "context": (
                context_score
                if context_score is not None
                else self._context(left, right)
            ),
            "stage": self._stage(left, right),
            "mission": self._mission(left, right),
        }
        available = {
            name: value for name, value in factors.items() if value is not None
        }
        if not available:
            return None
        total_weight = sum(EDGE_WEIGHTS[name] for name in available)
        score = sum(
            available[name] * EDGE_WEIGHTS[name] / total_weight
            for name in available
        )
        return ChainEdge(
            source_id=left.predicate_id,
            target_id=right.predicate_id,
            score=score,
            factors=tuple(
                (name, round(value, 6)) for name, value in available.items()
            ),
        )

    @staticmethod
    def _chain(predicates: list[Predicate], edges: list[ChainEdge]) -> Chain:
        edge_average = mean(edge.score for edge in edges)
        confidence_average = mean(item.confidence for item in predicates)
        severity_average = mean(item.severity for item in predicates)
        stage_count = len({item.stage for item in predicates})
        mission = float(
            any(
                item.stage == Stage.MISSION_EFFECT
                or item.mission_relevant is True
                for item in predicates
            )
        )
        score = (
            edge_average * CHAIN_WEIGHTS["edge"]
            + confidence_average * CHAIN_WEIGHTS["confidence"]
            + severity_average * CHAIN_WEIGHTS["severity"]
            + stage_count * CHAIN_WEIGHTS["stages"]
            + mission * CHAIN_WEIGHTS["mission"]
        )
        raw = "|".join(item.predicate_id for item in predicates).encode()
        chain_id = "chain-" + hashlib.sha1(raw).hexdigest()[:12]
        return Chain(
            chain_id=chain_id,
            predicates=tuple(predicates),
            edges=tuple(edges),
            score=min(max(score, 0.0), 1.0),
        )

    def _time(self, left: Predicate, right: Predicate) -> float | None:
        if left.timestamp is None or right.timestamp is None:
            return None
        delta = right.timestamp - left.timestamp
        if self.time_window is None:
            return 1.0 if delta == 0 else 1.0 / (1.0 + delta)
        if delta > self.time_window:
            return 0.0
        return 1.0 - delta / max(self.time_window, 1e-9)

    @staticmethod
    def _context(left: Predicate, right: Predicate) -> float | None:
        if not left.context or not right.context:
            return None
        union = left.context | right.context
        return len(left.context & right.context) / len(union)

    @staticmethod
    def _stage(left: Predicate, right: Predicate) -> float:
        delta = STAGE_ORDER[right.stage] - STAGE_ORDER[left.stage]
        if delta == 1:
            return 1.0
        if delta == 0:
            return 0.45
        if delta == 2:
            return 0.8
        if delta > 2:
            return 0.65
        return 0.0

    @staticmethod
    def _mission(left: Predicate, right: Predicate) -> float:
        if right.stage == Stage.MISSION_EFFECT:
            return 1.0
        if left.stage == Stage.MISSION_EFFECT:
            return 0.7
        if right.stage == Stage.RESPONSE:
            return 0.55
        if (
            left.stage in {Stage.INGRESS, Stage.TRUST_BREAK}
            and right.stage == Stage.LIFECYCLE
        ):
            return 0.35
        return 0.15
