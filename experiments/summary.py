from __future__ import annotations

import argparse
import csv
import json
from math import sqrt
from pathlib import Path
from statistics import mean, stdev


CSV_METRICS = (
    "unique_new_session_hosts",
    "unique_privileged_hosts",
    "successful_exploit_hosts",
    "unique_impacted_hosts",
    "successful_impact_count",
    "first_successful_impact_step",
    "ordered_chain_completions",
)


def compact_condition(condition: dict) -> dict:
    return {
        key: value
        for key, value in condition.items()
        if key != "runs"
    }


def comparison(condition: dict, layerchain: dict) -> dict:
    baseline_reward = abs(condition["reward_mean"])
    layerchain_reward = abs(layerchain["reward_mean"])
    baseline_attack = condition["attack"]
    layerchain_attack = layerchain["attack"]
    reductions = {}
    for metric in (
        "unique_new_session_hosts",
        "unique_privileged_hosts",
        "successful_impact_count",
        "ordered_chain_completions",
    ):
        baseline = baseline_attack[f"{metric}_mean"]
        candidate = layerchain_attack[f"{metric}_mean"]
        reductions[f"{metric}_reduction_pct"] = (
            100 * (1 - candidate / baseline) if baseline else None
        )
    baseline_runs = {run["seed"]: run for run in condition["runs"]}
    layerchain_runs = {run["seed"]: run for run in layerchain["runs"]}
    paired_gains = [
        layerchain_runs[seed]["reward"] - baseline_runs[seed]["reward"]
        for seed in sorted(baseline_runs.keys() & layerchain_runs.keys())
    ]
    gain_mean = mean(paired_gains)
    gain_std = stdev(paired_gains) if len(paired_gains) > 1 else 0.0
    margin = 1.96 * gain_std / sqrt(len(paired_gains))
    return {
        "reward_penalty_reduction_pct": (
            100 * (1 - layerchain_reward / baseline_reward)
            if baseline_reward
            else None
        ),
        "paired_reward_gain_mean": gain_mean,
        "paired_reward_gain_std": gain_std,
        "paired_reward_gain_ci95_approx": [gain_mean - margin, gain_mean + margin],
        "paired_reward_win_rate": (
            sum(value > 0 for value in paired_gains) / len(paired_gains)
        ),
        **reductions,
    }


def csv_row(key: str, condition: dict) -> dict:
    mode, red = key.split("__", 1)
    attack = condition["attack"]
    row = {
        "condition": key,
        "blue_mode": mode,
        "red_agent": red,
        "episodes": condition["episodes"],
        "reward_mean": condition["reward_mean"],
        "reward_std": condition["reward_std"],
        "impact_episode_rate": attack["impact_episode_rate"],
    }
    for metric in CSV_METRICS:
        row[f"{metric}_mean"] = attack[f"{metric}_mean"]
        row[f"{metric}_std"] = attack.get(f"{metric}_std")
    for action_name in (
        "ExploitRemoteService",
        "PrivilegeEscalate",
        "Impact",
    ):
        result = attack["action_results"].get(action_name, {})
        row[f"{action_name}_completed"] = result.get("completed", 0)
        row[f"{action_name}_succeeded"] = result.get("succeeded", 0)
        row[f"{action_name}_success_rate"] = result.get("success_rate")
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="CAGE 결과 요약")
    parser.add_argument("input", type=Path)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--csv-output", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--seed", type=int, default=3407)
    parser.add_argument(
        "--cage-commit",
        default="8c3c50ca54b176c2de199847944e8dcc035497e3",
    )
    args = parser.parse_args()

    raw = json.loads(args.input.read_text(encoding="utf-8"))
    compact = {
        key: compact_condition(value)
        for key, value in raw.items()
    }
    episodes = next(iter(compact.values()))["episodes"]
    comparisons = {}
    for red in ("default", "chain"):
        layerchain = raw[f"layerchain__{red}"]
        for baseline in ("sleep", "reactive"):
            comparisons[f"layerchain_vs_{baseline}__{red}"] = comparison(
                raw[f"{baseline}__{red}"],
                layerchain,
            )
    summary = {
        "benchmark": "CAGE Challenge 4",
        "cage_commit": args.cage_commit,
        "episodes_per_condition": episodes,
        "steps_per_episode": args.steps,
        "seed_start": args.seed,
        "seed_end": args.seed + episodes - 1,
        "reward_direction": "closer_to_zero_is_better",
        "conditions": compact,
        "comparisons": comparisons,
    }
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.csv_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    rows = [csv_row(key, value) for key, value in compact.items()]
    with args.csv_output.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
