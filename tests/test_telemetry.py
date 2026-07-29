from ipaddress import IPv4Address
from types import SimpleNamespace

from wisa_agent.cage.telemetry import AttackTelemetry


class Session:
    def __init__(
        self,
        ident,
        hostname,
        username,
        parent=None,
        active=True,
        name=None,
    ):
        self.ident = ident
        self.hostname = hostname
        self.username = username
        self.parent = parent
        self.active = active
        self.name = name

    def has_privileged_access(self):
        return self.username in {"root", "SYSTEM"}


class FakeCyborg:
    def __init__(self):
        self.environment_controller = SimpleNamespace(
            state=SimpleNamespace(
                sessions={
                    "red_agent_0": {
                        0: Session(0, "root_host", "root"),
                    }
                }
            )
        )
        self.observations = {}

    def get_agent_ids(self):
        return ["blue_agent_0", "red_agent_0"]

    def get_ip_map(self):
        return {
            "root_host": IPv4Address("10.0.0.1"),
            "target_host": IPv4Address("10.0.0.2"),
        }

    def get_observation(self, agent_name):
        return self.observations[agent_name]


def action(name, **attributes):
    instance = type(name, (), {})()
    for attribute, value in attributes.items():
        setattr(instance, attribute, value)
    return instance


def test_attack_chain_and_session_metrics():
    cyborg = FakeCyborg()
    telemetry = AttackTelemetry()
    telemetry.reset(cyborg)

    cyborg.observations["red_agent_0"] = {
        "action": action(
            "AggressiveServiceDiscovery",
            ip_address=IPv4Address("10.0.0.2"),
        ),
        "success": True,
    }
    telemetry.observe(cyborg, 2)

    cyborg.environment_controller.state.sessions["red_agent_0"][1] = Session(
        1,
        "target_host",
        "user",
        parent=0,
    )
    cyborg.observations["red_agent_0"] = {
        "action": action(
            "ExploitRemoteService",
            ip_address=IPv4Address("10.0.0.2"),
        ),
        "success": True,
    }
    telemetry.observe(cyborg, 4)

    cyborg.environment_controller.state.sessions["red_agent_0"][1].username = "root"
    cyborg.observations["red_agent_0"] = {
        "action": action("PrivilegeEscalate", hostname="target_host"),
        "success": True,
    }
    telemetry.observe(cyborg, 6)

    cyborg.observations["red_agent_0"] = {
        "action": action("Impact", hostname="target_host"),
        "success": True,
    }
    telemetry.observe(cyborg, 8)
    result = telemetry.result()

    assert result["unique_new_session_hosts"] == 1
    assert result["unique_new_privileged_hosts"] == 1
    assert result["max_session_lineage_depth"] == 1
    assert result["first_new_session_step"] == 4
    assert result["first_successful_impact_step"] == 8
    assert result["ordered_chain_completions"] == 1
    assert result["privileged_to_impact_host_rate"] == 0.5
    assert result["action_results"]["Impact"]["success_rate"] == 1.0


def test_failed_action_does_not_advance_chain():
    cyborg = FakeCyborg()
    telemetry = AttackTelemetry()
    telemetry.reset(cyborg)
    cyborg.observations["red_agent_0"] = {
        "action": action("Impact", hostname="root_host"),
        "success": False,
    }
    telemetry.observe(cyborg, 3)
    result = telemetry.result()

    assert result["successful_impact_count"] == 0
    assert result["ordered_chain_completions"] == 0
    assert result["action_results"]["Impact"]["failed"] == 1
