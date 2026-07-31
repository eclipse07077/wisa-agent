from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from heapq import heappop, heappush
from math import log
from statistics import median
from typing import Iterable, Iterator

import numpy as np

from wisa_agent.method import (
    AttackOrchestrator,
    Chain,
    ChainBuilder,
    ExperimentPlan,
    Predicate,
    Stage,
)
from wisa_agent.method.config import (
    ANOMALY_WEIGHTS,
    CONNECTOR_LOCAL_WEIGHT,
    CONNECTOR_PERSISTENCE_WEIGHT,
    EDGE_THRESHOLD,
    MAX_CHAIN_LENGTH,
    MMR_PENALTY,
    ROBUST_OUTLIER_SCALE,
    TC_CHAIN_LIMIT,
    TC_PREDICATE_LIMIT,
    TRACE_WINDOW,
    VALIDATION_QUANTILE,
)


RELATION_STAGE = {
    "EVENT_CONNECT": Stage.INGRESS,
    "EVENT_RECVFROM": Stage.INGRESS,
    "EVENT_RECVMSG": Stage.INGRESS,
    "EVENT_EXECUTE": Stage.TRUST_BREAK,
    "EVENT_CLONE": Stage.TRUST_BREAK,
    "EVENT_OPEN": Stage.LIFECYCLE,
    "EVENT_READ": Stage.LIFECYCLE,
    "EVENT_WRITE": Stage.MISSION_EFFECT,
    "EVENT_SENDMSG": Stage.MISSION_EFFECT,
    "EVENT_SENDTO": Stage.MISSION_EFFECT,
}


@dataclass(frozen=True)
class ProvenanceEvent:
    timestamp: int
    source: str
    target: str
    relation: str
    path: str
    source_kind: str
    target_kind: str


@dataclass(frozen=True)
class EventScore:
    event: ProvenanceEvent
    score: float
    structural: float
    trace: float
    path: float


@dataclass(frozen=True)
class CDMAttackResult:
    node_scores: dict[str, float]
    chain_scores: dict[str, float]
    chains: tuple[Chain, ...]
    predicates: tuple[Predicate, ...]
    plans: tuple[ExperimentPlan, ...]


@dataclass
class SemanticGroup:
    subject: str
    session: int
    stage: Stage
    started: int
    last: int
    best: EventScore
    event_count: int = 0
    endpoints: set[str] = field(default_factory=set)
    relations: set[str] = field(default_factory=set)
    paths: set[str] = field(default_factory=set)
    endpoint_scores: dict[str, float] = field(default_factory=dict)
    evidence_ids: list[str] = field(default_factory=list)

    def add(self, item: EventScore) -> None:
        event = item.event
        self.last = event.timestamp
        self.event_count += 1
        self.endpoints.update((event.source, event.target))
        for endpoint in (event.source, event.target):
            self.endpoint_scores[endpoint] = max(
                self.endpoint_scores.get(endpoint, 0.0),
                item.score,
            )
        self.relations.add(event.relation)
        if event.path:
            self.paths.add(NormalProfile._path_bucket(event.path))
        if len(self.evidence_ids) < 64:
            self.evidence_ids.append(
                f"{event.timestamp}:{event.relation}"
            )
        if item.score > self.best.score:
            self.best = item


@dataclass
class TraceSession:
    subject: str
    session: int
    started: int
    last: int
    suspicious: bool = False
    peak: float = 0.0
    groups: dict[Stage, SemanticGroup] = field(default_factory=dict)

    @property
    def session_id(self) -> str:
        return f"{self.subject}:{self.session}"


class TracePredicateMiner:
    def __init__(self, threshold: float):
        self.threshold = threshold
        self.window = 18_000_000_000
        self.active: dict[str, TraceSession] = {}
        self.indices: Counter[str] = Counter()
        self.expiry: list[tuple[int, str, int]] = []
        self.completed: list[TraceSession] = []

    def add(self, item: EventScore) -> None:
        self._expire(item.event.timestamp)
        for subject in CDMAttackAgent._subjects(item.event):
            session = self.active.get(subject)
            if session is None:
                index = self.indices[subject]
                self.indices[subject] += 1
                session = TraceSession(
                    subject,
                    index,
                    item.event.timestamp,
                    item.event.timestamp,
                )
                self.active[subject] = session
            session.last = item.event.timestamp
            session.suspicious = (
                session.suspicious or item.score >= self.threshold
            )
            session.peak = max(session.peak, item.score)
            stage = RELATION_STAGE[item.event.relation]
            group = session.groups.get(stage)
            if group is None:
                group = SemanticGroup(
                    subject,
                    session.session,
                    stage,
                    item.event.timestamp,
                    item.event.timestamp,
                    item,
                )
                session.groups[stage] = group
            group.add(item)
            heappush(
                self.expiry,
                (session.last + self.window, subject, session.session),
            )

    def finish(self) -> list[TraceSession]:
        for subject in tuple(self.active):
            self._complete(subject)
        return self.completed

    def _expire(self, timestamp: int) -> None:
        while self.expiry and self.expiry[0][0] < timestamp:
            expiry, subject, session_id = heappop(self.expiry)
            session = self.active.get(subject)
            if (
                session is not None
                and session.session == session_id
                and session.last + self.window == expiry
            ):
                self._complete(subject)

    def _complete(self, subject: str) -> None:
        session = self.active.pop(subject)
        if session.suspicious:
            self.completed.append(session)


class NormalProfile:
    def __init__(
        self,
        marginalize_missing: bool = False,
        missingness_aware: bool = False,
    ):
        self.marginalize_missing = marginalize_missing
        self.missingness_aware = missingness_aware
        self.structural: Counter[tuple[str, str, str]] = Counter()
        self.structural_context: Counter[tuple[str, str]] = Counter()
        self.transitions: Counter[tuple[str, str]] = Counter()
        self.transition_context: Counter[str] = Counter()
        self.paths: Counter[tuple[str, str]] = Counter()
        self.path_context: Counter[str] = Counter()
        self.path_presence: Counter[tuple[str, bool]] = Counter()
        self.path_presence_context: Counter[str] = Counter()
        self.relations: set[str] = set()
        self.node_kinds: set[str] = set()

    def fit(self, events: Iterable[ProvenanceEvent]) -> None:
        previous: dict[str, tuple[int, str]] = {}
        for event in events:
            structural = (
                event.source_kind,
                event.relation,
                event.target_kind,
            )
            context = (event.source_kind, event.target_kind)
            self.structural[structural] += 1
            self.structural_context[context] += 1
            self.relations.add(event.relation)
            self.node_kinds.update((event.source_kind, event.target_kind))
            if self.missingness_aware:
                present = bool(event.path)
                self.path_presence[(event.relation, present)] += 1
                self.path_presence_context[event.relation] += 1
                if event.path:
                    path = self._path_bucket(event.path)
                    self.paths[(event.relation, path)] += 1
                    self.path_context[event.relation] += 1
            elif event.path or not self.marginalize_missing:
                path = self._path_bucket(event.path)
                self.paths[(event.relation, path)] += 1
                self.path_context[event.relation] += 1
            last = previous.get(event.source)
            if (
                last is not None
                and 0 <= event.timestamp - last[0] <= 18_000_000_000
            ):
                self.transitions[(last[1], event.relation)] += 1
                self.transition_context[last[1]] += 1
            previous[event.source] = (event.timestamp, event.relation)

    def score(
        self,
        event: ProvenanceEvent,
        previous_relation: str | None,
    ) -> EventScore:
        cardinality = max(
            len(self.relations) * max(len(self.node_kinds), 1),
            1,
        )
        structural = self._surprise(
            self.structural[
                (
                    event.source_kind,
                    event.relation,
                    event.target_kind,
                )
            ],
            self.structural_context[
                (event.source_kind, event.target_kind)
            ],
            cardinality,
        )
        if previous_relation is None:
            trace = 0.0
        else:
            trace = self._surprise(
                self.transitions[(previous_relation, event.relation)],
                self.transition_context[previous_relation],
                max(len(self.relations), 1),
            )
        if self.missingness_aware:
            if event.path:
                path = self._surprise(
                    self.paths[
                        (
                            event.relation,
                            self._path_bucket(event.path),
                        )
                    ],
                    self.path_context[event.relation],
                    max(len(self.paths), 1),
                )
            else:
                path = self._surprise(
                    self.path_presence[(event.relation, False)],
                    self.path_presence_context[event.relation],
                    2,
                )
            components = {
                "structural": structural,
                "trace": trace,
                "path": path,
            }
        elif event.path or not self.marginalize_missing:
            path = self._surprise(
                self.paths[(event.relation, self._path_bucket(event.path))],
                self.path_context[event.relation],
                max(len(self.paths), 1),
            )
            components = {
                "structural": structural,
                "trace": trace,
                "path": path,
            }
        else:
            path = 0.0
            components = {
                "structural": structural,
                "trace": trace,
            }
        total_weight = sum(ANOMALY_WEIGHTS[name] for name in components)
        value = sum(
            ANOMALY_WEIGHTS[name] * score / total_weight
            for name, score in components.items()
        )
        return EventScore(
            event=event,
            score=min(max(value, 0.0), 1.0),
            structural=structural,
            trace=trace,
            path=path,
        )

    @staticmethod
    def _surprise(count: int, total: int, cardinality: int) -> float:
        probability = (count + 1) / max(total + cardinality, 1)
        floor = 1 / max(total + cardinality, 2)
        return min(max(log(probability) / log(floor), 0.0), 1.0)

    @staticmethod
    def _path_bucket(path: str) -> str:
        if not path:
            return "unknown"
        parts = path.split("/", 3)
        return "/".join(parts[:3])


class CDMAttackAgent:
    def __init__(
        self,
        profile: NormalProfile,
        threshold: float,
        candidate_limit: int = TC_PREDICATE_LIMIT,
        chain_limit: int = TC_CHAIN_LIMIT,
        predicate_mode: str = "event",
        attribution_mode: str = "endpoints",
    ):
        if predicate_mode not in {"event", "semantic", "trace"}:
            raise ValueError(predicate_mode)
        if attribution_mode not in {
            "endpoints",
            "connectors",
            "cutset",
            "core",
            "seeded",
            "grounded",
        }:
            raise ValueError(attribution_mode)
        self.profile = profile
        self.threshold = threshold
        self.candidate_limit = candidate_limit
        self.chain_limit = chain_limit
        self.predicate_mode = predicate_mode
        self.attribution_mode = attribution_mode
        self.builder = ChainBuilder(
            edge_threshold=EDGE_THRESHOLD,
            max_length=MAX_CHAIN_LENGTH,
            time_window=TRACE_WINDOW,
        )
        self.orchestrator = AttackOrchestrator(self.builder)

    def run(self, events: Iterable[ProvenanceEvent]) -> CDMAttackResult:
        return self.run_scored(self._score_stream(events))

    def run_scored(
        self,
        scored: Iterable[EventScore],
    ) -> CDMAttackResult:
        node_scores: dict[str, float] = {}
        eligible = []
        trace_miner = (
            TracePredicateMiner(self.threshold)
            if self.predicate_mode == "trace"
            else None
        )
        for item in scored:
            for node in (item.event.source, item.event.target):
                node_scores[node] = max(
                    node_scores.get(node, 0.0),
                    item.score,
                )
            if trace_miner is not None:
                trace_miner.add(item)
            elif item.score >= self.threshold:
                eligible.append(item)
        if trace_miner is not None:
            predicates = self._select_sessions(
                [
                    self._semantic_predicate(group, session.peak)
                    for session in trace_miner.finish()
                    for group in session.groups.values()
                ]
            )
        elif self.predicate_mode == "semantic":
            predicates = self._select_predicates(
                self._semantic_predicates(eligible)
            )
        else:
            selected = self._select(eligible)
            predicates = [
                self._predicate(index, item)
                for index, item in enumerate(selected)
            ]
        endpoints = {
            predicate.predicate_id: frozenset(
                predicate.details["endpoints"]
            )
            for predicate in predicates
        }
        chains = self.orchestrator.discover(
            predicates,
            self.chain_limit,
            compatible=lambda left, right: bool(
                endpoints[left.predicate_id]
                & endpoints[right.predicate_id]
            ),
            diversity_penalty=(
                MMR_PENALTY
                if self.attribution_mode in {
                    "connectors",
                    "cutset",
                    "core",
                }
                else 0.0
            ),
        )
        plans = tuple(
            plan
            for plan in self.orchestrator.plan(chains)
            if self.orchestrator.validate(
                plan,
                self.profile.relations
                | {predicate.relation for predicate in predicates},
            )[0]
        )
        if self.attribution_mode == "connectors":
            chain_scores = self._connector_scores(chains)
        elif self.attribution_mode == "cutset":
            chain_scores = self._cutset_scores(chains)
        elif self.attribution_mode == "core":
            chain_scores = self._core_scores(chains)
        elif self.attribution_mode == "seeded":
            chain_scores = self._seeded_scores(chains)
        elif self.attribution_mode == "grounded":
            chain_scores = self._grounded_scores(
                chains,
                node_scores,
            )
        else:
            chain_scores = self._endpoint_scores(chains)
        return CDMAttackResult(
            node_scores=node_scores,
            chain_scores=chain_scores,
            chains=tuple(chains),
            predicates=tuple(predicates),
            plans=plans,
        )

    @staticmethod
    def _endpoint_scores(chains: list[Chain]) -> dict[str, float]:
        scores: dict[str, float] = {}
        for chain in chains:
            for predicate in chain.predicates:
                support = chain.score * predicate.confidence
                for node in predicate.details["endpoints"]:
                    scores[node] = max(scores.get(node, 0.0), support)
        return scores

    @staticmethod
    def _connector_scores(chains: list[Chain]) -> dict[str, float]:
        scores: dict[str, float] = {}
        for chain in chains:
            occurrences: Counter[str] = Counter()
            local: dict[str, float] = {}
            targets = {predicate.target for predicate in chain.predicates}
            for predicate in chain.predicates:
                endpoint_scores = dict(
                    predicate.details.get("endpoint_scores", ())
                )
                values = tuple(endpoint_scores.values())
                center = median(values) if values else 0.0
                deviation = (
                    median(abs(value - center) for value in values)
                    if values
                    else 0.0
                )
                outlier_threshold = (
                    center + ROBUST_OUTLIER_SCALE * deviation
                )
                for node in predicate.details["endpoints"]:
                    occurrences[node] += 1
                    value = float(
                        endpoint_scores.get(
                            node,
                            predicate.confidence,
                        )
                    )
                    local[node] = max(
                        local.get(node, 0.0),
                        value,
                    )
                    if value > outlier_threshold:
                        targets.add(node)
            connectors = targets | {
                node for node, count in occurrences.items() if count >= 2
            }
            for node in connectors:
                persistence = min(occurrences[node] / 2, 1.0)
                contribution = (
                    CONNECTOR_LOCAL_WEIGHT * local.get(node, 0.0)
                    + CONNECTOR_PERSISTENCE_WEIGHT * persistence
                )
                support = chain.score * contribution
                scores[node] = max(scores.get(node, 0.0), support)
        return scores

    @staticmethod
    def _cutset_scores(chains: list[Chain]) -> dict[str, float]:
        scores: dict[str, float] = {}
        for chain in chains:
            occurrences: Counter[str] = Counter()
            local: dict[str, float] = {}
            targets = set()
            for predicate in chain.predicates:
                endpoint_scores = dict(
                    predicate.details.get("endpoint_scores", ())
                )
                targets.add(predicate.target)
                for node in predicate.details["endpoints"]:
                    occurrences[node] += 1
                    local[node] = max(
                        local.get(node, 0.0),
                        float(
                            endpoint_scores.get(
                                node,
                                predicate.confidence,
                            )
                        ),
                    )
            cutset = {
                node for node, count in occurrences.items() if count >= 2
            }
            if not cutset and targets:
                cutset.add(
                    max(
                        targets,
                        key=lambda node: (
                            local.get(node, 0.0),
                            node,
                        ),
                    )
                )
            for node in cutset:
                persistence = min(occurrences[node] / 2, 1.0)
                contribution = (
                    CONNECTOR_LOCAL_WEIGHT * local.get(node, 0.0)
                    + CONNECTOR_PERSISTENCE_WEIGHT * persistence
                )
                support = chain.score * contribution
                scores[node] = max(scores.get(node, 0.0), support)
        return scores

    @staticmethod
    def _core_scores(chains: list[Chain]) -> dict[str, float]:
        scores: dict[str, float] = {}
        for chain in chains:
            endpoint_sets = [
                set(predicate.details["endpoints"])
                for predicate in chain.predicates
            ]
            core = (
                set.intersection(*endpoint_sets)
                if endpoint_sets
                else set()
            )
            local: dict[str, float] = {}
            targets = set()
            for predicate in chain.predicates:
                endpoint_scores = dict(
                    predicate.details.get("endpoint_scores", ())
                )
                targets.add(predicate.target)
                for node in predicate.details["endpoints"]:
                    local[node] = max(
                        local.get(node, 0.0),
                        float(
                            endpoint_scores.get(
                                node,
                                predicate.confidence,
                            )
                        ),
                    )
            if not core and targets:
                core.add(
                    max(
                        targets,
                        key=lambda node: (
                            local.get(node, 0.0),
                            node,
                        ),
                    )
                )
            for node in core:
                contribution = (
                    CONNECTOR_LOCAL_WEIGHT * local.get(node, 0.0)
                    + CONNECTOR_PERSISTENCE_WEIGHT
                )
                support = chain.score * contribution
                scores[node] = max(scores.get(node, 0.0), support)
        return scores

    def _seeded_scores(self, chains: list[Chain]) -> dict[str, float]:
        scores: dict[str, float] = {}
        for chain in chains:
            occurrences: Counter[str] = Counter()
            stages: dict[str, set[Stage]] = {}
            local: dict[str, float] = {}
            seeds = set()
            for predicate in chain.predicates:
                endpoint_scores = dict(
                    predicate.details.get("endpoint_scores", ())
                )
                for node in predicate.details["endpoints"]:
                    value = float(
                        endpoint_scores.get(
                            node,
                            predicate.confidence,
                        )
                    )
                    occurrences[node] += 1
                    stages.setdefault(node, set()).add(predicate.stage)
                    local[node] = max(local.get(node, 0.0), value)
                    if value >= self.threshold:
                        seeds.add(node)
            connectors = {
                node
                for node, node_stages in stages.items()
                if len(node_stages) >= 2 and occurrences[node] >= 2
            }
            selected = seeds | connectors
            if not seeds:
                continue
            for node in selected:
                persistence = min(len(stages[node]) / 3, 1.0)
                contribution = (
                    CONNECTOR_LOCAL_WEIGHT * local[node]
                    + CONNECTOR_PERSISTENCE_WEIGHT * persistence
                )
                scores[node] = max(
                    scores.get(node, 0.0),
                    chain.score * contribution,
                )
        return scores

    @staticmethod
    def _grounded_scores(
        chains: list[Chain],
        node_scores: dict[str, float],
    ) -> dict[str, float]:
        scores: dict[str, float] = {}
        for chain in chains:
            for predicate in chain.predicates:
                support = chain.score * predicate.confidence
                for node in predicate.details["endpoints"]:
                    value = support * node_scores.get(node, 0.0)
                    scores[node] = max(scores.get(node, 0.0), value)
        return scores

    def _score_events(
        self,
        events: Iterable[ProvenanceEvent],
    ) -> list[EventScore]:
        return list(self._score_stream(events))

    def _score_stream(
        self,
        events: Iterable[ProvenanceEvent],
    ) -> Iterator[EventScore]:
        previous: dict[str, tuple[int, str]] = {}
        for event in events:
            last = previous.get(event.source)
            previous_relation = None
            if (
                last is not None
                and 0 <= event.timestamp - last[0] <= 18_000_000_000
            ):
                previous_relation = last[1]
            yield self.profile.score(event, previous_relation)
            previous[event.source] = (event.timestamp, event.relation)

    def _select(self, scored: list[EventScore]) -> list[EventScore]:
        by_stage: dict[Stage, list[EventScore]] = {
            stage: [] for stage in Stage
        }
        for item in scored:
            by_stage[RELATION_STAGE[item.event.relation]].append(item)
        quota = max(self.candidate_limit // len(Stage), 1)
        selected = [
            item
            for stage in Stage
            for item in sorted(
                by_stage[stage],
                key=lambda value: value.score,
                reverse=True,
            )[:quota]
        ]
        selected_ids = {id(item) for item in selected}
        for item in sorted(scored, key=lambda value: value.score, reverse=True):
            if len(selected) >= self.candidate_limit:
                break
            if id(item) not in selected_ids:
                selected.append(item)
                selected_ids.add(id(item))
        return selected

    def _select_predicates(
        self,
        predicates: list[Predicate],
    ) -> list[Predicate]:
        by_stage: dict[Stage, list[Predicate]] = {
            stage: [] for stage in Stage
        }
        for predicate in predicates:
            by_stage[predicate.stage].append(predicate)
        quota = max(self.candidate_limit // len(Stage), 1)
        selected = [
            predicate
            for stage in Stage
            for predicate in sorted(
                by_stage[stage],
                key=lambda item: (item.confidence, item.severity),
                reverse=True,
            )[:quota]
        ]
        selected_ids = {item.predicate_id for item in selected}
        for predicate in sorted(
            predicates,
            key=lambda item: (item.confidence, item.severity),
            reverse=True,
        ):
            if len(selected) >= self.candidate_limit:
                break
            if predicate.predicate_id not in selected_ids:
                selected.append(predicate)
                selected_ids.add(predicate.predicate_id)
        return selected

    def _select_sessions(
        self,
        predicates: list[Predicate],
    ) -> list[Predicate]:
        sessions: dict[str, list[Predicate]] = {}
        for predicate in predicates:
            session_id = str(predicate.details["session_id"])
            sessions.setdefault(session_id, []).append(predicate)
        ranked = sorted(
            sessions.values(),
            key=lambda group: max(
                float(item.details["session_score"]) for item in group
            ),
            reverse=True,
        )
        selected = []
        for group in ranked:
            ordered = sorted(
                group,
                key=lambda item: item.timestamp or 0.0,
            )
            if selected and len(selected) + len(ordered) > self.candidate_limit:
                continue
            selected.extend(ordered)
            if len(selected) >= self.candidate_limit:
                break
        return selected[: self.candidate_limit]

    def _semantic_predicates(
        self,
        scored: list[EventScore],
    ) -> list[Predicate]:
        groups: dict[tuple[str, int, Stage], SemanticGroup] = {}
        sessions: dict[str, tuple[int, int]] = {}
        for item in scored:
            event = item.event
            for subject in self._subjects(event):
                session, last = sessions.get(subject, (0, event.timestamp))
                if event.timestamp - last > 18_000_000_000:
                    session += 1
                sessions[subject] = (session, event.timestamp)
                stage = RELATION_STAGE[event.relation]
                key = (subject, session, stage)
                group = groups.get(key)
                if group is None:
                    group = SemanticGroup(
                        subject=subject,
                        session=session,
                        stage=stage,
                        started=event.timestamp,
                        last=event.timestamp,
                        best=item,
                    )
                    groups[key] = group
                group.add(item)
        return [
            self._semantic_predicate(group)
            for group in groups.values()
        ]

    @staticmethod
    def _subjects(event: ProvenanceEvent) -> tuple[str, ...]:
        subjects = []
        if event.source_kind == "subject":
            subjects.append(event.source)
        if event.target_kind == "subject" and event.target not in subjects:
            subjects.append(event.target)
        return tuple(subjects)

    @staticmethod
    def _semantic_predicate(
        group: SemanticGroup,
        session_score: float | None = None,
    ) -> Predicate:
        item = group.best
        event = item.event
        predicate_id = (
            f"{group.subject}:{group.session}:{group.stage.value}:"
            f"{event.timestamp}"
        )
        endpoints = tuple(sorted(group.endpoints))
        relations = tuple(sorted(group.relations))
        context = {
            f"entity:{group.subject}",
            f"session:{group.subject}:{group.session}",
            f"types:{event.source_kind}:{event.target_kind}",
        }
        context.update(f"relation:{relation}" for relation in relations)
        context.update(f"path:{path}" for path in group.paths)
        severity = (
            0.75 * item.score
            + 0.25 * max(item.structural, item.trace)
        )
        return Predicate(
            predicate_id=predicate_id,
            stage=group.stage,
            target=group.subject,
            layer=f"{event.source_kind}->{event.target_kind}",
            relation=event.relation,
            timestamp=event.timestamp / 1e9,
            context=frozenset(context),
            confidence=item.score,
            severity=severity,
            mission_relevant=group.stage == Stage.MISSION_EFFECT,
            evidence_ids=tuple(group.evidence_ids),
            details={
                "endpoints": endpoints,
                "endpoint_scores": tuple(
                    sorted(group.endpoint_scores.items())
                ),
                "relations": relations,
                "event_count": group.event_count,
                "window": (group.started, group.last),
                "session_id": f"{group.subject}:{group.session}",
                "session_score": (
                    item.score if session_score is None else session_score
                ),
                "structural": item.structural,
                "trace": item.trace,
                "path": item.path,
            },
        )

    @staticmethod
    def _predicate(index: int, item: EventScore) -> Predicate:
        event = item.event
        predicate_id = f"{event.timestamp}:{index}:{event.relation}"
        context = {
            f"source:{event.source}",
            f"target:{event.target}",
            f"relation:{event.relation}",
            f"types:{event.source_kind}:{event.target_kind}",
        }
        if event.path:
            context.add(f"path:{NormalProfile._path_bucket(event.path)}")
        stage = RELATION_STAGE[event.relation]
        return Predicate(
            predicate_id=predicate_id,
            stage=stage,
            target=event.target,
            layer=f"{event.source_kind}->{event.target_kind}",
            relation=event.relation,
            timestamp=event.timestamp / 1e9,
            context=frozenset(context),
            confidence=item.score,
            severity=(
                0.75 * item.score
                + 0.25 * max(item.structural, item.trace)
            ),
            mission_relevant=stage == Stage.MISSION_EFFECT,
            evidence_ids=(predicate_id,),
            details={
                "endpoints": (event.source, event.target),
                "structural": item.structural,
                "trace": item.trace,
                "path": item.path,
            },
        )


def validation_threshold(
    profile: NormalProfile,
    events: Iterable[ProvenanceEvent],
    quantile: float = VALIDATION_QUANTILE,
) -> float:
    scores = np.fromiter(
        (
            item.score
            for item in CDMAttackAgent(
                profile,
                1.0,
            )._score_stream(events)
        ),
        dtype=float,
    )
    if len(scores) == 0:
        return 1.0
    return float(np.quantile(scores, quantile))
