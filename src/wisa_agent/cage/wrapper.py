from __future__ import annotations

from typing import Mapping

from CybORG.Agents.Wrappers.EnterpriseMAE import EnterpriseMAE

from .blue import LayerChainBlueAgent
from .core import SegmentSpec


class MessageRelayEnterpriseMAE(EnterpriseMAE):
    def __init__(
        self,
        env,
        agents: Mapping[str, LayerChainBlueAgent],
        *args,
        **kwargs,
    ):
        self.team_agents = dict(agents)
        super().__init__(env, *args, **kwargs)

    def reset(self, *args, **kwargs):
        observations, info = super().reset(*args, **kwargs)
        self._configure_agents(reset=True)
        return observations, info

    def step(self, action_dict=None, messages=None):
        relay = {
            name: agent.message
            for name, agent in self.team_agents.items()
            if name in self.possible_agents
        }
        observations, rewards, terminated, truncated, info = super().step(
            action_dict=action_dict,
            messages=relay,
        )
        self._configure_agents(reset=False)
        return observations, rewards, terminated, truncated, info

    def _configure_agents(self, reset: bool) -> None:
        for name, agent in self.team_agents.items():
            segments = tuple(
                SegmentSpec(
                    subnet=subnet,
                    hosts=tuple(
                        hostname
                        for hostname in self.hosts(name)
                        if hostname.startswith(f"{subnet}_") and "router" not in hostname
                    ),
                )
                for subnet in self.subnets(name)
            )
            agent.configure(
                segments=segments,
                labels=self.action_labels(name),
                mask=self.action_mask(name),
            )
            if reset:
                agent.reset_episode()
