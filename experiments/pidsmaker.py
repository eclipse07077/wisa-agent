import argparse
import random
import runpy
import sys
from pathlib import Path


def label_access_guard(event: str, args: tuple) -> None:
    if event != "open" or not args:
        return
    try:
        path = str(args[0]).lower()
    except (TypeError, ValueError):
        return
    if "ground_truth" in path:
        raise RuntimeError(f"label access blocked: {args[0]}")


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--db-host", required=True)
    parser.add_argument("--db-user", required=True)
    parser.add_argument("--db-password", default="")
    parser.add_argument("--db-port", default="5432")
    parser.add_argument("--db-name")
    parser.add_argument("--skip-label-tasks", action="store_true")
    parser.add_argument(
        "--stop-after",
        choices=("build_graphs", "gnn_training"),
    )
    return parser.parse_known_args()


def main() -> None:
    args, remaining = parse_args()
    source = args.repo.resolve() / "src"
    benchmark = source / "benchmark.py"
    if not benchmark.is_file():
        raise FileNotFoundError(benchmark)

    args.artifacts.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(source))
    if args.skip_label_tasks:
        sys.addaudithook(label_access_guard)

    import config

    config.ROOT_ARTIFACT_DIR = f"{args.artifacts.resolve()}/"
    config.DATABASE_DEFAULT_CONFIG.update(
        host=args.db_host,
        user=args.db_user,
        password=args.db_password,
        port=args.db_port,
    )
    if args.db_name is not None:
        if len(remaining) < 2:
            raise ValueError("PIDSMaker dataset argument is missing")
        dataset = remaining[1]
        config.DATASET_DEFAULT_CONFIG[dataset]["database"] = args.db_name
        config.DATASET_DEFAULT_CONFIG[dataset]["database_all_file"] = (
            args.db_name
        )
    if args.skip_label_tasks:
        from detection import evaluation
        from triage import tracing

        evaluation.main = lambda cfg: {}
        tracing.main = lambda cfg: {}
    sys.argv = [str(benchmark), *remaining]
    if args.stop_after is None:
        runpy.run_path(str(benchmark), run_name="__main__")
        return

    import numpy as np
    import torch
    import wandb
    import benchmark as official
    from config import (
        get_runtime_required_args,
        get_yml_cfg,
        set_task_to_done,
        update_task_paths_to_restart,
    )

    runtime_args, unknown = get_runtime_required_args(
        return_unknown_args=True
    )
    if unknown:
        raise ValueError(f"unknown PIDSMaker arguments: {unknown}")
    cfg = get_yml_cfg(runtime_args)
    if cfg.detection.gnn_training.use_seed:
        random.seed(0)
        np.random.seed(0)
        torch.manual_seed(0)
        torch.cuda.manual_seed_all(0)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    wandb.init(mode="disabled")
    for task, values in official.get_task_to_module(cfg).items():
        restart = update_task_paths_to_restart(cfg)
        if restart[task]:
            values["module"].main(cfg)
            set_task_to_done(values["task_path"])
        if task == args.stop_after:
            break
    wandb.finish()


if __name__ == "__main__":
    main()
