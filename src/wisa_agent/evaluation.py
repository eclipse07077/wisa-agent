from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PairedResult:
    count: int
    mean_difference: float
    standard_deviation: float
    confidence_interval: tuple[float, float]
    effect_size: float
    win_rate: float


def paired_result(
    reference: dict[int, float],
    candidate: dict[int, float],
    bootstrap_samples: int = 10000,
    seed: int = 20260729,
) -> PairedResult:
    common = sorted(set(reference) & set(candidate))
    if not common:
        raise ValueError("paired observations are empty")
    differences = np.asarray(
        [candidate[item] - reference[item] for item in common],
        dtype=float,
    )
    deviation = float(
        differences.std(ddof=1) if len(differences) > 1 else 0.0
    )
    generator = np.random.default_rng(seed)
    samples = generator.choice(
        differences,
        size=(bootstrap_samples, len(differences)),
        replace=True,
    ).mean(axis=1)
    low, high = np.quantile(samples, (0.025, 0.975))
    average = float(differences.mean())
    effect = average / deviation if deviation > 0 else 0.0
    return PairedResult(
        count=len(common),
        mean_difference=average,
        standard_deviation=deviation,
        confidence_interval=(float(low), float(high)),
        effect_size=float(effect),
        win_rate=float((differences > 0).mean()),
    )
