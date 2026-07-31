from __future__ import annotations

import hashlib
import inspect
import json
from math import isclose
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def load(name: str) -> dict:
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def equal(left: float, right: float) -> None:
    assert isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-12)


def equal_sequence(left: list[float], right: list[float]) -> None:
    assert len(left) == len(right)
    for left_value, right_value in zip(left, right):
        equal(left_value, right_value)


def malicious_nodes(reported_nodes: int, precision: float) -> int:
    return round(reported_nodes * precision)


def check_attack(summary: dict, raw: dict) -> None:
    aggregate = raw["aggregate"]
    equal(summary["baseline"]["auroc"], aggregate["base"]["auroc"])
    equal(summary["baseline"]["ap"], aggregate["base"]["ap"])
    equal(summary["grounded_trace"]["auroc"], aggregate["full"]["auroc"])
    equal(summary["grounded_trace"]["ap"], aggregate["full"]["ap"])
    assert (
        summary["grounded_trace"]["reported_nodes"]
        == aggregate["chains"]["reported_nodes"]
    )
    assert summary["grounded_trace"]["malicious_nodes"] == malicious_nodes(
        aggregate["chains"]["reported_nodes"],
        aggregate["chains"]["precision"],
    )
    equal(
        summary["grounded_trace"]["precision"],
        aggregate["chains"]["precision"],
    )
    equal(
        summary["grounded_trace"]["recall"],
        aggregate["chains"]["recall"],
    )
    equal(
        summary["matched_anomaly_only"]["precision"],
        aggregate["chains"]["matched_baseline_precision"],
    )
    equal(
        summary["matched_anomaly_only"]["recall"],
        aggregate["chains"]["matched_baseline_recall"],
    )
    assert (
        summary["matched_anomaly_only"]["reported_nodes"]
        == aggregate["chains"]["reported_nodes"]
    )
    assert summary["matched_anomaly_only"]["malicious_nodes"] == malicious_nodes(
        aggregate["chains"]["reported_nodes"],
        aggregate["chains"]["matched_baseline_precision"],
    )
    for count in (100, 500, 1000):
        equal(
            aggregate["base"][f"precision_at_{count}"],
            aggregate["full"][f"precision_at_{count}"],
        )
        equal(
            aggregate["base"][f"recall_at_{count}"],
            aggregate["full"][f"recall_at_{count}"],
        )


def check_hashes(manifest: dict) -> None:
    for relative, expected in manifest["sha256"].items():
        data = (ROOT / relative).read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        valid = actual == expected
        if actual != expected and relative.endswith(
            (".json", ".md", ".py", ".tex", ".bib", ".yml", ".yaml", ".csv", ".ps1")
        ):
            normalized_lf = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            normalized_crlf = normalized_lf.replace(b"\n", b"\r\n")
            valid = expected in {
                hashlib.sha256(normalized_lf).hexdigest(),
                hashlib.sha256(normalized_crlf).hexdigest(),
            }
        assert valid, relative


def check_cage(summary: dict, manifest: dict) -> None:
    final = load("cage-final-v6-100x500.json")
    stats = load("cage-final-stats.json")["report__default"]
    paper_cage = summary["cage"]
    final_summary = paper_cage["v6_final"]
    layerchain = final["layerchain__default"]
    report = final["report__default"]
    assert paper_cage["commit"] == manifest["benchmarks"]["cage_challenge_4"][
        "commit"
    ]
    assert paper_cage["red"] == manifest["benchmarks"]["cage_challenge_4"][
        "red_agent"
    ]
    assert paper_cage["steps"] == manifest["evaluation"]["cage_steps"] == 500
    assert final_summary["episodes"] == layerchain["episodes"] == report["episodes"] == 100
    assert [run["seed"] for run in layerchain["runs"]] == list(range(5400, 5500))
    assert [run["seed"] for run in report["runs"]] == list(range(5400, 5500))
    assert final_summary["seeds"] == manifest["evaluation"]["cage_v6_final_seeds"]
    assert manifest["evaluation"]["cage_final_episodes"] == 100
    for raw, reported in (
        (layerchain, final_summary["layerchain"]),
        (report, final_summary["report"]),
    ):
        equal(reported["reward"], raw["reward_mean"])
        equal(reported["reward_std"], raw["reward_std"])
        equal(
            reported["privileged_hosts"],
            raw["attack"]["unique_privileged_hosts_mean"],
        )
        equal(
            reported["impacted_hosts"],
            raw["attack"]["unique_impacted_hosts_mean"],
        )
        equal(
            reported["successful_impacts"],
            raw["attack"]["successful_impact_count_mean"],
        )
    difference = final_summary["report_minus_layerchain"]
    metric_map = {
        "reward": ("reward", "reward_ci95"),
        "unique_privileged_hosts": (
            "privileged_hosts",
            "privileged_hosts_ci95",
        ),
        "unique_impacted_hosts": ("impacted_hosts", "impacted_hosts_ci95"),
        "successful_impact_count": (
            "successful_impacts",
            "successful_impacts_ci95",
        ),
    }
    for raw_name, (mean_name, interval_name) in metric_map.items():
        equal(difference[mean_name], stats[raw_name]["mean_difference"])
        equal_sequence(
            difference[interval_name],
            stats[raw_name]["confidence_interval"],
        )
        assert stats[raw_name]["count"] == 100
    assert layerchain["blue_actions"]["Analyse"] == 19686
    assert layerchain["blue_actions"]["DeployDecoy"] == 7093
    assert layerchain["blue_actions"]["Remove"] == 5
    assert report["blue_actions"]["Analyse"] == 10448
    assert report["blue_actions"]["DeployDecoy"] == 5554
    assert report["blue_actions"]["Remove"] == 4975

    v12 = load("cage-v12-final-100x500.json")
    v12_default_stats = load("cage-v12-final-default-stats.json")[
        "report_v12__default"
    ]
    v12_chain_stats = load("cage-v12-final-chain-stats.json")[
        "report_v12__chain"
    ]
    v12_summary = paper_cage["final"]
    assert v12_summary["seeds"] == manifest["evaluation"]["cage_final_seeds"]
    assert v12_summary["seeds"] == [14400, 14499]
    assert v12_summary["episodes"] == 100
    assert v12_summary["steps"] == manifest["evaluation"]["cage_steps"]
    assert manifest["evaluation"]["cage_final_red_policies"] == 2
    assert manifest["benchmarks"]["cage_challenge_4"]["red_agents"] == [
        "FiniteStateRedAgent",
        "ChainAwareRedAgent",
    ]
    for red_name, reference_name, mode_name, stats_raw in (
        (
            "default_red",
            "layerchain__default",
            "report_v12__default",
            v12_default_stats,
        ),
        (
            "chain_red",
            "layerchain__chain",
            "report_v12__chain",
            v12_chain_stats,
        ),
    ):
        reference = v12[reference_name]
        mode = v12[mode_name]
        reported = v12_summary[red_name]
        assert [run["seed"] for run in reference["runs"]] == list(
            range(14400, 14500)
        )
        assert [run["seed"] for run in mode["runs"]] == list(
            range(14400, 14500)
        )
        for raw, named in (
            (reference, reported["layerchain"]),
            (mode, reported["v12"]),
        ):
            equal(named["reward"], raw["reward_mean"])
            equal(named["reward_std"], raw["reward_std"])
            equal(
                named["privileged_hosts"],
                raw["attack"]["unique_privileged_hosts_mean"],
            )
            equal(
                named["impacted_hosts"],
                raw["attack"]["unique_impacted_hosts_mean"],
            )
            equal(
                named["successful_impacts"],
                raw["attack"]["successful_impact_count_mean"],
            )
        difference = reported["v12_minus_layerchain"]
        for raw_name, (mean_name, interval_name) in metric_map.items():
            equal(difference[mean_name], stats_raw[raw_name]["mean_difference"])
            equal_sequence(
                difference[interval_name],
                stats_raw[raw_name]["confidence_interval"],
            )
            assert stats_raw[raw_name]["count"] == 100
        equal(difference["effect_size"], stats_raw["reward"]["effect_size"])
        equal(difference["win_rate"], stats_raw["reward"]["win_rate"])
        assert stats_raw["reward"]["confidence_interval"][0] > 0
        for field in (
            "unique_privileged_hosts",
            "unique_impacted_hosts",
            "successful_impact_count",
        ):
            assert stats_raw[field]["confidence_interval"][1] < 0

    v12_dev = load("cage-v12-dev-20x500.json")
    v12_val = load("cage-v12-val-20x500.json")
    for data, start in ((v12_dev, 12400), (v12_val, 13400)):
        for mode in (
            "layerchain__default",
            "report_v12__default",
            "layerchain__chain",
            "report_v12__chain",
        ):
            assert [run["seed"] for run in data[mode]["runs"]] == list(
                range(start, start + 20)
            )

    followup = paper_cage["prospective_followup"]
    v9 = load("cage-v9-dev-20x500.json")
    v9_stats = load("cage-v9-vs-v6.json")["report_v9__default"]
    v10 = load("cage-v10-dev-20x500.json")
    v10_v6 = load("cage-v10-vs-v6.json")["report_v10__default"]
    v10_layerchain = load("cage-v10-dev-stats.json")["report_v10__default"]
    for mode in ("layerchain__default", "report__default", "report_v9__default"):
        assert [run["seed"] for run in v9[mode]["runs"]] == list(range(6400, 6420))
    assert [run["seed"] for run in v10["report_v10__default"]["runs"]] == list(
        range(6400, 6420)
    )
    equal(followup["layerchain_reward"], v9["layerchain__default"]["reward_mean"])
    equal(followup["v6_reward"], v9["report__default"]["reward_mean"])
    equal(
        paper_cage["failed_versions"]["fresh_analysis_v9_reward"],
        v9["report_v9__default"]["reward_mean"],
    )
    equal(v9_stats["reward"]["mean_difference"], -2738.65)
    equal(
        paper_cage["failed_versions"]["event_aware_v10_reward"],
        v10["report_v10__default"]["reward_mean"],
    )
    equal(
        followup["v10_minus_v6"]["reward"],
        v10_v6["reward"]["mean_difference"],
    )
    equal_sequence(
        followup["v10_minus_v6"]["reward_ci95"],
        v10_v6["reward"]["confidence_interval"],
    )
    equal(
        followup["v10_minus_v6"]["impacted_hosts"],
        v10_v6["unique_impacted_hosts"]["mean_difference"],
    )
    equal(v10_layerchain["reward"]["mean_difference"], -457.45)
    equal_sequence(
        v10_layerchain["reward"]["confidence_interval"],
        [-909.9137499999999, -35.2225000000004],
    )
    assert followup["selected"] is False
    assert followup["validation_seeds_opened"] is False
    assert followup["final_seeds_opened"] is False
    assert manifest["evaluation"]["followup_validation_seeds_opened"] is False
    assert manifest["evaluation"]["followup_final_seeds_opened"] is False
    integrity = summary["integrity"]
    assert integrity["cage_original_heldout_seeds_evaluated"] is True
    assert integrity["cage_followup_reserved_seeds_evaluated"] is False
    cage_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in RESULTS.glob("cage*.json")
    )
    for seed in (*range(7400, 7420), *range(8400, 8500)):
        assert f'"seed": {seed}' not in cage_text


def check_tc(summary: dict, manifest: dict) -> None:
    cadets = load("tc-cadets-raw-trace-grounded-dev.json")
    theia = load("tc-theia-raw.json")
    clearscope = load("tc-clearscope-e5.json")
    for summary_name, raw in (
        ("tc_cadets_e3", cadets),
        ("tc_theia_e3", theia),
        ("tc_clearscope_e5", clearscope),
    ):
        check_attack(summary[summary_name], raw)
        split = summary[summary_name]["split"]
        assert split["train_days"] == raw["split"]["train"]
        assert split["validation_days"] == raw["split"]["validation"]
        test_name = (
            "development_days"
            if "development_days" in split
            else "test_days"
        )
        assert split[test_name] == raw["split"]["test"]
        equal(summary[summary_name]["threshold"], raw["threshold"])
    assert (
        cadets["aggregate"]["nodes"],
        cadets["aggregate"]["positives"],
        cadets["aggregate"]["label_coverage"],
    ) == (297085, 68, 68 / 72)
    assert (
        theia["aggregate"]["nodes"],
        theia["aggregate"]["positives"],
        theia["aggregate"]["label_coverage"],
    ) == (701622, 118, 1.0)
    assert (
        clearscope["aggregate"]["nodes"],
        clearscope["aggregate"]["positives"],
        clearscope["aggregate"]["label_coverage"],
    ) == (150964, 51, 1.0)
    assert cadets["days"]["11"]["chains"]["reported_nodes"] == 108
    assert theia["days"]["13"]["chains"]["reported_nodes"] == 196
    assert clearscope["days"]["14"]["chains"]["reported_nodes"] == 5
    assert clearscope["chain_count"] == 97
    assert manifest["benchmarks"]["pidsmaker_velox"]["commit"] == (
        "54f687c54aa03e5519cf44953d5ee44f5f6a4a28"
    )

    for name, method, reported, malicious, matched, minimum_ap in (
        ("tc-cadets-v5.json", "v5", 1870, 11, 12, 0.104029),
        ("tc-cadets-v6.json", "v6", 1708, 10, 12, 0.104029),
        ("tc-cadets-v7.json", "v7", 183, 5, 10, 0.129095),
    ):
        raw = load(name)
        chains = raw["aggregate"]["chains"]
        assert raw["method"] == method
        assert chains["reported_nodes"] == reported
        assert malicious_nodes(reported, chains["precision"]) == malicious
        assert (
            malicious_nodes(reported, chains["matched_baseline_precision"])
            == matched
        )
        assert raw["aggregate"]["full"]["ap"] >= minimum_ap

    no_path = summary["tc_post_e5_no_path_diagnostic"]
    no_path_raw = load("tc-cadets-no-path.json")
    check_attack(no_path, no_path_raw)
    assert no_path_raw["drop_path"] is True
    assert no_path["chain_count"] == no_path_raw["chain_count"] == 192
    assert no_path["predicate_count"] == no_path_raw["predicate_count"] == 8192
    alerts = summary["tc_alert_calibration"]
    for dataset, name, day in (
        ("cadets_e3", "tc-cadets-alert.json", "11"),
        ("theia_e3", "tc-theia-alert.json", "13"),
    ):
        raw = load(name)
        reported = alerts[dataset]
        equal(reported["threshold"], raw["alert_rule"]["threshold"])
        assert reported["reported_nodes"] == raw["aggregate"]["chains"][
            "reported_nodes"
        ]
        assert reported["malicious_nodes"] == malicious_nodes(
            raw["aggregate"]["chains"]["reported_nodes"],
            raw["aggregate"]["chains"]["precision"],
        )
        assert reported["matched_base_malicious_nodes"] == malicious_nodes(
            raw["aggregate"]["chains"]["reported_nodes"],
            raw["aggregate"]["chains"]["matched_baseline_precision"],
        )
        assert reported["attack_free_reported_nodes"] == raw["days"][day][
            "metrics"
        ]["chains"]["reported_nodes"]
    assert load("tc-theia-alert.json")["days"]["10"]["metrics"]["chains"][
        "reported_nodes"
    ] == 0


def check_method(latex: str) -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from wisa_agent.method import (
        ChainBuilder,
        DecisionContext,
        DefenseOrchestrator,
        ResponsePlanner,
    )
    from wisa_agent.method.config import (
        ACTION_ATTRIBUTES,
        ANOMALY_WEIGHTS,
        BELIEF_DECAY,
        CHAIN_WEIGHTS,
        CONNECTOR_LOCAL_WEIGHT,
        CONNECTOR_PERSISTENCE_WEIGHT,
        DEVIATION_RISK_WEIGHTS,
        EDGE_THRESHOLD,
        EDGE_WEIGHTS,
        HONEYPOT_THRESHOLD,
        MAX_CHAIN_LENGTH,
        MAX_OUTGOING_EDGES,
        MIN_CHAIN_LENGTH,
        MIN_CHAIN_STAGES,
        MMR_PENALTY,
        MONITOR_THRESHOLD,
        RULE_RISK_WEIGHTS,
        ROBUST_OUTLIER_SCALE,
        STRONG_RESPONSE_THRESHOLD,
        TC_CHAIN_LIMIT,
        TC_PREDICATE_LIMIT,
        TRACE_WINDOW,
        VALIDATION_QUANTILE,
    )
    from wisa_agent.tc.cdm_agent import CDMAttackAgent, validation_threshold

    assert ANOMALY_WEIGHTS == {
        "structural": 0.50,
        "trace": 0.30,
        "path": 0.20,
    }
    assert EDGE_WEIGHTS == {
        "time": 0.30,
        "context": 0.30,
        "stage": 0.25,
        "mission": 0.15,
    }
    assert CHAIN_WEIGHTS == {
        "edge": 0.55,
        "confidence": 0.20,
        "severity": 0.05,
        "stages": 0.06,
        "mission": 0.08,
    }
    assert RULE_RISK_WEIGHTS == {
        "confidence": 0.35,
        "severity": 0.25,
        "correlation": 0.25,
        "criticality": 0.15,
    }
    assert DEVIATION_RISK_WEIGHTS == {
        "anomaly": 0.50,
        "correlation": 0.30,
        "criticality": 0.20,
    }
    assert BELIEF_DECAY == 0.80
    assert MMR_PENALTY == 0.25
    assert CONNECTOR_LOCAL_WEIGHT == 0.65
    assert CONNECTOR_PERSISTENCE_WEIGHT == 0.35
    assert ROBUST_OUTLIER_SCALE == 3.0
    assert ACTION_ATTRIBUTES["honeypot"] == (
        0.35,
        0.70,
        1.00,
        0.10,
        0.95,
    )
    builder = ChainBuilder(time_window=TRACE_WINDOW)
    assert builder.edge_threshold == EDGE_THRESHOLD == 0.58
    assert builder.time_window == TRACE_WINDOW == 18.0
    assert builder.min_length == MIN_CHAIN_LENGTH == 3
    assert builder.max_length == MAX_CHAIN_LENGTH == 5
    assert builder.min_stages == MIN_CHAIN_STAGES == 3
    assert MAX_OUTGOING_EDGES == 5
    signature = inspect.signature(CDMAttackAgent)
    assert signature.parameters["candidate_limit"].default == TC_PREDICATE_LIMIT
    assert signature.parameters["chain_limit"].default == TC_CHAIN_LIMIT
    assert signature.parameters["attribution_mode"].default == "endpoints"
    assert inspect.signature(validation_threshold).parameters[
        "quantile"
    ].default == VALIDATION_QUANTILE
    orchestrator = DefenseOrchestrator(ChainBuilder())
    assert orchestrator._action(0.49, (), 1, 0.55) == "monitor"
    assert orchestrator._action(0.50, (), 1, 0.55) == "honeypot"
    assert orchestrator._action(0.70, (), 1, 0.55) == "temporary_isolate"
    assert orchestrator._action(0.85, (), 2, 0.55) == "block"
    assert (
        MONITOR_THRESHOLD,
        HONEYPOT_THRESHOLD,
        STRONG_RESPONSE_THRESHOLD,
    ) == (0.50, 0.70, 0.85)
    weak = ResponsePlanner().rank(
        DecisionContext(0.65, 0.30, 0.55, 1.0, False)
    )
    mission = ResponsePlanner().rank(
        DecisionContext(0.90, 1.0, 0.95, 0.0, True)
    )
    assert weak[0].name == "honeypot"
    assert mission[0].name == "restore"
    report_source = (
        ROOT / "src" / "wisa_agent" / "cage" / "report.py"
    ).read_text(encoding="utf-8")
    compact_report = re.sub(r"\s+", "", report_source)
    for token in (
        "edge_threshold=EDGE_THRESHOLD",
        "max_length=MAX_CHAIN_LENGTH",
        "time_window=TRACE_WINDOW",
        "risk<HONEYPOT_THRESHOLD",
        "risk<STRONG_RESPONSE_THRESHOLD",
    ):
        assert token in compact_report
    cdm_source = (
        ROOT / "src" / "wisa_agent" / "tc" / "cdm_agent.py"
    ).read_text(encoding="utf-8")
    compact_cdm = re.sub(r"\s+", "", cdm_source)
    for token in (
        '"structural":structural',
        '"trace":trace',
        '"path":path',
        "ANOMALY_WEIGHTS[name]*score/total_weight",
    ):
        assert token in compact_cdm
    for token in (
        "0.50A_{\\mathrm{struct}}(e)+0.30A_{\\mathrm{trace}}(e)",
        "+0.20A_{\\mathrm{path}}(e)",
        "0.30T_{ij}+0.30J_{ij}+0.25G_{ij}+0.15M_{ij}",
        "0.55\\bar{E}+0.20\\bar{q}+0.05\\bar{v}",
        "+0.06|\\mathcal{S}_C|+0.08I_{\\mathrm{mission}}",
        "0.35q+0.25v+0.25c+0.15k",
        "0.50a+0.30c+0.20k",
        "E_{ij}\\geq0.58",
        "2,048 predicates",
        "top 48 chains",
    ):
        assert token in latex, token


def main() -> None:
    summary = load("results.json")
    manifest = json.loads(
        (ROOT / "paper" / "artifacts.json").read_text(encoding="utf-8")
    )
    assert manifest["schema"] == 1
    assert summary["frozen_versions"] == manifest["frozen_versions"]
    assert summary["integrity"]["test_labels_used_for_training"] is False
    assert summary["integrity"]["failed_runs_removed"] is False
    assert summary["integrity"]["llm_api_used"] is False
    check_hashes(manifest)
    check_cage(summary, manifest)
    check_tc(summary, manifest)
    manuscripts = {
        name: (ROOT / "paper" / name).read_text(encoding="utf-8")
        for name in ("paper.md", "paper-en.md")
    }
    latex = (ROOT / "paper" / "main.tex").read_text(encoding="utf-8")
    check_method(latex)
    common_values = (
        "-564.72",
        "[-812.21, -319.86]",
        "1,218",
        "3/1,220",
        "297,085",
        "701,622",
        "150,964",
        "94.44%",
        "108",
        "196",
        "97",
        "10,448",
        "5,554",
        "19,686",
        "7,093",
        "4,975",
        "2,738.65",
        "457.45",
        "[-909.91, -35.22]",
        "468.65",
        "[276.24, 656.89]",
        "595.39",
        "[410.39, 784.28]",
    )
    for name, manuscript in manuscripts.items():
        for value in common_values:
            assert value in manuscript, (name, value)
    latex_values = (
        "-564.72",
        "[-812.21,-319.86]",
        "1,218",
        "3/1,220",
        "297,085",
        "701,622",
        "150,964",
        "94.44\\%",
        "2--5",
        "17/530",
        "4 of 522",
        "11 for anomaly-only",
        "108 nodes",
        "196",
        "97 valid chains",
        "183 nodes",
        "468.65",
        "[276.24,656.89]",
        "595.39",
        "[410.39,784.28]",
        "One hundred fifty",
    )
    for value in latex_values:
        assert value in latex, value
    assert latex.isascii()
    assert "??" not in latex
    references = (ROOT / "paper" / "references.bib").read_text(
        encoding="utf-8"
    )
    assert "Reinforcement Learning Journal" in references
    assert "arXiv preprint arXiv:2601.22983" in references
    keys = set(re.findall(r"^@[A-Za-z]+\{([^,]+),", references, re.MULTILINE))
    assert references.count("{") == references.count("}")
    for manuscript in manuscripts.values():
        citations = set(re.findall(r"@([A-Za-z0-9_]+)", manuscript))
        assert citations <= keys
    latex_citations = {
        key.strip()
        for group in re.findall(r"\\cite\{([^}]+)\}", latex)
        for key in group.split(",")
    }
    assert latex_citations <= keys
    print("paper evidence check passed")


if __name__ == "__main__":
    main()
