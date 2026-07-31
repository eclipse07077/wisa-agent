from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from .chain import ChainBuilder
from .config import (
    ACTION_ATTRIBUTES,
    COVERAGE_UTILITY,
    DEVIATION_RISK_WEIGHTS,
    HIGH_RESPONSE_EVIDENCE,
    HONEYPOT_THRESHOLD,
    MIN_STRONG_EVIDENCE,
    MISSION_CRITICALITY,
    MISSION_UTILITY_BONUS,
    MONITOR_THRESHOLD,
    RULE_RISK_WEIGHTS,
    STRONG_RESPONSE_THRESHOLD,
)
from .model import Chain, Predicate, Stage


@dataclass(frozen=True)
class Finding:
    target: str
    risk: float
    action: str
    predicates: tuple[Predicate, ...]
    chains: tuple[Chain, ...]
    independent_layers: int
    reason: str


@dataclass(frozen=True)
class ActionOption:
    name: str
    mitigation: float
    information: float
    deception: float
    cost: float
    reversibility: float


@dataclass(frozen=True)
class DecisionContext:
    belief: float
    evidence: float
    criticality: float
    coverage_gap: float
    mission_effect: bool


@dataclass(frozen=True)
class RankedAction:
    name: str
    utility: float


class ResponsePlanner:
    def __init__(self):
        self.options = tuple(
            ActionOption(name, *values)
            for name, values in ACTION_ATTRIBUTES.items()
        )

    def rank(
        self,
        context: DecisionContext,
        available: frozenset[str] | None = None,
    ) -> list[RankedAction]:
        ranked = []
        for option in self.options:
            if available is not None and option.name not in available:
                continue
            if not self._admissible(option.name, context):
                continue
            uncertainty = 1.0 - context.evidence
            utility = (
                context.belief * option.mitigation * context.evidence
                + uncertainty * option.information
                + context.coverage_gap
                * option.deception
                * COVERAGE_UTILITY
                - option.cost
                * (0.4 + 0.6 * context.criticality)
                - uncertainty * (1.0 - option.reversibility)
            )
            if context.mission_effect:
                utility += MISSION_UTILITY_BONUS * option.mitigation
            ranked.append(RankedAction(option.name, utility))
        return sorted(
            ranked,
            key=lambda item: (item.utility, item.name),
            reverse=True,
        )

    @staticmethod
    def _admissible(name: str, context: DecisionContext) -> bool:
        if context.mission_effect and name in {
            "temporary_isolate",
            "block",
        }:
            return False
        if name in {"temporary_isolate", "restore", "block"} and (
            context.belief < HONEYPOT_THRESHOLD
            or context.evidence < MIN_STRONG_EVIDENCE
        ):
            return False
        if name in {"restore", "block"} and (
            context.belief < STRONG_RESPONSE_THRESHOLD
            or context.evidence < HIGH_RESPONSE_EVIDENCE
        ):
            return False
        return True


class DefenseOrchestrator:
    def __init__(
        self,
        chain_builder: ChainBuilder,
        use_chain: bool = True,
        use_honeypot: bool = True,
        use_guard: bool = True,
    ):
        self.chain_builder = chain_builder
        self.use_chain = use_chain
        self.use_honeypot = use_honeypot
        self.use_guard = use_guard

    def assess(
        self,
        predicates: list[Predicate],
        criticality: dict[str, float],
    ) -> list[Finding]:
        chains = self.chain_builder.build(predicates) if self.use_chain else []
        findings: list[Finding] = []
        for target in sorted({predicate.target for predicate in predicates}):
            target_predicates = tuple(
                predicate for predicate in predicates if predicate.target == target
            )
            target_chains = tuple(
                chain for chain in chains if target in chain.targets
            )
            confidence = max(item.confidence for item in target_predicates)
            severity = max(item.severity for item in target_predicates)
            correlation = self._correlation(target_predicates, target_chains)
            target_criticality = criticality.get(target, 0.4)
            anomaly = [
                float(item.details["adjusted_anomaly_magnitude"])
                for item in target_predicates
                if "adjusted_anomaly_magnitude" in item.details
            ]
            predefined_risk = (
                RULE_RISK_WEIGHTS["confidence"] * confidence
                + RULE_RISK_WEIGHTS["severity"] * severity
                + RULE_RISK_WEIGHTS["correlation"] * correlation
                + RULE_RISK_WEIGHTS["criticality"] * target_criticality
            )
            if anomaly:
                deviation_risk = (
                    DEVIATION_RISK_WEIGHTS["anomaly"] * max(anomaly)
                    + DEVIATION_RISK_WEIGHTS["correlation"] * correlation
                    + DEVIATION_RISK_WEIGHTS["criticality"]
                    * target_criticality
                )
                risk = max(predefined_risk, deviation_risk)
            else:
                risk = predefined_risk
            layers = len({predicate.layer for predicate in target_predicates})
            action = self._action(
                risk,
                target_predicates,
                layers,
                target_criticality,
            )
            findings.append(
                Finding(
                    target=target,
                    risk=min(max(risk, 0.0), 1.0),
                    action=action,
                    predicates=target_predicates,
                    chains=target_chains,
                    independent_layers=layers,
                    reason=self._reason(target_predicates, target_chains),
                )
            )
        return sorted(
            findings,
            key=lambda item: (item.risk, item.independent_layers, item.target),
            reverse=True,
        )

    @staticmethod
    def _correlation(
        predicates: tuple[Predicate, ...],
        chains: tuple[Chain, ...],
    ) -> float:
        if chains:
            chain_score = max(chain.score for chain in chains)
        else:
            chain_score = 0.0
        layer_score = min(len({item.layer for item in predicates}) / 2, 1.0)
        stage_score = min(len({item.stage for item in predicates}) / 3, 1.0)
        temporal_score = max(
            (
                float(item.details.get("temporal_correlation", 0.0))
                for item in predicates
            ),
            default=0.0,
        )
        return max(
            0.55 * chain_score + 0.25 * layer_score + 0.20 * stage_score,
            temporal_score,
        )

    def _action(
        self,
        risk: float,
        predicates: tuple[Predicate, ...],
        independent_layers: int,
        criticality: float,
    ) -> str:
        if risk < MONITOR_THRESHOLD:
            return "monitor"
        if risk < HONEYPOT_THRESHOLD:
            return "honeypot" if self.use_honeypot else "analyse"
        if risk < STRONG_RESPONSE_THRESHOLD:
            return "temporary_isolate"
        if self.use_guard:
            required_layers = 3 if criticality >= MISSION_CRITICALITY else 2
            if independent_layers < required_layers:
                return "temporary_isolate"
        if any(item.stage == Stage.MISSION_EFFECT for item in predicates):
            return "restore"
        return "block"

    @staticmethod
    def _reason(
        predicates: tuple[Predicate, ...],
        chains: tuple[Chain, ...],
    ) -> str:
        stages = ",".join(sorted({item.stage.value for item in predicates}))
        layers = ",".join(sorted({item.layer for item in predicates}))
        chain_score = max((chain.score for chain in chains), default=0.0)
        return f"stages={stages};layers={layers};chain={chain_score:.3f}"
