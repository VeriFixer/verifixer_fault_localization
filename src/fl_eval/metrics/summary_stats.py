from dataclasses import dataclass

from fl_eval.metrics.scoring import ExamOutput


@dataclass(frozen=True)
class StatsSummaryEntry:
    count: int = 0
    avg_exam_file: float = 0.0
    found_rate_file: float = 0.0
    exist_rate_file: float = 0.0
    avg_exam_method: float = 0.0
    found_rate_method: float = 0.0
    exist_rate_method: float = 0.0
    count_method: int = 0
    avg_exam_score_pred_not_empty: float = 0.0
    avg_exam_score_pred_not_empty_method: float = 0.0


def _safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _safe_bool_rate(values: list[bool], percent: bool = False) -> float:
    if not values:
        return 0.0
    rate = sum(1.0 for value in values if value) / len(values)
    if percent:
        return rate * 100.0
    return rate


def build_summary_entry(scores: list[ExamOutput]) -> StatsSummaryEntry:
    if not scores:
        return StatsSummaryEntry()

    avg_exam_file = _safe_mean([score.score_file for score in scores])
    found_rate_file = _safe_bool_rate([score.found_file for score in scores], percent=True)
    exist_rate_file = _safe_bool_rate([score.empty_file for score in scores])

    avg_exam_method = _safe_mean([score.score_method for score in scores])
    found_rate_method = _safe_bool_rate([score.found_method for score in scores], percent=True)
    exist_rate_method = _safe_bool_rate([score.empty_method for score in scores])

    avg_exam_score_pred_not_empty = _safe_mean(
        [score.score_file for score in scores if not score.empty_file]
    )
    avg_exam_score_pred_not_empty_method = _safe_mean(
        [score.score_method for score in scores if not score.empty_method]
    )

    return StatsSummaryEntry(
        count=len(scores),
        avg_exam_file=avg_exam_file,
        found_rate_file=found_rate_file,
        exist_rate_file=exist_rate_file,
        avg_exam_method=avg_exam_method,
        found_rate_method=found_rate_method,
        exist_rate_method=exist_rate_method,
        count_method=len(scores),
        avg_exam_score_pred_not_empty=avg_exam_score_pred_not_empty,
        avg_exam_score_pred_not_empty_method=avg_exam_score_pred_not_empty_method,
    )
