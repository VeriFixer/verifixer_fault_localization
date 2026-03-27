"""Tests for cross-technique prediction guarantees in pos_test safeguard."""

from run_pos_test_guard import check_prediction_guarantees


def test_prediction_guarantees_pass_when_monotonic():
    per_technique_predictions = {
        "counterBase": {
            "m1": [10],
            "m2": [],
        },
        "counterExampleIf": {
            "m1": [10, 12],
            "m2": [],
        },
        "counterExampleIfReassume": {
            "m1": [10, 12, 20],
            "m2": [5],
        },
    }

    errors = check_prediction_guarantees(per_technique_predictions)

    assert errors == []


def test_prediction_guarantees_fail_when_counterexampleif_drops_counterbase_lines():
    per_technique_predictions = {
        "counterBase": {
            "m1": [7, 8],
        },
        "counterExampleIf": {
            "m1": [7],
        },
        "counterExampleIfReassume": {
            "m1": [7, 8],
        },
    }

    errors = check_prediction_guarantees(per_technique_predictions)

    assert any("must be included in counterExampleIf" in err for err in errors)


def test_prediction_guarantees_fail_when_reassume_drops_counterexampleif_lines():
    per_technique_predictions = {
        "counterBase": {
            "m1": [7],
        },
        "counterExampleIf": {
            "m1": [7, 9],
        },
        "counterExampleIfReassume": {
            "m1": [7],
        },
    }

    errors = check_prediction_guarantees(per_technique_predictions)

    assert any("must be included in counterExampleIfReassume" in err for err in errors)
