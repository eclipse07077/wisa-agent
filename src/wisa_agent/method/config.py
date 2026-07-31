ANOMALY_WEIGHTS = {
    "structural": 0.50,
    "trace": 0.30,
    "path": 0.20,
}
EDGE_WEIGHTS = {
    "time": 0.30,
    "context": 0.30,
    "stage": 0.25,
    "mission": 0.15,
}
CHAIN_WEIGHTS = {
    "edge": 0.55,
    "confidence": 0.20,
    "severity": 0.05,
    "stages": 0.06,
    "mission": 0.08,
}
RULE_RISK_WEIGHTS = {
    "confidence": 0.35,
    "severity": 0.25,
    "correlation": 0.25,
    "criticality": 0.15,
}
DEVIATION_RISK_WEIGHTS = {
    "anomaly": 0.50,
    "correlation": 0.30,
    "criticality": 0.20,
}
EDGE_THRESHOLD = 0.58
TRACE_WINDOW = 18.0
MIN_CHAIN_LENGTH = 3
MAX_CHAIN_LENGTH = 5
MIN_CHAIN_STAGES = 3
MAX_OUTGOING_EDGES = 5
TC_PREDICATE_LIMIT = 2048
TC_CHAIN_LIMIT = 48
VALIDATION_QUANTILE = 0.995
MONITOR_THRESHOLD = 0.50
HONEYPOT_THRESHOLD = 0.70
STRONG_RESPONSE_THRESHOLD = 0.85
MISSION_CRITICALITY = 0.85
BELIEF_DECAY = 0.80
MIN_STRONG_EVIDENCE = 0.50
HIGH_RESPONSE_EVIDENCE = 0.75
COVERAGE_UTILITY = 0.25
MISSION_UTILITY_BONUS = 0.15
MMR_PENALTY = 0.25
CONNECTOR_LOCAL_WEIGHT = 0.65
CONNECTOR_PERSISTENCE_WEIGHT = 0.35
ROBUST_OUTLIER_SCALE = 3.0
ACTION_ATTRIBUTES = {
    "monitor": (0.05, 0.15, 0.00, 0.00, 1.00),
    "analyse": (0.15, 0.85, 0.00, 0.05, 1.00),
    "honeypot": (0.35, 0.70, 1.00, 0.10, 0.95),
    "temporary_isolate": (0.80, 0.10, 0.00, 0.35, 0.75),
    "restore": (0.95, 0.05, 0.00, 0.55, 0.45),
    "block": (0.90, 0.05, 0.00, 0.50, 0.55),
}
