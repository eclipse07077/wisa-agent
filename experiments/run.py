from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean, pstdev

from CybORG import CybORG
from CybORG.Agents import EnterpriseGreenAgent, FiniteStateRedAgent, SleepAgent
from CybORG.Simulator.Scenarios import EnterpriseScenarioGenerator

from wisa_agent.cage.red import ChainAwareRedAgent
from wisa_agent.cage.teams import build_team
from wisa_agent.cage.telemetry import AttackTelemetry
from wisa_agent.cage.wrapper import MessageRelayEnterpriseMAE


RED_AGENTS = {
    "default": FiniteStateRedAgent,
    "chain": ChainAwareRedAgent,
}


def run_episode(mode: str, red_name: str, seed: int, steps: int) -> dict:
    scenario = EnterpriseScenarioGenerator(
        blue_agent_class=SleepAgent,
        green_agent_class=EnterpriseGreenAgent,
        red_agent_class=RED_AGENTS[red_name],
        steps=steps,
    )
    cyborg = CybORG(scenario, "sim", seed=seed)
    agents = build_team(mode)
    env = MessageRelayEnterpriseMAE(cyborg, agents)
    observations, _ = env.reset()
    telemetry = AttackTelemetry()
    telemetry.reset(cyborg)
    rewards: list[float] = []
    red_actions: Counter[str] = Counter()

    for step in range(1, steps + 1):
        actions = {
            name: agent.get_action(observations[name], env.action_space(name))
            for name, agent in agents.items()
            if name in env.agents
        }
        observations, reward, terminated, truncated, _ = env.step(actions)
        telemetry.observe(cyborg, step)
        rewards.append(mean(reward.values()))
        for name in cyborg.agents:
            if "red" not in name:
                continue
            action_batch = cyborg.get_last_action(name)
            if action_batch is None:
                continue
            if not isinstance(action_batch, list):
                action_batch = [action_batch]
            for action in action_batch:
                if action is None:
                    continue
                red_actions[type(action).__name__] += 1
        if all(
            terminated.get(name, False) or truncated.get(name, False)
            for name in env.agents
        ):
            break

    blue_actions = Counter()
    blue_metrics = []
    for agent in agents.values():
        blue_actions.update(agent.action_counts)
        if hasattr(agent, "metrics"):
            blue_metrics.append(agent.metrics())
    return {
        "seed": seed,
        "reward": sum(rewards),
        "blue_actions": dict(sorted(blue_actions.items())),
        "blue_metrics": blue_metrics,
        "red_actions": dict(sorted(red_actions.items())),
        "attack": telemetry.result(),
    }


def summarize_attack(runs: list[dict]) -> dict:
    metrics = (
        "unique_session_hosts",
        "unique_new_session_hosts",
        "unique_privileged_hosts",
        "unique_new_privileged_hosts",
        "successful_exploit_hosts",
        "unique_impacted_hosts",
        "successful_impact_count",
        "max_concurrent_session_hosts",
        "max_concurrent_privileged_hosts",
        "max_session_lineage_depth",
        "ordered_chain_completions",
        "privileged_to_impact_host_rate",
    )
    summary = {}
    for metric in metrics:
        values = [
            run["attack"][metric]
            for run in runs
            if run["attack"][metric] is not None
        ]
        summary[f"{metric}_mean"] = mean(values) if values else None
        summary[f"{metric}_std"] = pstdev(values) if values else None

    first_impact = [
        run["attack"]["first_successful_impact_step"]
        for run in runs
        if run["attack"]["first_successful_impact_step"] is not None
    ]
    first_session = [
        run["attack"]["first_new_session_step"]
        for run in runs
        if run["attack"]["first_new_session_step"] is not None
    ]
    summary["episodes_with_impact"] = len(first_impact)
    summary["impact_episode_rate"] = len(first_impact) / len(runs)
    summary["first_successful_impact_step_mean"] = (
        mean(first_impact) if first_impact else None
    )
    summary["first_successful_impact_step_std"] = (
        pstdev(first_impact) if first_impact else None
    )
    summary["episodes_with_new_session"] = len(first_session)
    summary["new_session_episode_rate"] = len(first_session) / len(runs)
    summary["first_new_session_step_mean"] = (
        mean(first_session) if first_session else None
    )

    completed = Counter()
    succeeded = Counter()
    failed = Counter()
    for run in runs:
        for action_name, result in run["attack"]["action_results"].items():
            completed[action_name] += result["completed"]
            succeeded[action_name] += result["succeeded"]
            failed[action_name] += result["failed"]
    summary["action_results"] = {
        action_name: {
            "completed": completed[action_name],
            "succeeded": succeeded[action_name],
            "failed": failed[action_name],
            "success_rate": (
                succeeded[action_name] / completed[action_name]
                if completed[action_name]
                else None
            ),
        }
        for action_name in sorted(completed)
    }
    return summary


def summarize(runs: list[dict]) -> dict:
    rewards = [run["reward"] for run in runs]
    blue_actions = Counter()
    red_actions = Counter()
    for run in runs:
        blue_actions.update(run["blue_actions"])
        red_actions.update(run["red_actions"])
    return {
        "episodes": len(runs),
        "reward_mean": mean(rewards),
        "reward_std": pstdev(rewards),
        "reward_min": min(rewards),
        "reward_max": max(rewards),
        "blue_actions": dict(sorted(blue_actions.items())),
        "red_actions": dict(sorted(red_actions.items())),
        "attack": summarize_attack(runs),
        "runs": runs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="CAGE 비교 실험")
    parser.add_argument("--episodes", type=int, default=5)
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--seed", type=int, default=3407)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=(
            "sleep",
            "reactive",
            "layerchain",
            "report",
            "report_v9",
            "report_v10",
            "report_v11",
            "report_v12",
            "report_transition",
            "report_no_chain",
            "report_no_honeypot",
            "report_no_guard",
        ),
        default=("sleep", "reactive", "layerchain"),
    )
    parser.add_argument(
        "--reds",
        nargs="+",
        choices=tuple(RED_AGENTS),
        default=tuple(RED_AGENTS),
    )
    args = parser.parse_args()

    results = {}
    for red_name in args.reds:
        for mode in args.modes:
            key = f"{mode}__{red_name}"
            runs = [
                run_episode(mode, red_name, args.seed + index, args.steps)
                for index in range(args.episodes)
            ]
            results[key] = summarize(runs)
            print(
                key,
                results[key]["reward_mean"],
                results[key]["reward_std"],
                flush=True,
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
