from wisa_agent.cage.red import ChainAwareRedAgent


def test_red_probabilities_are_normalized():
    agent = ChainAwareRedAgent()
    for row in agent.state_transitions_probability.values():
        values = [value for value in row if value is not None]
        assert abs(sum(values) - 1.0) < 1e-9


def test_red_priorities_are_normalized():
    agent = ChainAwareRedAgent()
    assert sum(agent.host_states_priority_list.values()) == 100
