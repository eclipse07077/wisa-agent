from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class Stage(str, Enum):
    INGRESS = "ingress"
    TRUST_BREAK = "trust_break"
    LIFECYCLE = "lifecycle"
    MISSION_EFFECT = "mission_effect"
    RESPONSE = "response"


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    timestamp: float | None
    layer: str
    source: str
    subject: str
    relation: str
    object: str
    context: frozenset[str] = frozenset()
    confidence: float = 0.0
    provenance: str = "unknown"
    details: Mapping[str, Any] = field(default_factory=dict, compare=False)


@dataclass(frozen=True)
class Predicate:
    predicate_id: str
    stage: Stage
    target: str
    layer: str
    relation: str
    timestamp: float | None
    context: frozenset[str]
    confidence: float
    severity: float
    mission_relevant: bool | None
    evidence_ids: tuple[str, ...]
    details: Mapping[str, Any] = field(default_factory=dict, compare=False)


@dataclass(frozen=True)
class ChainEdge:
    source_id: str
    target_id: str
    score: float
    factors: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class Chain:
    chain_id: str
    predicates: tuple[Predicate, ...]
    edges: tuple[ChainEdge, ...]
    score: float

    @property
    def targets(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(predicate.target for predicate in self.predicates))

    @property
    def layers(self) -> frozenset[str]:
        return frozenset(predicate.layer for predicate in self.predicates)

    @property
    def stages(self) -> frozenset[Stage]:
        return frozenset(predicate.stage for predicate in self.predicates)
