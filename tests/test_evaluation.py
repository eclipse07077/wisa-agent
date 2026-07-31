from wisa_agent.evaluation import paired_result


def test_paired_result_uses_common_keys():
    result = paired_result(
        {1: 1.0, 2: 2.0, 3: 3.0},
        {1: 2.0, 2: 3.0, 4: 9.0},
        bootstrap_samples=100,
    )
    assert result.count == 2
    assert result.mean_difference == 1.0
    assert result.win_rate == 1.0
