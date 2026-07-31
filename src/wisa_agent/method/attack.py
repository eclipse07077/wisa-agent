from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Callable

from .chain import ChainBuilder
from .model import Chain, Predicate, Stage


@dataclass(frozen=True)
class ExperimentPlan:
    group: str
    concepts: tuple[str, ...]
    chain_ids: tuple[str, ...]
    priority: float


class AttackOrchestrator:
    def __init__(self, chain_builder: ChainBuilder):
        self.chain_builder = chain_builder

    def discover(
        self,
        predicates: list[Predicate],
        limit: int = 32,
        compatible: Callable[[Predicate, Predicate], bool] | None = None,
        context_score: Callable[[Predicate, Predicate], float | None] | None = None,
        diversity_penalty: float = 0.0,
    ) -> list[Chain]:
        return self.chain_builder.build(
            predicates,
            limit,
            compatible,
            context_score,
            diversity_penalty,
        )

    def plan(self, chains: list[Chain]) -> list[ExperimentPlan]:
        concepts = sorted(
            {
                predicate.relation
                for chain in chains
                for predicate in chain.predicates
            }
        )
        chain_ids = tuple(chain.chain_id for chain in chains[:8])
        plans = [
            ExperimentPlan("baseline", (), chain_ids, 1.0),
            ExperimentPlan("negative", ("unrelated",), chain_ids, 0.95),
        ]
        plans.extend(
            ExperimentPlan("single", (concept,), chain_ids, 0.80)
            for concept in concepts
        )
        plans.extend(
            ExperimentPlan("pairwise", pair, chain_ids, 0.85)
            for pair in combinations(concepts, 2)
        )
        if concepts:
            plans.append(
                ExperimentPlan("combined", tuple(concepts[:5]), chain_ids, 0.90)
            )
        high_risk = tuple(
            dict.fromkeys(
                predicate.relation
                for chain in chains
                for predicate in chain.predicates
                if predicate.stage in {Stage.TRUST_BREAK, Stage.MISSION_EFFECT}
            )
        )
        if high_risk:
            plans.append(
                ExperimentPlan("high_risk", high_risk[:3], chain_ids, 1.0)
            )
        return sorted(plans, key=lambda item: (item.priority, item.group), reverse=True)

    @staticmethod
    def validate(
        plan: ExperimentPlan,
        available_relations: set[str],
    ) -> tuple[bool, tuple[str, ...]]:
        violations = tuple(
            concept
            for concept in plan.concepts
            if concept != "unrelated" and concept not in available_relations
        )
        return not violations, violations
