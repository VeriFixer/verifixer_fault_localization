from fl_eval.metrics.scoring import ExamOutput, ExamScore
from fl_eval.metrics.summary_stats import build_summary_entry


def _mk_exam(
    filename: str,
    file_score: float,
    method_score: float,
    file_found: bool,
    method_found: bool,
    file_prediction: bool,
    method_prediction: bool,
) -> ExamOutput:
    return ExamOutput(
        filename=filename,
        method_name="m",
        file=ExamScore(score=file_score, found=file_found, prediction=file_prediction),
        method=ExamScore(score=method_score, found=method_found, prediction=method_prediction),
    )


def test_build_summary_entry_empty_scores_defaults_to_zero() -> None:
    summary = build_summary_entry([])

    assert summary.count == 0
    assert summary.count_method == 0
    assert summary.avg_exam_file == 0.0
    assert summary.avg_exam_method == 0.0
    assert summary.avg_exam_score_pred_not_empty == 0.0
    assert summary.avg_exam_score_pred_not_empty_method == 0.0


def test_build_summary_entry_uses_only_non_empty_predictions_for_new_averages() -> None:
    scores = [
        _mk_exam("f1", 0.2, 0.4, True, True, True, True),
        _mk_exam("f2", 0.8, 0.6, False, False, False, False),
        _mk_exam("f3", 0.6, 0.2, True, True, True, True),
    ]

    summary = build_summary_entry(scores)

    assert summary.count == 3
    assert summary.avg_exam_file == (0.2 + 0.8 + 0.6) / 3
    assert summary.avg_exam_method == (0.4 + 0.6 + 0.2) / 3

    # Only f1 and f3 should be used for these new metrics.
    assert summary.avg_exam_score_pred_not_empty == (0.2 + 0.6) / 2
    assert summary.avg_exam_score_pred_not_empty_method == (0.4 + 0.2) / 2


def test_build_summary_entry_all_predictions_empty_sets_new_averages_to_zero() -> None:
    scores = [
        _mk_exam("f1", 0.2, 0.4, False, False, False, False),
        _mk_exam("f2", 0.6, 0.8, False, False, False, False),
    ]

    summary = build_summary_entry(scores)

    assert summary.count == 2
    assert summary.avg_exam_score_pred_not_empty == 0.0
    assert summary.avg_exam_score_pred_not_empty_method == 0.0
