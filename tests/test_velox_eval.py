import sqlite3

from experiments.velox_chain import load_loss_scores
from experiments.velox_eval import matched_budget, selected_metrics


def test_selected_metrics_ignores_nodes_outside_universe():
    result = selected_metrics(
        {"a", "b", "c", "d"},
        {"a", "d", "z"},
        {"a", "b", "z"},
    )
    assert result["reported"] == 2
    assert result["tp"] == 1
    assert result["fp"] == 1
    assert result["fn"] == 1
    assert result["tn"] == 1


def test_matched_budget_uses_label_free_uuid_tie_break():
    selected, audit = matched_budget(
        {
            "a": 3.0,
            "b": 2.0,
            "c": 2.0,
            "d": 2.0,
            "e": 1.0,
        },
        3,
    )
    assert selected == {"a", "c", "d"}
    assert audit == {
        "cutoff": 2.0,
        "strictly_above": 1,
        "tied_at_cutoff": 3,
        "selected_from_tie": 2,
    }


def test_loss_scores_match_official_node_maximum_reduction(tmp_path):
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "create table node_index(index_id text primary key, uuid text)"
    )
    connection.executemany(
        "insert into node_index values(?, ?)",
        (("1", "A"), ("2", "B"), ("3", "C")),
    )
    losses = tmp_path / "losses"
    losses.mkdir()
    (losses / "one.csv").write_text(
        "loss,srcnode,dstnode,time\n"
        "0.2,1,2,1\n"
        "0.8,1,3,2\n",
        encoding="utf-8",
    )
    scores, digest, files = load_loss_scores(losses, connection)
    assert scores == {"A": 0.8, "B": 0.2, "C": 0.8}
    assert len(digest) == 64
    assert files == 1
