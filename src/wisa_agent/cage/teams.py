from __future__ import annotations

from .blue import LayerChainBlueAgent
from .wrapper import MessageRelayEnterpriseMAE


def build_team(mode: str) -> dict[str, LayerChainBlueAgent]:
    return {
        f"blue_agent_{index}": LayerChainBlueAgent(
            name=f"blue_agent_{index}",
            mode=mode,
        )
        for index in range(5)
    }


class LayerChainSubmission:
    NAME = "LayerChain"
    TEAM = "WISA Agent Research"
    TECHNIQUE = "Layer Discovery and Causal Chaining"
    AGENTS = build_team("layerchain")

    @staticmethod
    def wrap(env):
        return MessageRelayEnterpriseMAE(env, LayerChainSubmission.AGENTS)


class ReactiveSubmission:
    NAME = "Reactive"
    TEAM = "WISA Agent Research"
    TECHNIQUE = "Reactive Heuristic"
    AGENTS = build_team("reactive")

    @staticmethod
    def wrap(env):
        return MessageRelayEnterpriseMAE(env, ReactiveSubmission.AGENTS)
