from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from typing import Iterable

import numpy as np
from CybORG.Agents import BaseAgent

from wisa_agent.method import (
    ChainBuilder,
    DecisionContext,
    DefenseOrchestrator,
    Predicate,
    ResponsePlanner,
    Stage,
)
from wisa_agent.method.config import (
    BELIEF_DECAY,
    EDGE_THRESHOLD,
    HONEYPOT_THRESHOLD,
    MAX_CHAIN_LENGTH,
    MISSION_CRITICALITY,
    STRONG_RESPONSE_THRESHOLD,
    TRACE_WINDOW,
)

from .blue import ACTION_DURATIONS, ActionCatalog
from .core import LayeredObservation, ObservationDecoder, SegmentSpec


STAGE_CODE = {
    Stage.INGRESS: 1,
    Stage.TRUST_BREAK: 2,
    Stage.LIFECYCLE: 3,
    Stage.MISSION_EFFECT: 4,
    Stage.RESPONSE: 5,
}
CODE_STAGE = {value: key for key, value in STAGE_CODE.items()}


@dataclass
class PendingAction:
    command: str
    target: str
    due_step: int


@dataclass
class EffectWatch:
    command: str
    target: str
    expires_step: int


def encode_report_message(
    stage: Stage | None,
    risk: float,
    independent_layers: int,
) -> np.ndarray:
    bits = np.zeros(8, dtype=bool)
    if stage is None:
        return bits
    band = (
        1
        if risk < HONEYPOT_THRESHOLD
        else 2
        if risk < STRONG_RESPONSE_THRESHOLD
        else 3
    )
    code = STAGE_CODE[stage]
    bits[0] = bool(band & 0b10)
    bits[1] = bool(band & 0b01)
    for offset in range(4):
        bits[2 + offset] = bool(code & (1 << (3 - offset)))
    bits[6] = independent_layers >= 2
    bits[7] = True
    return bits


class ReportBlueAgent(BaseAgent):
    def __init__(
        self,
        name: str | None = None,
        use_chain: bool = True,
        use_honeypot: bool = True,
        use_guard: bool = True,
        use_transition_honeypot: bool = False,
        require_fresh_analysis: bool = False,
        corroborated_response: bool = False,
        event_aware_verification: bool = False,
        method_v11: bool = False,
        proactive_deception: bool = False,
    ):
        super().__init__(name)
        self.catalog = ActionCatalog()
        self.decoder: ObservationDecoder | None = None
        self.orchestrator = DefenseOrchestrator(
            ChainBuilder(
                edge_threshold=EDGE_THRESHOLD,
                max_length=MAX_CHAIN_LENGTH,
                time_window=TRACE_WINDOW,
            ),
            use_chain=use_chain,
            use_honeypot=use_honeypot,
            use_guard=use_guard,
        )
        self.use_transition_honeypot = use_transition_honeypot
        self.require_fresh_analysis = require_fresh_analysis
        self.corroborated_response = corroborated_response
        self.event_aware_verification = event_aware_verification
        self.method_v11 = method_v11
        self.proactive_deception = proactive_deception
        self.planner = ResponsePlanner()
        self.history: deque[Predicate] = deque(maxlen=72)
        self.beliefs: dict[str, float] = {}
        self.streaks: dict[tuple[str, str], int] = {}
        self.step = 0
        self.cooldown = 0
        self.message = np.zeros(8, dtype=bool)
        self.decoyed_hosts: set[str] = set()
        self.decoy_contacts: set[str] = set()
        self.active_hostiles: set[str] = set()
        self.transition_counts: Counter[tuple[str, str]] = Counter()
        self.predicted_decoys = 0
        self.pending: PendingAction | None = None
        self.effect_watches: dict[str, EffectWatch] = {}
        self.failed_effects: Counter[str] = Counter()
        self.remediations: Counter[str] = Counter()
        self.analysis_steps: dict[str, int] = {}
        self.analysis_confirmations = 0
        self.action_counts: Counter[str] = Counter()
        self.decision_counts: Counter[str] = Counter()
        self.utility_decisions: Counter[str] = Counter()
        self.last_action_label = ""
        self.verified_effects = 0
        self.unverified_effects = 0
        self.chain_ids: set[str] = set()

    def configure(
        self,
        segments: Iterable[SegmentSpec],
        labels: Iterable[str],
        mask: Iterable[bool],
    ) -> None:
        specs = tuple(segments)
        if self.decoder is None or self.decoder.segments != specs:
            self.decoder = ObservationDecoder(specs)
        self.catalog.update(labels, mask)

    def reset_episode(self) -> None:
        self.history.clear()
        self.beliefs.clear()
        self.streaks.clear()
        self.step = 0
        self.cooldown = 0
        self.message = np.zeros(8, dtype=bool)
        self.decoyed_hosts.clear()
        self.decoy_contacts.clear()
        self.active_hostiles.clear()
        self.transition_counts.clear()
        self.predicted_decoys = 0
        self.pending = None
        self.effect_watches.clear()
        self.failed_effects.clear()
        self.remediations.clear()
        self.analysis_steps.clear()
        self.analysis_confirmations = 0
        self.action_counts.clear()
        self.decision_counts.clear()
        self.utility_decisions.clear()
        self.last_action_label = ""
        self.verified_effects = 0
        self.unverified_effects = 0
        self.chain_ids.clear()

    def get_action(self, observation: np.ndarray, action_space) -> int:
        if self.decoder is None:
            return action_space.n - 1
        layered = self.decoder.decode(observation)
        self._verify(layered)
        predicates = self._predicates(layered)
        self.history.extend(predicates)
        recent = [
            predicate
            for predicate in self.history
            if predicate.timestamp is None
            or predicate.timestamp >= self.step - 18
        ]
        criticality = self._criticality(layered)
        findings = self.orchestrator.assess(recent, criticality)
        self._update_beliefs(findings)
        current_targets = {
            predicate.target
            for predicate in predicates
            if not predicate.target.startswith("peer:")
        }
        finding = next(
            (item for item in findings if item.target in current_targets),
            None,
        )
        if finding is None:
            self.message = np.zeros(8, dtype=bool)
        else:
            stage = max(
                (predicate.stage for predicate in finding.predicates),
                key=lambda value: STAGE_CODE[value],
            )
            self.message = encode_report_message(
                stage,
                finding.risk,
                finding.independent_layers,
            )
            self.decision_counts[finding.action] += 1
            self.chain_ids.update(chain.chain_id for chain in finding.chains)
        self.step += 1

        if self.cooldown > 0:
            self.cooldown -= 1
            return self._sleep()

        policy = self._policy_action(layered)
        if policy is not None:
            return self._commit(policy)
        response = self._respond(finding, layered)
        if response is not None:
            return response
        if self.method_v11 or self.proactive_deception:
            proactive = self._proactive_deception(layered)
            if proactive is not None:
                return proactive
        monitor = self.catalog.find("Monitor")
        if monitor is not None:
            return self._commit(monitor)
        return self._select("Sleep")

    def metrics(self) -> dict[str, object]:
        return {
            "decoyed_hosts": len(self.decoyed_hosts),
            "decoy_contacts": len(self.decoy_contacts),
            "learned_transitions": len(self.transition_counts),
            "predicted_decoys": self.predicted_decoys,
            "verified_effects": self.verified_effects,
            "unverified_effects": self.unverified_effects,
            "chains_formed": len(self.chain_ids),
            "decisions": dict(sorted(self.decision_counts.items())),
            "utility_decisions": dict(
                sorted(self.utility_decisions.items())
            ),
            "active_beliefs": len(self.beliefs),
            "failed_effects": dict(sorted(self.failed_effects.items())),
            "remediated_hosts": len(self.remediations),
            "analysis_confirmations": self.analysis_confirmations,
            "active_effect_watches": len(self.effect_watches),
        }

    def _predicates(self, layered: LayeredObservation) -> list[Predicate]:
        predicates: list[Predicate] = []
        active_keys: set[tuple[str, str]] = set()
        current_hostiles: set[str] = set()
        criticality = self._criticality(layered)
        for segment in layered.segments:
            for signal in segment.signals:
                context = frozenset({signal.subnet, signal.hostname})
                if signal.connection:
                    current_hostiles.add(signal.hostname)
                    active_keys.add((signal.hostname, "connection"))
                    streak = self._advance(signal.hostname, "connection")
                    predicates.append(
                        self._predicate(
                            signal.hostname,
                            "network",
                            "unexpected_connection",
                            Stage.INGRESS,
                            0.68,
                            min(0.55 + streak * 0.08, 0.90),
                            context | {Stage.INGRESS.value},
                        )
                    )
                if signal.process:
                    current_hostiles.add(signal.hostname)
                    active_keys.add((signal.hostname, "process"))
                    streak = self._advance(signal.hostname, "process")
                    predicates.append(
                        self._predicate(
                            signal.hostname,
                            "process",
                            "unexpected_process",
                            Stage.LIFECYCLE,
                            0.82,
                            min(0.70 + streak * 0.08, 0.98),
                            context | {Stage.LIFECYCLE.value},
                        )
                    )
                if signal.connection and signal.process:
                    mission = (
                        criticality.get(signal.hostname, 0.0)
                        >= MISSION_CRITICALITY
                    )
                    stage = (
                        Stage.MISSION_EFFECT
                        if mission
                        else Stage.TRUST_BREAK
                    )
                    predicates.append(
                        self._predicate(
                            signal.hostname,
                            "host",
                            (
                                "mission_asset_compromise"
                                if mission
                                else "cross_layer_presence"
                            ),
                            stage,
                            0.88,
                            0.95 if mission else 0.90,
                            context | {stage.value},
                            mission,
                        )
                    )
                if signal.hostname in self.decoyed_hosts and (
                    signal.connection or signal.process
                ):
                    self.decoy_contacts.add(signal.hostname)
                    predicates.append(
                        self._predicate(
                            signal.hostname,
                            "deception",
                            "honeypot_contact",
                            Stage.TRUST_BREAK,
                            0.98,
                            0.98,
                            context | {"honeypot", Stage.TRUST_BREAK.value},
                        )
                    )
        for key in tuple(self.streaks):
            if key not in active_keys:
                self.streaks[key] = 0
        if self.use_transition_honeypot:
            new_targets = current_hostiles - self.active_hostiles
            for source in self.active_hostiles:
                for target in new_targets:
                    if source != target:
                        self.transition_counts[(source, target)] += 1
        self.active_hostiles = current_hostiles
        for index, alert in enumerate(layered.alerts):
            if not alert.connection or alert.severity == 0:
                continue
            stage = CODE_STAGE.get(alert.host_index)
            if stage is None:
                continue
            target = f"peer:{index}"
            predicates.append(
                self._predicate(
                    target,
                    "peer",
                    "peer_chain_alert",
                    stage,
                    0.60 + alert.severity * 0.10,
                    0.50 + alert.severity * 0.12,
                    frozenset({target, stage.value}),
                )
            )
        return predicates

    def _predicate(
        self,
        target: str,
        layer: str,
        relation: str,
        stage: Stage,
        confidence: float,
        severity: float,
        context: frozenset[str],
        mission_relevant: bool | None = None,
        details: dict[str, float] | None = None,
    ) -> Predicate:
        predicate_id = f"{self.step}:{target}:{layer}:{relation}"
        return Predicate(
            predicate_id=predicate_id,
            stage=stage,
            target=target,
            layer=layer,
            relation=relation,
            timestamp=float(self.step),
            context=context,
            confidence=confidence,
            severity=severity,
            mission_relevant=mission_relevant,
            evidence_ids=(predicate_id,),
            details={} if details is None else details,
        )

    def _advance(self, target: str, relation: str) -> int:
        key = (target, relation)
        self.streaks[key] = self.streaks.get(key, 0) + 1
        return self.streaks[key]

    def _respond(self, finding, layered: LayeredObservation) -> int | None:
        if self.method_v11:
            return self._respond_planned(finding, layered)
        if finding is None or finding.target.startswith("peer:"):
            return None
        target = finding.target
        signal = next(
            (
                signal
                for segment in layered.segments
                for signal in segment.signals
                if signal.hostname == target
            ),
            None,
        )
        if signal is None:
            return None
        if (
            self.event_aware_verification
            and target in self.effect_watches
            and finding.action in {"temporary_isolate", "block", "restore"}
        ):
            return None
        independent_layers = getattr(finding, "independent_layers", 0)
        command = "Monitor"
        if finding.action == "honeypot":
            decoy_target = self._honeypot_target(target, layered)
            if decoy_target is not None:
                if (
                    self.use_transition_honeypot
                    and self.transition_counts[(target, decoy_target)] > 0
                ):
                    self.predicted_decoys += 1
                target = decoy_target
                command = "DeployDecoy"
        elif finding.action == "analyse":
            command = "Analyse"
        elif finding.action == "temporary_isolate":
            if self.corroborated_response and independent_layers < 2:
                command = "Analyse"
            elif (
                self.corroborated_response
                and signal.process
                and signal.connection
            ):
                command = "Restore"
            elif signal.process and not self._strong_evidence(target):
                command = "Analyse"
            elif signal.process and self.remediations[target] > 0:
                command = "Restore"
            else:
                command = "Remove" if signal.process else "Analyse"
        elif finding.action in {"block", "restore"}:
            if self.corroborated_response and independent_layers < 2:
                command = "Analyse"
            elif signal.process and not self._strong_evidence(target):
                command = "Analyse"
            elif signal.process and signal.connection:
                command = "Restore"
            elif signal.process:
                command = "Remove"
            else:
                command = "Analyse"
        action = self.catalog.find(command, (target,)) if command != "Monitor" else self.catalog.find(command)
        if action is None and command == "DeployDecoy":
            action = self.catalog.find("Analyse", (target,))
            command = "Analyse"
        if action is None:
            return None
        if command == "DeployDecoy":
            self.decoyed_hosts.add(target)
        if command == "Analyse" and self.require_fresh_analysis:
            self.analysis_steps[target] = self.step
        if command in {"Remove", "Restore"}:
            if self.require_fresh_analysis:
                self.analysis_steps.pop(target, None)
                self.analysis_confirmations += 1
            self.pending = PendingAction(
                command=command,
                target=target,
                due_step=self.step + ACTION_DURATIONS.get(command, 1),
            )
        return self._commit(action)

    def _respond_planned(
        self,
        finding,
        layered: LayeredObservation,
    ) -> int | None:
        if finding is None or finding.target.startswith("peer:"):
            return None
        target = finding.target
        signal = next(
            (
                signal
                for segment in layered.segments
                for signal in segment.signals
                if signal.hostname == target
            ),
            None,
        )
        if signal is None:
            return None
        if target in self.effect_watches:
            return None
        chain_score = max(
            (chain.score for chain in finding.chains),
            default=0.0,
        )
        evidence = max(
            min(finding.independent_layers / 2, 1.0),
            chain_score,
        )
        if any(
            predicate.relation == "honeypot_contact"
            for predicate in finding.predicates
        ):
            evidence = 1.0
        mission_effect = any(
            predicate.stage == Stage.MISSION_EFFECT
            for predicate in finding.predicates
        )
        decoy_target = self._honeypot_target(target, layered)
        available = {"monitor"}
        if self.catalog.find("Analyse", (target,)) is not None:
            available.add("analyse")
        if decoy_target is not None:
            available.add("honeypot")
        if signal.process and self.catalog.find(
            "Remove",
            (target,),
        ) is not None:
            available.add("temporary_isolate")
        if signal.process and self.catalog.find(
            "Restore",
            (target,),
        ) is not None:
            available.add("restore")
        context = DecisionContext(
            belief=self.beliefs.get(target, finding.risk),
            evidence=evidence,
            criticality=self._criticality(layered).get(target, 0.4),
            coverage_gap=float(decoy_target is not None),
            mission_effect=mission_effect,
        )
        for decision in self.planner.rank(
            context,
            frozenset(available),
        ):
            command = {
                "monitor": "Monitor",
                "analyse": "Analyse",
                "honeypot": "DeployDecoy",
                "temporary_isolate": "Remove",
                "restore": "Restore",
            }[decision.name]
            selected_target = (
                decoy_target if decision.name == "honeypot" else target
            )
            action = (
                self.catalog.find(command)
                if command == "Monitor"
                else self.catalog.find(command, (selected_target,))
            )
            if action is None:
                continue
            self.utility_decisions[decision.name] += 1
            if command == "DeployDecoy":
                self.decoyed_hosts.add(selected_target)
            if command in {"Remove", "Restore"}:
                self.pending = PendingAction(
                    command,
                    selected_target,
                    self.step + ACTION_DURATIONS.get(command, 1),
                )
            return self._commit(action)
        return None

    def _update_beliefs(self, findings) -> None:
        current = {
            finding.target: finding.risk
            for finding in findings
            if not finding.target.startswith("peer:")
        }
        for target in set(self.beliefs) | set(current):
            belief = max(
                self.beliefs.get(target, 0.0) * BELIEF_DECAY,
                current.get(target, 0.0),
            )
            if belief < 0.05:
                self.beliefs.pop(target, None)
            else:
                self.beliefs[target] = belief

    def _proactive_deception(
        self,
        layered: LayeredObservation,
    ) -> int | None:
        criticality = self._criticality(layered)
        candidates = []
        for segment in layered.segments:
            coverage = sum(
                host in self.decoyed_hosts for host in segment.spec.hosts
            )
            for signal in segment.signals:
                if (
                    signal.connection
                    or signal.process
                    or signal.hostname in self.decoyed_hosts
                ):
                    continue
                action = self.catalog.find(
                    "DeployDecoy",
                    (signal.hostname,),
                )
                if action is not None:
                    candidates.append(
                        (
                            coverage,
                            criticality.get(signal.hostname, 0.4),
                            signal.hostname,
                            action,
                        )
                    )
        if not candidates:
            return None
        _, _, target, action = min(candidates)
        self.decoyed_hosts.add(target)
        self.utility_decisions["coverage"] += 1
        return self._commit(action)

    def _strong_evidence(self, target: str) -> bool:
        if not self.require_fresh_analysis:
            return True
        analysis_step = self.analysis_steps.get(target)
        if analysis_step is None:
            return False
        age = self.step - analysis_step
        return 0 < age <= 18

    def _honeypot_target(
        self,
        source: str,
        layered: LayeredObservation,
    ) -> str | None:
        for segment in layered.segments:
            if source not in segment.spec.hosts:
                continue
            candidates = [
                signal.hostname
                for signal in segment.signals
                if signal.hostname != source
                and not signal.connection
                and not signal.process
                and signal.hostname not in self.decoyed_hosts
                and self.catalog.find(
                    "DeployDecoy",
                    (signal.hostname,),
                )
                is not None
            ]
            if candidates:
                criticality = self._criticality(layered)
                return sorted(
                    candidates,
                    key=lambda target: (
                        -(
                            self.transition_counts[(source, target)]
                            if self.use_transition_honeypot
                            else 0
                        ),
                        -criticality.get(target, 0.0),
                        target,
                    ),
                )[0]
        if (
            source not in self.decoyed_hosts
            and self.catalog.find("DeployDecoy", (source,)) is not None
        ):
            return source
        return None

    def _verify(self, layered: LayeredObservation) -> None:
        if self.event_aware_verification:
            self._verify_event_aware(layered)
            return
        if self.pending is None or self.step < self.pending.due_step:
            return
        signal = next(
            (
                signal
                for segment in layered.segments
                for signal in segment.signals
                if signal.hostname == self.pending.target
            ),
            None,
        )
        if signal is None:
            self.unverified_effects += 1
            self.failed_effects[self.pending.command] += 1
        elif self.pending.command == "Remove" and not signal.process:
            self.verified_effects += 1
            self.remediations[self.pending.target] += 1
        elif self.pending.command == "Restore" and not signal.process and not signal.connection:
            self.verified_effects += 1
            self.remediations.pop(self.pending.target, None)
        elif self.pending.command == "Analyse":
            self.unverified_effects += 1
        else:
            self.unverified_effects += 1
            self.failed_effects[self.pending.command] += 1
        self.pending = None

    def _verify_event_aware(self, layered: LayeredObservation) -> None:
        signals = {
            signal.hostname: signal
            for segment in layered.segments
            for signal in segment.signals
        }
        if self.pending is not None and self.step >= self.pending.due_step:
            self.effect_watches[self.pending.target] = EffectWatch(
                command=self.pending.command,
                target=self.pending.target,
                expires_step=self.step + 18,
            )
            self.pending = None
        for target, watch in tuple(self.effect_watches.items()):
            signal = signals.get(target)
            if signal is not None and (signal.process or signal.connection):
                self.unverified_effects += 1
                self.failed_effects[watch.command] += 1
                self.effect_watches.pop(target)
            elif self.step >= watch.expires_step:
                self.verified_effects += 1
                if watch.command == "Remove":
                    self.remediations[target] += 1
                elif watch.command == "Restore":
                    self.remediations.pop(target, None)
                self.effect_watches.pop(target)

    def _criticality(self, layered: LayeredObservation) -> dict[str, float]:
        result: dict[str, float] = {}
        for segment in layered.segments:
            subnet = segment.spec.subnet.lower()
            active = (
                layered.mission == 1
                and ("zone_a" in subnet or "_a_" in subnet)
            ) or (
                layered.mission == 2
                and ("zone_b" in subnet or "_b_" in subnet)
            )
            value = 0.95 if active and "operational" in subnet else 0.75 if active else 0.55
            for signal in segment.signals:
                result[signal.hostname] = value
        return result

    def _policy_action(self, layered: LayeredObservation) -> int | None:
        ordered = sorted(
            {
                value
                for candidate in self.catalog.labels
                for value in candidate.split()
                if value.endswith("_subnet")
            }
        )
        for segment in layered.segments:
            for source_index, (blocked, denied) in enumerate(
                zip(segment.blocked, segment.policy)
            ):
                if blocked == denied:
                    continue
                command = "BlockTrafficZone" if denied else "AllowTrafficZone"
                for index, label in enumerate(self.catalog.labels):
                    if not self.catalog.mask[index]:
                        continue
                    if not label.startswith(f"{command} {segment.spec.subnet} "):
                        continue
                    source_labels = [
                        value for value in label.split() if value.endswith("_subnet")
                    ]
                    if (
                        len(source_labels) >= 2
                        and source_index < len(ordered)
                        and source_labels[-1] == ordered[source_index]
                    ):
                        return index
        return None

    def _select(self, command: str) -> int:
        action = self.catalog.find(command)
        if action is None:
            action = len(self.catalog.labels) - 1
        return self._commit(action)

    def _sleep(self) -> int:
        action = self.catalog.find("Sleep")
        if action is None:
            action = len(self.catalog.labels) - 1
        self.action_counts["Sleep"] += 1
        self.last_action_label = self.catalog.labels[action]
        return action

    def _commit(self, index: int) -> int:
        label = self.catalog.labels[index]
        command = label.split()[0]
        self.cooldown = max(ACTION_DURATIONS.get(command, 1) - 1, 0)
        self.action_counts[command] += 1
        self.last_action_label = label
        return index
