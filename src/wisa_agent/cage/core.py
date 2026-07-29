from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


NUM_SUBNETS = 9
MESSAGE_COUNT = 4
MESSAGE_WIDTH = 8
MESSAGE_BITS = MESSAGE_COUNT * MESSAGE_WIDTH


@dataclass(frozen=True)
class SegmentSpec:
    subnet: str
    hosts: tuple[str, ...]


@dataclass(frozen=True)
class HostSignal:
    subnet: str
    hostname: str
    host_index: int
    process: bool
    connection: bool


@dataclass(frozen=True)
class SegmentState:
    spec: SegmentSpec
    blocked: tuple[bool, ...]
    policy: tuple[bool, ...]
    signals: tuple[HostSignal, ...]


@dataclass(frozen=True)
class RemoteAlert:
    severity: int
    host_index: int
    process: bool
    connection: bool


@dataclass(frozen=True)
class LayeredObservation:
    mission: int
    segments: tuple[SegmentState, ...]
    alerts: tuple[RemoteAlert, ...]


@dataclass
class HostMemory:
    process_streak: int = 0
    connection_streak: int = 0
    last_active_step: int = -1
    chain_links: int = 0


@dataclass(frozen=True)
class HostRisk:
    signal: HostSignal
    severity: int
    score: float
    stage: str
    process_streak: int
    connection_streak: int
    chain_links: int


class ObservationDecoder:
    def __init__(self, segments: Iterable[SegmentSpec]):
        self.segments = tuple(segments)

    def decode(self, observation: np.ndarray) -> LayeredObservation:
        vector = np.asarray(observation, dtype=np.int64)
        expected = 1 + MESSAGE_BITS
        expected += sum(3 * NUM_SUBNETS + 2 * len(spec.hosts) for spec in self.segments)
        if vector.size != expected:
            raise ValueError(f"unexpected observation length: {vector.size} != {expected}")

        cursor = 1
        states: list[SegmentState] = []
        for spec in self.segments:
            cursor += NUM_SUBNETS
            blocked = tuple(bool(v) for v in vector[cursor : cursor + NUM_SUBNETS])
            cursor += NUM_SUBNETS
            policy = tuple(bool(v) for v in vector[cursor : cursor + NUM_SUBNETS])
            cursor += NUM_SUBNETS
            process = vector[cursor : cursor + len(spec.hosts)]
            cursor += len(spec.hosts)
            connection = vector[cursor : cursor + len(spec.hosts)]
            cursor += len(spec.hosts)
            signals = tuple(
                HostSignal(
                    subnet=spec.subnet,
                    hostname=hostname,
                    host_index=index,
                    process=bool(process[index]),
                    connection=bool(connection[index]),
                )
                for index, hostname in enumerate(spec.hosts)
            )
            states.append(
                SegmentState(
                    spec=spec,
                    blocked=blocked,
                    policy=policy,
                    signals=signals,
                )
            )

        alerts = decode_messages(vector[cursor:])
        return LayeredObservation(
            mission=int(vector[0]),
            segments=tuple(states),
            alerts=alerts,
        )


class ChainTracker:
    def __init__(self, chain_window: int = 8):
        self.chain_window = chain_window
        self.memory: dict[str, HostMemory] = {}
        self.last_active_host: str | None = None
        self.last_active_step = -1

    def reset(self) -> None:
        self.memory.clear()
        self.last_active_host = None
        self.last_active_step = -1

    def update(
        self,
        observation: LayeredObservation,
        step: int,
        use_chain: bool = True,
    ) -> tuple[HostRisk, ...]:
        remote_severity = max((alert.severity for alert in observation.alerts), default=0)
        risks: list[HostRisk] = []
        for segment in observation.segments:
            for signal in segment.signals:
                memory = self.memory.setdefault(signal.hostname, HostMemory())
                memory.process_streak = memory.process_streak + 1 if signal.process else 0
                memory.connection_streak = (
                    memory.connection_streak + 1 if signal.connection else 0
                )
                active = signal.process or signal.connection
                if active:
                    if (
                        use_chain
                        and self.last_active_host not in (None, signal.hostname)
                        and self.last_active_step >= 0
                        and step - self.last_active_step <= self.chain_window
                    ):
                        memory.chain_links += 1
                    memory.last_active_step = step
                    self.last_active_host = signal.hostname
                    self.last_active_step = step

                severity, stage = classify_signal(signal)
                score = 0.50 * float(signal.process) + 0.30 * float(signal.connection)
                if use_chain:
                    score += min(memory.process_streak + memory.connection_streak, 4) * 0.04
                    score += min(memory.chain_links, 2) * 0.07
                    score += remote_severity * 0.03
                if severity > 0:
                    risks.append(
                        HostRisk(
                            signal=signal,
                            severity=severity,
                            score=min(score, 1.0),
                            stage=stage,
                            process_streak=memory.process_streak,
                            connection_streak=memory.connection_streak,
                            chain_links=memory.chain_links,
                        )
                    )
        return tuple(
            sorted(
                risks,
                key=lambda risk: (risk.severity, risk.score, risk.signal.hostname),
                reverse=True,
            )
        )


def classify_signal(signal: HostSignal) -> tuple[int, str]:
    if signal.process and signal.connection:
        return 3, "lateral"
    if signal.process:
        return 2, "execution"
    if signal.connection:
        return 1, "discovery"
    return 0, "benign"


def encode_message(risk: HostRisk | None) -> np.ndarray:
    bits = np.zeros(MESSAGE_WIDTH, dtype=bool)
    if risk is None:
        return bits
    severity = min(max(risk.severity, 0), 3)
    host_index = min(max(risk.signal.host_index, 0), 15)
    bits[0] = bool(severity & 0b10)
    bits[1] = bool(severity & 0b01)
    for offset in range(4):
        bits[2 + offset] = bool(host_index & (1 << (3 - offset)))
    bits[6] = risk.signal.process
    bits[7] = risk.signal.connection
    return bits


def decode_messages(bits: np.ndarray) -> tuple[RemoteAlert, ...]:
    flat = np.asarray(bits, dtype=np.int64)
    if flat.size != MESSAGE_BITS:
        raise ValueError(f"unexpected message length: {flat.size}")
    alerts: list[RemoteAlert] = []
    for index in range(MESSAGE_COUNT):
        message = flat[index * MESSAGE_WIDTH : (index + 1) * MESSAGE_WIDTH]
        severity = int(message[0]) * 2 + int(message[1])
        host_index = sum(int(message[2 + offset]) << (3 - offset) for offset in range(4))
        alerts.append(
            RemoteAlert(
                severity=severity,
                host_index=host_index,
                process=bool(message[6]),
                connection=bool(message[7]),
            )
        )
    return tuple(alerts)
