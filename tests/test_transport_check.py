from transport_check import check


def test_cross_solver_check_is_reproducible():
    result = check(
        trials=25,
        seed=20260731,
        max_roots=8,
        max_shared=10,
    )
    assert result["matched"] == 25
    assert result["reference"] == (
        "scipy.optimize.linear_sum_assignment"
    )
