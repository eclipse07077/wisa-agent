from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import linear_sum_assignment

from wisa_agent.tc.ravel import TransportEdge
from wisa_agent.tc.transport import exact_transport


WEIGHTS = (0.0, 0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0)


def check(
    trials: int,
    seed: int,
    max_roots: int,
    max_shared: int,
) -> dict:
    generator = random.Random(seed)
    for trial in range(trials):
        root_count = generator.randint(2, max_roots)
        shared_count = generator.randint(1, max_shared)
        roots = tuple(f"r{index:03d}" for index in range(root_count))
        shared = tuple(
            f"n{index:03d}"
            for index in range(shared_count)
        )
        nodes = shared + roots
        node_index = {
            node: index
            for index, node in enumerate(nodes)
        }
        matrix = np.full(
            (root_count, len(nodes)),
            -1e12,
            dtype=float,
        )
        edges = []
        for root_index, root in enumerate(roots):
            edges.append(
                TransportEdge(root, root, 0.0, 1.0, 0, "local")
            )
            matrix[root_index, node_index[root]] = 0.0
            for node in shared:
                if generator.random() >= 0.35:
                    continue
                utility = generator.choice(WEIGHTS)
                edges.append(
                    TransportEdge(
                        root,
                        node,
                        utility,
                        1.0,
                        1,
                        "proof",
                    )
                )
                matrix[root_index, node_index[node]] = utility
        selected = exact_transport(edges, roots)
        own_objective = sum(edge.utility for edge in selected)
        rows, columns = linear_sum_assignment(
            matrix,
            maximize=True,
        )
        reference_objective = float(matrix[rows, columns].sum())
        if not math.isclose(
            own_objective,
            reference_objective,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise RuntimeError(
                f"objective mismatch at trial {trial}"
            )
    return {
        "method": "transport_cross_solver_check_v1",
        "seed": seed,
        "trials": trials,
        "max_roots": max_roots,
        "max_shared_nodes": max_shared,
        "edge_probability": 0.35,
        "weights": WEIGHTS,
        "reference": "scipy.optimize.linear_sum_assignment",
        "scipy": scipy.__version__,
        "matched": trials,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260731)
    parser.add_argument("--max-roots", type=int, default=15)
    parser.add_argument("--max-shared", type=int, default=20)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if (
        args.trials < 1
        or args.max_roots < 2
        or args.max_shared < 1
    ):
        raise ValueError("invalid check size")
    result = check(
        args.trials,
        args.seed,
        args.max_roots,
        args.max_shared,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
