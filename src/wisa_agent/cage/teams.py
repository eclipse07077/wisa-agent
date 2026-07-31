from __future__ import annotations

from .blue import LayerChainBlueAgent
from .report import ReportBlueAgent
from .wrapper import MessageRelayEnterpriseMAE


def build_team(mode: str) -> dict[str, LayerChainBlueAgent | ReportBlueAgent]:
    report_modes = {
        "report": {},
        "report_v9": {"require_fresh_analysis": True},
        "report_v10": {
            "corroborated_response": True,
            "event_aware_verification": True,
        },
        "report_v11": {
            "event_aware_verification": True,
            "method_v11": True,
        },
        "report_v12": {
            "corroborated_response": True,
            "event_aware_verification": True,
            "proactive_deception": True,
        },
        "report_transition": {"use_transition_honeypot": True},
        "report_no_chain": {"use_chain": False},
        "report_no_honeypot": {"use_honeypot": False},
        "report_no_guard": {"use_guard": False},
    }
    if mode in report_modes:
        return {
            f"blue_agent_{index}": ReportBlueAgent(
                name=f"blue_agent_{index}",
                **report_modes[mode],
            )
            for index in range(5)
        }
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
