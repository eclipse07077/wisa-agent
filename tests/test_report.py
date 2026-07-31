from types import SimpleNamespace

import numpy as np

from wisa_agent.cage.core import (
    HostSignal,
    LayeredObservation,
    SegmentSpec,
    SegmentState,
)
from wisa_agent.cage.report import (
    PendingAction,
    ReportBlueAgent,
    encode_report_message,
)
from wisa_agent.method import Stage


def test_report_message_layout():
    bits = encode_report_message(Stage.TRUST_BREAK, 0.8, 2)
    assert bits.shape == (8,)
    assert bits[0]
    assert bits[6]
    assert bits[7]


def test_mission_predicate_and_next_honeypot():
    spec = SegmentSpec(
        "operational_zone_a_subnet",
        ("source", "next"),
    )
    layered = LayeredObservation(
        mission=1,
        segments=(
            SegmentState(
                spec=spec,
                blocked=(False,) * 9,
                policy=(False,) * 9,
                signals=(
                    HostSignal(
                        spec.subnet,
                        "source",
                        0,
                        True,
                        True,
                    ),
                    HostSignal(
                        spec.subnet,
                        "next",
                        1,
                        False,
                        False,
                    ),
                ),
            ),
        ),
        alerts=(),
    )
    agent = ReportBlueAgent()
    agent.catalog.update(
        ("DeployDecoy source", "DeployDecoy next"),
        (True, True),
    )
    predicates = agent._predicates(layered)
    assert any(item.stage == Stage.MISSION_EFFECT for item in predicates)
    assert agent._honeypot_target("source", layered) == "next"


def test_temporary_isolate_materializes_remove():
    spec = SegmentSpec("subnet", ("source",))
    layered = LayeredObservation(
        mission=0,
        segments=(
            SegmentState(
                spec=spec,
                blocked=(False,) * 9,
                policy=(False,) * 9,
                signals=(
                    HostSignal(
                        spec.subnet,
                        "source",
                        0,
                        True,
                        False,
                    ),
                ),
            ),
        ),
        alerts=(),
    )
    agent = ReportBlueAgent()
    agent.catalog.update(
        ("Remove source", "Restore source", "Monitor"),
        (True, True, True),
    )
    action = agent._respond(
        SimpleNamespace(action="temporary_isolate", target="source"),
        layered,
    )
    assert action == 0
    assert agent.pending is not None
    assert agent.pending.command == "Remove"
    agent.pending = None
    agent.remediations["source"] = 1
    action = agent._respond(
        SimpleNamespace(action="temporary_isolate", target="source"),
        layered,
    )
    assert action == 1
    assert agent.pending is not None
    assert agent.pending.command == "Restore"


def test_strong_response_requires_fresh_persistent_analysis():
    spec = SegmentSpec("subnet", ("source",))
    layered = LayeredObservation(
        mission=0,
        segments=(
            SegmentState(
                spec=spec,
                blocked=(False,) * 9,
                policy=(False,) * 9,
                signals=(
                    HostSignal(
                        spec.subnet,
                        "source",
                        0,
                        True,
                        False,
                    ),
                ),
            ),
        ),
        alerts=(),
    )
    agent = ReportBlueAgent(require_fresh_analysis=True)
    agent.catalog.update(
        ("Analyse source", "Remove source", "Restore source", "Monitor"),
        (True, True, True, True),
    )
    finding = SimpleNamespace(action="temporary_isolate", target="source")
    assert agent._respond(finding, layered) == 0
    assert agent.analysis_steps["source"] == 0
    assert agent.pending is None
    agent.step = 2
    assert agent._respond(finding, layered) == 1
    assert "source" not in agent.analysis_steps
    assert agent.analysis_confirmations == 1
    assert agent.pending is not None
    assert agent.pending.command == "Remove"


def test_stale_analysis_does_not_authorize_strong_response():
    spec = SegmentSpec("subnet", ("source",))
    layered = LayeredObservation(
        mission=0,
        segments=(
            SegmentState(
                spec=spec,
                blocked=(False,) * 9,
                policy=(False,) * 9,
                signals=(
                    HostSignal(
                        spec.subnet,
                        "source",
                        0,
                        True,
                        True,
                    ),
                ),
            ),
        ),
        alerts=(),
    )
    agent = ReportBlueAgent(require_fresh_analysis=True)
    agent.catalog.update(
        ("Analyse source", "Restore source", "Monitor"),
        (True, True, True),
    )
    agent.analysis_steps["source"] = 1
    agent.step = 20
    finding = SimpleNamespace(action="restore", target="source")
    assert agent._respond(finding, layered) == 0
    assert agent.analysis_steps["source"] == 20
    assert agent.pending is None


def test_corroborated_response_routes_cross_layer_to_restore():
    spec = SegmentSpec("subnet", ("source",))
    layered = LayeredObservation(
        mission=0,
        segments=(
            SegmentState(
                spec=spec,
                blocked=(False,) * 9,
                policy=(False,) * 9,
                signals=(
                    HostSignal(
                        spec.subnet,
                        "source",
                        0,
                        True,
                        True,
                    ),
                ),
            ),
        ),
        alerts=(),
    )
    agent = ReportBlueAgent(corroborated_response=True)
    agent.catalog.update(
        ("Analyse source", "Remove source", "Restore source", "Monitor"),
        (True, True, True, True),
    )
    finding = SimpleNamespace(
        action="temporary_isolate",
        target="source",
        independent_layers=3,
    )
    assert agent._respond(finding, layered) == 2
    assert agent.pending is not None
    assert agent.pending.command == "Restore"


def test_event_aware_verification_uses_recurrence_window():
    spec = SegmentSpec("subnet", ("source",))
    inactive = LayeredObservation(
        mission=0,
        segments=(
            SegmentState(
                spec=spec,
                blocked=(False,) * 9,
                policy=(False,) * 9,
                signals=(
                    HostSignal(
                        spec.subnet,
                        "source",
                        0,
                        False,
                        False,
                    ),
                ),
            ),
        ),
        alerts=(),
    )
    agent = ReportBlueAgent(event_aware_verification=True)
    agent.pending = PendingAction("Remove", "source", 2)
    agent.step = 2
    agent._verify(inactive)
    assert "source" in agent.effect_watches
    assert agent.verified_effects == 0
    agent.step = 20
    agent._verify(inactive)
    assert "source" not in agent.effect_watches
    assert agent.verified_effects == 1
    assert agent.remediations["source"] == 1


def test_event_recurrence_marks_effect_failure():
    spec = SegmentSpec("subnet", ("source",))
    active = LayeredObservation(
        mission=0,
        segments=(
            SegmentState(
                spec=spec,
                blocked=(False,) * 9,
                policy=(False,) * 9,
                signals=(
                    HostSignal(
                        spec.subnet,
                        "source",
                        0,
                        True,
                        False,
                    ),
                ),
            ),
        ),
        alerts=(),
    )
    agent = ReportBlueAgent(event_aware_verification=True)
    agent.effect_watches["source"] = SimpleNamespace(
        command="Remove",
        target="source",
        expires_step=20,
    )
    agent.step = 5
    agent._verify(active)
    assert "source" not in agent.effect_watches
    assert agent.unverified_effects == 1
    assert agent.failed_effects["Remove"] == 1


def test_honeypot_prefers_learned_transition():
    spec = SegmentSpec("subnet", ("source", "a", "b"))
    layered = LayeredObservation(
        mission=0,
        segments=(
            SegmentState(
                spec=spec,
                blocked=(False,) * 9,
                policy=(False,) * 9,
                signals=(
                    HostSignal(spec.subnet, "source", 0, True, False),
                    HostSignal(spec.subnet, "a", 1, False, False),
                    HostSignal(spec.subnet, "b", 2, False, False),
                ),
            ),
        ),
        alerts=(),
    )
    agent = ReportBlueAgent(use_transition_honeypot=True)
    agent.catalog.update(
        ("DeployDecoy a", "DeployDecoy b"),
        (True, True),
    )
    agent.transition_counts[("source", "b")] = 2
    assert agent._honeypot_target("source", layered) == "b"


def test_v11_builds_deception_coverage_without_active_threat():
    spec = SegmentSpec("subnet", ("source", "next"))
    layered = LayeredObservation(
        mission=0,
        segments=(
            SegmentState(
                spec=spec,
                blocked=(False,) * 9,
                policy=(False,) * 9,
                signals=(
                    HostSignal(spec.subnet, "source", 0, False, False),
                    HostSignal(spec.subnet, "next", 1, False, False),
                ),
            ),
        ),
        alerts=(),
    )
    agent = ReportBlueAgent(method_v11=True)
    agent.catalog.update(
        ("DeployDecoy source", "DeployDecoy next", "Monitor"),
        (True, True, True),
    )
    action = agent._proactive_deception(layered)
    assert action in {0, 1}
    assert len(agent.decoyed_hosts) == 1
    assert agent.utility_decisions["coverage"] == 1
