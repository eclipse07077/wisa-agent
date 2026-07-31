from pathlib import Path

from wisa_agent.tc.cdm_agent import (
    CDMAttackAgent,
    EventScore,
    NormalProfile,
    ProvenanceEvent,
)
from wisa_agent.tc.pairwise import PairwiseSeedDetector


def event(
    timestamp: int,
    source: str,
    target: str,
    relation: str,
    path: str,
    source_kind: str,
    target_kind: str,
) -> ProvenanceEvent:
    return ProvenanceEvent(
        timestamp,
        source,
        target,
        relation,
        path,
        source_kind,
        target_kind,
    )


def test_pairwise_detector_calibrates_and_round_trips(tmp_path: Path):
    training = [
        event(
            index,
            "file",
            "process",
            "EVENT_OPEN",
            "/usr/lib/libc.so",
            "file",
            "subject",
        )
        for index in range(64)
    ]
    detector = PairwiseSeedDetector(
        seed=1,
        token_buckets=64,
    )
    result = detector.fit(training, batch_size=16)
    calibration = detector.calibrate(training, batch_size=16)
    scores = list(detector.iter_scores(training, batch_size=16))
    checkpoint = tmp_path / "pairwise.pt"
    detector.save(checkpoint)
    restored = PairwiseSeedDetector.load(checkpoint)
    restored_scores = list(restored.iter_scores(training, batch_size=16))
    assert result["events"] == 64
    assert calibration.count == 64
    assert [item.score for item in scores] == [
        item.score for item in restored_scores
    ]


def test_seeded_attribution_keeps_seeds_and_causal_connector():
    raw = [
        event(
            10_000_000_000,
            "process",
            "flow",
            "EVENT_CONNECT",
            "",
            "subject",
            "netflow",
        ),
        event(
            11_000_000_000,
            "binary",
            "process",
            "EVENT_EXECUTE",
            "/tmp/tool",
            "file",
            "subject",
        ),
        event(
            12_000_000_000,
            "config",
            "process",
            "EVENT_OPEN",
            "/tmp/config",
            "file",
            "subject",
        ),
        event(
            13_000_000_000,
            "process",
            "output",
            "EVENT_WRITE",
            "/tmp/output",
            "subject",
            "file",
        ),
    ]
    scored = [
        EventScore(
            item,
            0.99 if index == 0 else 0.2,
            0.99 if index == 0 else 0.2,
            0.0,
            0.0,
        )
        for index, item in enumerate(raw)
    ]
    profile = NormalProfile()
    profile.fit(raw)
    result = CDMAttackAgent(
        profile,
        threshold=0.9,
        candidate_limit=32,
        predicate_mode="trace",
        attribution_mode="seeded",
    ).run_scored(scored)
    assert result.chains
    assert {"process", "flow"} <= set(result.chain_scores)
    assert not {"binary", "config", "output"} & set(result.chain_scores)
