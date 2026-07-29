from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

import numpy as np
from CybORG.Agents import BaseAgent

from .core import (
    ChainTracker,
    HostRisk,
    ObservationDecoder,
    SegmentSpec,
    encode_message,
)


ACTION_DURATIONS = {
    "Analyse": 2,
    "DeployDecoy": 2,
    "Remove": 3,
    "Restore": 5,
}


@dataclass
class ActionCatalog:
    labels: tuple[str, ...] = ()
    mask: tuple[bool, ...] = ()

    def update(self, labels: Iterable[str], mask: Iterable[bool]) -> None:
        self.labels = tuple(labels)
        self.mask = tuple(bool(value) for value in mask)

    def find(self, command: str, terms: Iterable[str] = ()) -> int | None:
        required = tuple(terms)
        for index, label in enumerate(self.labels):
            if not self.mask[index]:
                continue
            if label == command or (
                label.startswith(f"{command} ") and all(term in label for term in required)
            ):
                return index
        return None


class LayerChainBlueAgent(BaseAgent):
    def __init__(self, name: str | None = None, mode: str = "layerchain"):
        super().__init__(name)
        self.mode = mode
        self.catalog = ActionCatalog()
        self.decoder: ObservationDecoder | None = None
        self.tracker = ChainTracker()
        self.step = 0
        self.cooldown = 0
        self.message = np.zeros(8, dtype=bool)
        self.decoyed_hosts: set[str] = set()
        self.round_robin = 0
        self.action_counts: Counter[str] = Counter()
        self.last_action_label = ""

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
        self.tracker.reset()
        self.step = 0
        self.cooldown = 0
        self.message = np.zeros(8, dtype=bool)
        self.decoyed_hosts.clear()
        self.round_robin = 0
        self.action_counts.clear()
        self.last_action_label = ""

    def get_action(self, observation: np.ndarray, action_space) -> int:
        if self.decoder is None:
            return action_space.n - 1

        layered = self.decoder.decode(observation)
        use_chain = self.mode == "layerchain"
        risks = self.tracker.update(layered, self.step, use_chain=use_chain)
        top_risk = risks[0] if risks else None
        self.message = encode_message(top_risk) if use_chain else np.zeros(8, dtype=bool)
        self.step += 1

        if self.mode == "sleep":
            return self._select("Sleep")

        if self.cooldown > 0:
            self.cooldown -= 1
            return self._select("Sleep")

        action = self._respond(top_risk, layered)
        if action is None:
            action = self._maintain(layered)
        if action is None:
            action = self._select("Sleep")
        return action

    def _respond(self, risk: HostRisk | None, layered) -> int | None:
        if risk is not None and risk.severity >= 3:
            command = (
                "Restore"
                if risk.process_streak >= 2 or risk.chain_links > 0
                else "Analyse"
            )
            action = self.catalog.find(command, (risk.signal.hostname,))
            if action is not None:
                return self._commit(action)

        if risk is not None and risk.severity == 2:
            command = "Remove" if risk.process_streak >= 2 else "Analyse"
            action = self.catalog.find(command, (risk.signal.hostname,))
            if action is not None:
                return self._commit(action)

        if risk is not None and risk.severity == 1 and risk.score >= 0.38:
            action = self.catalog.find("Analyse", (risk.signal.hostname,))
            if action is not None:
                return self._commit(action)

        if self.mode == "layerchain":
            severe_alerts = sum(alert.severity >= 2 for alert in layered.alerts)
            if severe_alerts >= 2:
                action = self.catalog.find("Monitor")
                if action is not None:
                    return self._commit(action)
        return None

    def _maintain(self, layered) -> int | None:
        policy_action = self._policy_action(layered)
        if policy_action is not None:
            return self._commit(policy_action)

        if self.step % 6 == 0:
            action = self.catalog.find("Monitor")
            if action is not None:
                return self._commit(action)

        valid_hosts = [
            signal.hostname
            for segment in layered.segments
            for signal in segment.signals
            if self.catalog.find("DeployDecoy", (signal.hostname,)) is not None
        ]
        undecoyed = [host for host in valid_hosts if host not in self.decoyed_hosts]
        if undecoyed:
            hostname = undecoyed[self.round_robin % len(undecoyed)]
            self.round_robin += 1
            action = self.catalog.find("DeployDecoy", (hostname,))
            if action is not None:
                self.decoyed_hosts.add(hostname)
                return self._commit(action)

        action = self.catalog.find("Monitor")
        return self._commit(action) if action is not None else None

    def _policy_action(self, layered) -> int | None:
        for segment in layered.segments:
            for source_index, (blocked, denied) in enumerate(
                zip(segment.blocked, segment.policy)
            ):
                if source_index >= len(segment.policy) or blocked == denied:
                    continue
                command = "BlockTrafficZone" if denied else "AllowTrafficZone"
                source_marker = f"<- "
                for index, label in enumerate(self.catalog.labels):
                    if not self.catalog.mask[index]:
                        continue
                    if not label.startswith(f"{command} {segment.spec.subnet} "):
                        continue
                    if source_marker not in label:
                        continue
                    source_labels = [
                        value
                        for value in label.split()
                        if value.endswith("_subnet")
                    ]
                    if len(source_labels) < 2:
                        continue
                    source_name = source_labels[-1]
                    ordered = sorted(
                        {
                            value
                            for candidate in self.catalog.labels
                            for value in candidate.split()
                            if value.endswith("_subnet")
                        }
                    )
                    if source_index < len(ordered) and source_name == ordered[source_index]:
                        return index
        return None

    def _select(self, command: str) -> int:
        action = self.catalog.find(command)
        if action is None:
            action = len(self.catalog.labels) - 1
        return self._commit(action)

    def _commit(self, index: int) -> int:
        label = self.catalog.labels[index]
        command = label.split()[0]
        self.cooldown = max(ACTION_DURATIONS.get(command, 1) - 1, 0)
        self.action_counts[command] += 1
        self.last_action_label = label
        return index
