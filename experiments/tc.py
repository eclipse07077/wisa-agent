from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

from wisa_agent.tc import LayerModel, ProvenanceAttackAgent, ProvenanceGraph


def load_graph(path: Path):
    with path.open("rb") as handle:
        return pickle.load(handle)


def arrays(graph) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    node_types = graph.ndata["type"].detach().cpu().numpy().reshape(-1)
    source, target = graph.edges()
    edges = np.column_stack(
        (
            source.detach().cpu().numpy(),
            target.detach().cpu().numpy(),
        )
    ).astype(np.int64)
    edge_types = graph.edata["type"].detach().cpu().numpy().reshape(-1)
    return node_types, edges, edge_types


def load_magic(root: Path, dataset: str):
    data = root / "data" / dataset
    metadata = json.loads((data / "metadata.json").read_text())
    train = []
    for index in range(metadata["n_train"]):
        node_types, edges, _ = arrays(load_graph(data / f"train{index}.pkl"))
        train.append((node_types, edges))

    test_arrays = [
        arrays(load_graph(data / f"test{index}.pkl"))
        for index in range(metadata["n_test"])
    ]
    offsets = np.cumsum([0] + [len(item[0]) for item in test_arrays[:-1]])
    node_types = np.concatenate([item[0] for item in test_arrays])
    edges = np.concatenate(
        [item[1] + offset for item, offset in zip(test_arrays, offsets)]
    )
    edge_types = np.concatenate([item[2] for item in test_arrays])
    labels = np.zeros(len(node_types), dtype=np.int8)
    labels[np.asarray(metadata["malicious"][0], dtype=np.int64)] = 1

    skipped = sum(len(item[0]) for item in test_arrays[:-1])
    evaluation_mask = np.arange(len(node_types)) >= skipped
    evaluation_mask[np.flatnonzero(labels)] = True
    with (root / "eval_result" / f"distance_save_{dataset}.pkl").open("rb") as handle:
        mean_distance, distances = pickle.load(handle)
    selected_scores = np.asarray(distances, dtype=float) / float(mean_distance)
    if selected_scores.shape[0] != int(evaluation_mask.sum()):
        raise ValueError(
            f"score count mismatch: {selected_scores.shape[0]} != {evaluation_mask.sum()}"
        )
    scores = np.zeros(len(node_types), dtype=float)
    scores[evaluation_mask] = selected_scores
    graph = ProvenanceGraph(
        node_types=node_types,
        edges=edges,
        edge_types=edge_types,
        scores=scores,
        evaluation_mask=evaluation_mask,
    )
    return train, graph, labels


def metrics(labels: np.ndarray, scores: np.ndarray, mask: np.ndarray) -> dict:
    y = labels[mask]
    value = scores[mask]
    result = {
        "auroc": roc_auc_score(y, value),
        "ap": average_precision_score(y, value),
    }
    ranked = np.argsort(value, kind="stable")[::-1]
    positives = max(int(y.sum()), 1)
    for budget in (100, 500, 1000):
        selected = ranked[: min(budget, len(ranked))]
        true_positive = int(y[selected].sum())
        result[f"precision_at_{budget}"] = true_positive / max(len(selected), 1)
        result[f"recall_at_{budget}"] = true_positive / positives
    return result


def chain_metrics(
    labels: np.ndarray,
    base_scores: np.ndarray,
    chain_nodes: tuple[int, ...],
    evaluation_mask: np.ndarray,
) -> dict:
    selected = np.asarray(
        [node for node in chain_nodes if evaluation_mask[node]],
        dtype=np.int64,
    )
    count = len(selected)
    if count == 0:
        return {
            "reported_nodes": 0,
            "precision": 0.0,
            "recall": 0.0,
            "matched_baseline_precision": 0.0,
            "matched_baseline_recall": 0.0,
        }
    true_positive = int(labels[selected].sum())
    candidates = np.flatnonzero(evaluation_mask)
    ranked = candidates[
        np.argsort(base_scores[candidates], kind="stable")[::-1][:count]
    ]
    baseline_true_positive = int(labels[ranked].sum())
    positives = max(int(labels[evaluation_mask].sum()), 1)
    return {
        "reported_nodes": count,
        "precision": true_positive / count,
        "recall": true_positive / positives,
        "matched_baseline_precision": baseline_true_positive / count,
        "matched_baseline_recall": baseline_true_positive / positives,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument(
        "--datasets",
        nargs="+",
        choices=("cadets", "theia", "trace"),
        default=("cadets",),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = {}
    for dataset in args.datasets:
        train, graph, labels = load_magic(args.root, dataset)
        layer_model = LayerModel.fit(train)
        output = ProvenanceAttackAgent(layer_model).run(graph)
        global_output = ProvenanceAttackAgent(
            layer_model,
            balance_layers=False,
        ).run(graph)
        result[dataset] = {
            "base": metrics(labels, output.base_scores, graph.evaluation_mask),
            "full": metrics(labels, output.scores, graph.evaluation_mask),
            "global_seed": metrics(
                labels,
                global_output.scores,
                graph.evaluation_mask,
            ),
            "chains": chain_metrics(
                labels,
                output.base_scores,
                output.chain_nodes,
                graph.evaluation_mask,
            ),
            "global_seed_chains": chain_metrics(
                labels,
                global_output.base_scores,
                global_output.chain_nodes,
                graph.evaluation_mask,
            ),
            "chain_count": len(output.chains),
            "global_seed_chain_count": len(global_output.chains),
            "predicate_count": len(output.predicates),
            "layers": {str(key): value for key, value in output.layers.items()},
        }
        print(dataset, json.dumps(result[dataset], ensure_ascii=False), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
