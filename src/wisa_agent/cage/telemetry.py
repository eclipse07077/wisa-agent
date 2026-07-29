from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any


CHAIN_STAGES = (
    ("AggressiveServiceDiscovery", "StealthServiceDiscovery"),
    ("ExploitRemoteService",),
    ("PrivilegeEscalate",),
    ("Impact",),
)


def _success_name(value: Any) -> str:
    name = getattr(value, "name", None)
    if name is not None:
        return str(name)
    if value is True:
        return "TRUE"
    if value is False:
        return "FALSE"
    return str(value).upper()


def _lineage_depth(session: Any, sessions: dict[Any, Any]) -> int:
    by_name = {
        getattr(candidate, "name", None): candidate
        for candidate in sessions.values()
        if getattr(candidate, "name", None) is not None
    }
    depth = 0
    current = session
    seen: set[tuple[Any, Any]] = set()
    while getattr(current, "parent", None) is not None:
        marker = (getattr(current, "ident", None), getattr(current, "parent", None))
        if marker in seen:
            break
        seen.add(marker)
        depth += 1
        parent = getattr(current, "parent", None)
        current = sessions.get(parent) or by_name.get(parent)
        if current is None:
            break
    return depth


@dataclass
class AttackTelemetry:
    red_agents: tuple[str, ...] = ()
    initial_session_hosts: set[str] = field(default_factory=set)
    initial_privileged_hosts: set[str] = field(default_factory=set)
    session_hosts: set[str] = field(default_factory=set)
    privileged_hosts: set[str] = field(default_factory=set)
    successful_exploit_hosts: set[str] = field(default_factory=set)
    impacted_hosts: set[str] = field(default_factory=set)
    max_concurrent_session_hosts: int = 0
    max_concurrent_privileged_hosts: int = 0
    max_session_lineage_depth: int = 0
    first_new_session_step: int | None = None
    first_successful_impact_step: int | None = None
    action_completed: Counter[str] = field(default_factory=Counter)
    action_succeeded: Counter[str] = field(default_factory=Counter)
    action_failed: Counter[str] = field(default_factory=Counter)
    successful_impact_count: int = 0
    target_events: dict[str, dict[str, list[int]]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(list))
    )

    def reset(self, cyborg: Any) -> None:
        self.red_agents = tuple(
            name for name in cyborg.get_agent_ids() if "red" in name.lower()
        )
        self.initial_session_hosts.clear()
        self.initial_privileged_hosts.clear()
        self.session_hosts.clear()
        self.privileged_hosts.clear()
        self.successful_exploit_hosts.clear()
        self.impacted_hosts.clear()
        self.max_concurrent_session_hosts = 0
        self.max_concurrent_privileged_hosts = 0
        self.max_session_lineage_depth = 0
        self.first_new_session_step = None
        self.first_successful_impact_step = None
        self.action_completed.clear()
        self.action_succeeded.clear()
        self.action_failed.clear()
        self.successful_impact_count = 0
        self.target_events.clear()
        self._capture_sessions(cyborg, step=0)
        self.initial_session_hosts.update(self.session_hosts)
        self.initial_privileged_hosts.update(self.privileged_hosts)

    def observe(self, cyborg: Any, step: int) -> None:
        ip_to_hostname = {
            str(ip): hostname for hostname, ip in cyborg.get_ip_map().items()
        }
        for agent_name in self.red_agents:
            observation = cyborg.get_observation(agent_name)
            action = observation.get("action")
            if action is None:
                continue
            action_name = type(action).__name__
            if action_name == "Sleep":
                continue
            result = _success_name(observation.get("success"))
            if result not in {"TRUE", "FALSE"}:
                continue
            self.action_completed[action_name] += 1
            if result == "TRUE":
                self.action_succeeded[action_name] += 1
                target = self._target(action, ip_to_hostname)
                if target is not None:
                    self.target_events[target][action_name].append(step)
                if action_name == "ExploitRemoteService" and target is not None:
                    self.successful_exploit_hosts.add(target)
                if action_name == "Impact":
                    self.successful_impact_count += 1
                    if target is not None:
                        self.impacted_hosts.add(target)
                    if self.first_successful_impact_step is None:
                        self.first_successful_impact_step = step
            else:
                self.action_failed[action_name] += 1
        self._capture_sessions(cyborg, step)

    def result(self) -> dict[str, Any]:
        completed_hosts = sorted(
            host for host in self.target_events if self._chain_completed(host)
        )
        new_session_hosts = self.session_hosts - self.initial_session_hosts
        new_privileged_hosts = (
            self.privileged_hosts - self.initial_privileged_hosts
        )
        action_results = {}
        for name in sorted(self.action_completed):
            completed = self.action_completed[name]
            succeeded = self.action_succeeded[name]
            action_results[name] = {
                "completed": completed,
                "succeeded": succeeded,
                "failed": self.action_failed[name],
                "success_rate": succeeded / completed if completed else None,
            }
        privileged_count = len(self.privileged_hosts)
        return {
            "initial_session_hosts": sorted(self.initial_session_hosts),
            "initial_privileged_hosts": sorted(self.initial_privileged_hosts),
            "unique_session_hosts": len(self.session_hosts),
            "unique_new_session_hosts": len(new_session_hosts),
            "new_session_hosts": sorted(new_session_hosts),
            "unique_privileged_hosts": privileged_count,
            "unique_new_privileged_hosts": len(new_privileged_hosts),
            "new_privileged_hosts": sorted(new_privileged_hosts),
            "successful_exploit_hosts": len(self.successful_exploit_hosts),
            "unique_impacted_hosts": len(self.impacted_hosts),
            "impacted_hosts": sorted(self.impacted_hosts),
            "successful_impact_count": self.successful_impact_count,
            "first_new_session_step": self.first_new_session_step,
            "first_successful_impact_step": self.first_successful_impact_step,
            "max_concurrent_session_hosts": self.max_concurrent_session_hosts,
            "max_concurrent_privileged_hosts": self.max_concurrent_privileged_hosts,
            "max_session_lineage_depth": self.max_session_lineage_depth,
            "ordered_chain_completions": len(completed_hosts),
            "ordered_chain_hosts": completed_hosts,
            "privileged_to_impact_host_rate": (
                len(self.impacted_hosts) / privileged_count
                if privileged_count
                else None
            ),
            "action_results": action_results,
        }

    def _capture_sessions(self, cyborg: Any, step: int) -> None:
        state = cyborg.environment_controller.state
        current_hosts: set[str] = set()
        current_privileged: set[str] = set()
        for agent_name in self.red_agents:
            sessions = state.sessions.get(agent_name, {})
            for session in sessions.values():
                if not getattr(session, "active", True):
                    continue
                hostname = getattr(session, "hostname", None)
                if hostname is None:
                    continue
                current_hosts.add(hostname)
                if session.has_privileged_access():
                    current_privileged.add(hostname)
                self.max_session_lineage_depth = max(
                    self.max_session_lineage_depth,
                    _lineage_depth(session, sessions),
                )
        previous_hosts = set(self.session_hosts)
        self.session_hosts.update(current_hosts)
        self.privileged_hosts.update(current_privileged)
        self.max_concurrent_session_hosts = max(
            self.max_concurrent_session_hosts,
            len(current_hosts),
        )
        self.max_concurrent_privileged_hosts = max(
            self.max_concurrent_privileged_hosts,
            len(current_privileged),
        )
        if (
            step > 0
            and self.first_new_session_step is None
            and (current_hosts - self.initial_session_hosts - previous_hosts)
        ):
            self.first_new_session_step = step

    @staticmethod
    def _target(action: Any, ip_to_hostname: dict[str, str]) -> str | None:
        hostname = getattr(action, "hostname", None)
        if hostname is not None:
            return str(hostname)
        ip_address = getattr(action, "ip_address", None)
        if ip_address is not None:
            return ip_to_hostname.get(str(ip_address), str(ip_address))
        return None

    def _chain_completed(self, host: str) -> bool:
        events = self.target_events[host]
        previous_step = -1
        for stage in CHAIN_STAGES:
            candidates = sorted(
                step
                for action_name in stage
                for step in events.get(action_name, ())
                if step > previous_step
            )
            if not candidates:
                return False
            previous_step = candidates[0]
        return True
