from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path

from wisa_agent.method import ChainBuilder
from wisa_agent.tc.cdm_agent import (
    CDMAttackAgent,
    NormalProfile,
    RELATION_STAGE,
    validation_threshold,
)

from cdm import TRAIN_DAYS, VALIDATION_DAYS, events


def normalized_context(left, right) -> float:
    def values(predicate) -> frozenset[str]:
        context = {
            item
            for item in predicate.context
            if not item.startswith(("source:", "target:"))
        }
        context.update(
            f"entity:{node}" for node in predicate.details["endpoints"]
        )
        return frozenset(context)

    left_context = values(left)
    right_context = values(right)
    return len(left_context & right_context) / len(
        left_context | right_context
    )


def diagnose(agent, eligible, limit: int) -> dict:
    agent.candidate_limit = limit
    selected = agent._select(eligible)
    predicates = [
        agent._predicate(index, item)
        for index, item in enumerate(selected)
    ]
    endpoints = {
        predicate.predicate_id: frozenset(predicate.details["endpoints"])
        for predicate in predicates
    }
    builder = ChainBuilder(
        edge_threshold=0.58,
        max_length=5,
        time_window=18.0,
    )
    stages = Counter(
        RELATION_STAGE[item.event.relation].value for item in selected
    )
    stage_pairs = Counter()
    passing_pairs = Counter()
    temporal_pairs = 0
    compatible_pairs = 0
    passing_edges = 0
    normalized_edges = 0
    maximum_edge = 0.0
    ordered = sorted(predicates, key=lambda item: item.timestamp or 0.0)
    for index, left in enumerate(ordered):
        for right in ordered[index + 1 :]:
            if (right.timestamp or 0.0) - (left.timestamp or 0.0) > 18.0:
                break
            temporal_pairs += 1
            if not (
                endpoints[left.predicate_id]
                & endpoints[right.predicate_id]
            ):
                continue
            compatible_pairs += 1
            pair = (left.stage.value, right.stage.value)
            stage_pairs[pair] += 1
            edge = builder.edge(left, right)
            if edge is not None:
                maximum_edge = max(maximum_edge, edge.score)
                if edge.score >= 0.58:
                    passing_edges += 1
                    passing_pairs[pair] += 1
            normalized = builder.edge(
                left,
                right,
                normalized_context(left, right),
            )
            if normalized is not None and normalized.score >= 0.58:
                normalized_edges += 1
    compatible = lambda left, right: bool(
        endpoints[left.predicate_id] & endpoints[right.predicate_id]
    )
    current_chains = builder.build(
        predicates,
        compatible=compatible,
    )
    normalized_chains = builder.build(
        predicates,
        compatible=compatible,
        context_score=normalized_context,
    )
    return {
        "selected": len(selected),
        "stages": stages,
        "temporal_pairs": temporal_pairs,
        "compatible_pairs": compatible_pairs,
        "passing_edges": passing_edges,
        "normalized_edges": normalized_edges,
        "maximum_edge": maximum_edge,
        "stage_pairs": {
            "->".join(pair): count for pair, count in stage_pairs.items()
        },
        "passing_pairs": {
            "->".join(pair): count for pair, count in passing_pairs.items()
        },
        "chains": len(current_chains),
        "normalized_chains": len(normalized_chains),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--days", nargs="+", type=int, default=[2])
    parser.add_argument(
        "--limits",
        nargs="+",
        type=int,
        default=[256, 512, 1024, 2048],
    )
    args = parser.parse_args()

    connection = sqlite3.connect(f"file:{args.database}?mode=ro", uri=True)
    profile = NormalProfile()
    profile.fit(events(connection, TRAIN_DAYS))
    threshold = validation_threshold(
        profile,
        events(connection, VALIDATION_DAYS),
    )
    agent = CDMAttackAgent(profile, threshold)
    result = {
        "threshold": threshold,
        "days": {},
    }
    for day in args.days:
        eligible = [
            item
            for item in agent._score_stream(events(connection, (day,)))
            if item.score >= threshold
        ]
        result["days"][str(day)] = {
            "eligible": len(eligible),
            "limits": {
                str(limit): diagnose(agent, eligible, limit)
                for limit in args.limits
            },
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
