from dataclasses import dataclass

from fl_eval.metrics.scoring import ExamOutput


@dataclass(frozen=True)
class StatsSummaryEntry:
    count: int = 0
    avg_exam_file: float = 0.0
    avg_exam_found_file: float = 0.0
    avg_exam_not_empty_file: float = 0.0
    found_rate_file: float = 0.0
    exist_rate_file: float = 0.0
    top1_success_file: float = 0.0
    top3_success_file: float = 0.0
    top5_success_file: float = 0.0
    avg_exam_method: float = 0.0
    avg_exam_found_method: float = 0.0
    avg_exam_not_empty_method: float = 0.0
    found_rate_method: float = 0.0
    exist_rate_method: float = 0.0
    top1_success_method: float = 0.0
    top3_success_method: float = 0.0
    top5_success_method: float = 0.0
    count_method: int = 0
    # Backward-compatible aliases kept for existing call sites/tables.
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


def _top_k_success_rate(scores: list[ExamOutput], scope: str, k: int) -> float:
    if not scores:
        return 0.0

    hits = 0
    for score in scores:
        scoped_score = score.file if scope == "file" else score.method
        top_k = scoped_score.line_prediction[:k]
        if scoped_score.line_ground_truth in top_k:
            hits += 1
    return (hits / len(scores)) * 100.0


def build_summary_entry(scores: list[ExamOutput]) -> StatsSummaryEntry:
    if not scores:
        return StatsSummaryEntry()

    avg_exam_file = _safe_mean([score.score_file for score in scores])
    avg_exam_found_file = _safe_mean([score.score_file for score in scores if score.found_file])
    found_rate_file = _safe_bool_rate([score.found_file for score in scores], percent=True)
    exist_rate_file = _safe_bool_rate([score.empty_file for score in scores])
    top1_success_file = _top_k_success_rate(scores, scope="file", k=1)
    top3_success_file = _top_k_success_rate(scores, scope="file", k=3)
    top5_success_file = _top_k_success_rate(scores, scope="file", k=5)

    avg_exam_method = _safe_mean([score.score_method for score in scores])
    avg_exam_found_method = _safe_mean([score.score_method for score in scores if score.found_method])
    found_rate_method = _safe_bool_rate([score.found_method for score in scores], percent=True)
    exist_rate_method = _safe_bool_rate([score.empty_method for score in scores])
    top1_success_method = _top_k_success_rate(scores, scope="method", k=1)
    top3_success_method = _top_k_success_rate(scores, scope="method", k=3)
    top5_success_method = _top_k_success_rate(scores, scope="method", k=5)

    avg_exam_not_empty_file = _safe_mean(
        [score.score_file for score in scores if not score.empty_file]
    )
    avg_exam_not_empty_method = _safe_mean(
        [score.score_method for score in scores if not score.empty_method]
    )

    return StatsSummaryEntry(
        count=len(scores),
        avg_exam_file=avg_exam_file,
        avg_exam_found_file=avg_exam_found_file,
        avg_exam_not_empty_file=avg_exam_not_empty_file,
        found_rate_file=found_rate_file,
        exist_rate_file=exist_rate_file,
        top1_success_file=top1_success_file,
        top3_success_file=top3_success_file,
        top5_success_file=top5_success_file,
        avg_exam_method=avg_exam_method,
        avg_exam_found_method=avg_exam_found_method,
        avg_exam_not_empty_method=avg_exam_not_empty_method,
        found_rate_method=found_rate_method,
        exist_rate_method=exist_rate_method,
        top1_success_method=top1_success_method,
        top3_success_method=top3_success_method,
        top5_success_method=top5_success_method,
        count_method=len(scores),
        avg_exam_score_pred_not_empty=avg_exam_not_empty_file,
        avg_exam_score_pred_not_empty_method=avg_exam_not_empty_method,
    )
