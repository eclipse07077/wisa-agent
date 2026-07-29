from CybORG.Agents.SimpleAgents.FiniteStateRedAgent import FiniteStateRedAgent


class ChainAwareRedAgent(FiniteStateRedAgent):
    def __init__(self, name=None, np_random=None, agent_subnets=None):
        super().__init__(
            name=name,
            np_random=np_random,
            agent_subnets=agent_subnets,
        )
        self.prioritise_servers = False

    def set_host_state_priority_list(self):
        return {
            "K": 8,
            "KD": 7,
            "S": 12,
            "SD": 10,
            "U": 18,
            "UD": 15,
            "R": 17,
            "RD": 13,
        }

    def state_transitions_probability(self):
        return {
            "K": [0.35, 0.55, 0.10, None, None, None, None, None, None],
            "KD": [None, 0.70, 0.30, None, None, None, None, None, None],
            "S": [0.20, None, None, 0.10, 0.70, None, None, None, None],
            "SD": [None, None, None, 0.10, 0.90, None, None, None, None],
            "U": [0.15, None, None, None, None, 0.83, None, None, 0.02],
            "UD": [0.05, None, None, None, None, 0.95, None, None, 0.00],
            "R": [0.25, None, None, None, None, None, 0.25, 0.50, 0.00],
            "RD": [0.10, None, None, None, None, None, 0.30, 0.60, 0.00],
        }
