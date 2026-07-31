from types import SimpleNamespace

from experiments.cdm_alert import alert_scores, chain_threshold


def chain(score, confidence=0.8, nodes=("a", "b")):
    predicate = SimpleNamespace(
        confidence=confidence,
        details={"endpoints": nodes},
    )
    return SimpleNamespace(score=score, predicates=(predicate,))


def test_chain_threshold_uses_higher_quantile():
    values = (chain(0.1), chain(0.2), chain(0.3))
    assert chain_threshold(values, 0.5) == 0.2
    assert chain_threshold(()) == 1.0


def test_alert_scores_filters_before_grounded_contribution():
    scores, selected = alert_scores(
        (chain(0.7), chain(0.9, 0.5, ("b", "c"))),
        0.8,
    )
    assert len(selected) == 1
    assert scores == {"b": 0.45, "c": 0.45}
