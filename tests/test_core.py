import numpy as np

from wisa_agent.cage.core import (
    ChainTracker,
    HostRisk,
    HostSignal,
    ObservationDecoder,
    SegmentSpec,
    decode_messages,
    encode_message,
)


def test_message_round_trip():
    risk = HostRisk(
        signal=HostSignal(
            subnet="zone",
            hostname="zone_server_host_2",
            host_index=10,
            process=True,
            connection=True,
        ),
        severity=3,
        score=1.0,
        stage="lateral",
        process_streak=2,
        connection_streak=2,
        chain_links=1,
    )
    encoded = encode_message(risk)
    decoded = decode_messages(np.concatenate([encoded, np.zeros(24, dtype=bool)]))
    assert decoded[0].severity == 3
    assert decoded[0].host_index == 10
    assert decoded[0].process
    assert decoded[0].connection


def test_decoder_and_chain_tracker():
    spec = SegmentSpec(
        subnet="zone",
        hosts=("zone_user_host_0", "zone_server_host_0"),
    )
    vector = np.zeros(1 + 27 + 4 + 32, dtype=np.int64)
    vector[1 + 27] = 1
    vector[1 + 27 + 2] = 1
    decoded = ObservationDecoder((spec,)).decode(vector)
    risks = ChainTracker().update(decoded, step=0)
    assert len(risks) == 1
    assert risks[0].severity == 3
