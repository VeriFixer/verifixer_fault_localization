"""Tests for cross-technique prediction guarantees in pos_test safeguard."""

from run_pos_test_guard import check_prediction_guarantees


def test_prediction_guarantees_pass_when_monotonic():
    per_technique_predictions = {
        "CNTB": {
            "m1": [10],
            "m2": [],
        },
        "CNTS": {
            "m1": [10, 12],
            "m2": [],
        },
        "CNTM": {
            "m1": [10, 12, 20],
            "m2": [5],
        },
    }

    errors = check_prediction_guarantees(per_technique_predictions)

    assert errors == []


def test_prediction_guarantees_fail_when_counterexampleif_drops_counterbase_lines():
    per_technique_predictions = {
        "CNTB": {
            "m1": [7, 8],
        },
        "CNTS": {
            "m1": [7],
        },
        "CNTM": {
            "m1": [7, 8],
        },
    }

    errors = check_prediction_guarantees(per_technique_predictions)

    assert any("must be included in CNTS" in err for err in errors)


def test_prediction_guarantees_fail_when_reassume_drops_counterexampleif_lines():
    per_technique_predictions = {
        "CNTB": {
            "m1": [7],
        },
        "CNTS": {
            "m1": [7, 9],
        },
        "CNTM": {
            "m1": [7],
        },
    }

    errors = check_prediction_guarantees(per_technique_predictions)

    assert any("must be included in CNTM" in err for err in errors)
