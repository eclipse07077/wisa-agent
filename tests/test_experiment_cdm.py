import csv
import sqlite3

from experiments.cdm import DATASETS, events, ground_truth


def write_labels(path, values):
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows((value,) for value in values)


def test_theia_ground_truth_is_mapped_by_attack_day(tmp_path):
    write_labels(
        tmp_path / "node_Firefox_Backdoor_Drakon_In_Memory.csv",
        ("firefox",),
    )
    write_labels(
        tmp_path / "node_Browser_Extension_Drakon_Dropper.csv",
        ("browser",),
    )
    labels, by_day = ground_truth(tmp_path, DATASETS["theia"])
    assert labels == {"FIREFOX", "BROWSER"}
    assert by_day == {
        10: {"FIREFOX"},
        12: {"BROWSER"},
        13: set(),
    }


def test_cadets_ground_truth_preserves_empty_day(tmp_path):
    write_labels(tmp_path / "node_Nginx_Backdoor_06.csv", ("six",))
    write_labels(tmp_path / "node_Nginx_Backdoor_12.csv", ("twelve",))
    write_labels(tmp_path / "node_Nginx_Backdoor_13.csv", ("thirteen",))
    labels, by_day = ground_truth(tmp_path, DATASETS["cadets"])
    assert labels == {"SIX", "TWELVE", "THIRTEEN"}
    assert by_day[11] == set()


def test_clearscope_e5_ground_truth_keeps_attack_free_day(tmp_path):
    write_labels(
        tmp_path / "node_clearscope_e5_appstarter_0515.csv",
        ("appstarter",),
    )
    write_labels(
        tmp_path / "node_clearscope_e5_lockwatch_0517.csv",
        ("lockwatch",),
    )
    write_labels(
        tmp_path / "node_clearscope_e5_tester_0517.csv",
        ("tester",),
    )
    labels, by_day = ground_truth(tmp_path, DATASETS["clearscope_e5"])
    assert labels == {"APPSTARTER", "LOCKWATCH", "TESTER"}
    assert by_day[14] == set()


def test_optc_h051_uses_official_temporal_split():
    dataset = DATASETS["optc_h051"]
    assert dataset.train == (19, 20, 21)
    assert dataset.validation == (22,)
    assert dataset.test == (23, 24, 25)


def test_events_can_blank_paths_without_changing_other_fields():
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        create table nodes(uuid text primary key, kind text);
        create table events(
            day integer,
            timestamp integer,
            source text,
            target text,
            relation text,
            path text
        );
        insert into nodes values ('A', 'subject'), ('B', 'file');
        insert into events values (6, 10, 'A', 'B', 'EVENT_OPEN', '/tmp/a');
        """
    )
    original = list(events(connection, (6,)))[0]
    blanked = list(events(connection, (6,), drop_path=True))[0]
    assert original.path == "/tmp/a"
    assert blanked.path == ""
    assert original.timestamp == blanked.timestamp
    assert original.source == blanked.source
    assert original.target == blanked.target
    assert original.relation == blanked.relation
    assert original.source_kind == blanked.source_kind
    assert original.target_kind == blanked.target_kind
