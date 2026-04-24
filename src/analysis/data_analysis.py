from dataclasses import dataclass
from itertools import combinations
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from scipy.stats import binomtest, rankdata, wilcoxon  # type: ignore
from pathlib import Path
from typing import Any, Callable, cast
from fl_eval.metrics.scoring import ExamOutput
from fl_eval.metrics.summary_stats import StatsSummaryEntry
from runners.run_model_common import get_technique_display_name
from logging_config import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class PairwiseStatResult:
    technique_1: str
    technique_2: str
    pair_count: int
    nonzero_pair_count: int
    statistic: float
    p_value: float
    rank_biserial: float
    significant: bool


@dataclass(frozen=True)
class PairwiseTopKResult:
    technique_1: str
    technique_2: str
    pair_count: int
    discordant_pairs: int
    a_success_b_fail: int
    a_fail_b_success: int
    p_value: float
    paired_odds_ratio: float
    significant: bool


def _normalize_scientific_notation(value: str) -> str:
    if "e" not in value and "E" not in value:
        return value

    mantissa, exponent = value.lower().split("e", maxsplit=1)
    exponent = exponent.lstrip("+")
    sign = ""
    if exponent.startswith("-"):
        sign = "-"
        exponent = exponent[1:]

    exponent = exponent.lstrip("0") or "0"
    return f"{mantissa}e{sign}{exponent}"


def _format_compact_p_value(p_value: float) -> str:
    rendered = f"{p_value:.3g}"
    if "e" in rendered.lower():
        rendered = f"{p_value:.0e}"
    return _normalize_scientific_notation(rendered)


def _format_fixed(value: float, decimals: int) -> str:
    return f"{value:.{decimals}f}"


def _get_exam_score_for_scope(score: ExamOutput, scope: str) -> float:
    if scope == "method":
        return score.score_method
    if scope == "file":
        return score.score_file
    raise ValueError(f"Unsupported EXAM scope: {scope}")


def _collect_paired_scores(
    raw_results: dict[str, list[ExamOutput]],
    tech1: str,
    tech2: str,
    scope: str = "file",
) -> tuple[list[str], np.ndarray, np.ndarray] | None:
    if tech1 not in raw_results or tech2 not in raw_results:
        logger.error(f"One or both techniques ({tech1}, {tech2}) not found in results.")
        return None

    data1 = raw_results[tech1]
    data2 = raw_results[tech2]

    if not data1 or not data2:
        logger.error(f"No data for {tech1} or {tech2}.")
        return None

    dict1 = {x.filename: x for x in data1}
    dict2 = {x.filename: x for x in data2}
    common_files = sorted(set(dict1) & set(dict2))

    if not common_files:
        return None

    scores1 = np.array([
        _get_exam_score_for_scope(dict1[filename], scope) for filename in common_files
    ])
    scores2 = np.array([
        _get_exam_score_for_scope(dict2[filename], scope) for filename in common_files
    ])
    return common_files, scores1, scores2


def _is_top_k_success(score: ExamOutput, scope: str, k: int) -> bool:
    scoped_score = score.file if scope == "file" else score.method
    if k <= 0:
        return False
    return scoped_score.line_ground_truth in scoped_score.line_prediction[:k]


def _collect_paired_top_k_success(
    raw_results: dict[str, list[ExamOutput]],
    tech1: str,
    tech2: str,
    scope: str = "file",
    k: int = 1,
) -> tuple[list[str], np.ndarray, np.ndarray] | None:
    collected = _collect_paired_scores(raw_results, tech1, tech2, scope=scope)
    if collected is None:
        return None

    common_files, _, _ = collected
    dict1 = {x.filename: x for x in raw_results[tech1]}
    dict2 = {x.filename: x for x in raw_results[tech2]}
    success1 = np.array([
        int(_is_top_k_success(dict1[filename], scope, k)) for filename in common_files
    ])
    success2 = np.array([
        int(_is_top_k_success(dict2[filename], scope, k)) for filename in common_files
    ])
    return common_files, success1, success2


def _compute_rank_biserial_from_differences(
    differences: np.ndarray,
) -> tuple[float, int]:
    nonzero_mask = differences != 0
    nonzero_diffs = differences[nonzero_mask]
    nonzero_count = int(nonzero_diffs.size)
    if nonzero_count == 0:
        return 0.0, 0

    ranks = rankdata(np.abs(nonzero_diffs), method="average")
    t_pos = float(np.sum(ranks[nonzero_diffs > 0]))
    t_neg = float(np.sum(ranks[nonzero_diffs < 0]))
    total = t_pos + t_neg
    if total == 0.0:
        return 0.0, nonzero_count
    return (t_pos - t_neg) / total, nonzero_count


def _run_paired_wilcoxon(scores1: np.ndarray, scores2: np.ndarray) -> tuple[float, float, float, int]:
    if scores1.size == 0 or scores2.size == 0:
        return 0.0, 1.0, 0.0, 0

    differences = scores1 - scores2
    rank_biserial, nonzero_count = _compute_rank_biserial_from_differences(differences)
    if nonzero_count == 0:
        return 0.0, 1.0, 0.0, 0

    try:
        result: Any = wilcoxon(differences, alternative="two-sided", zero_method="wilcox")
    except ValueError as exc:
        logger.warning(f"Could not run Wilcoxon test: {exc}")
        return 0.0, 1.0, rank_biserial, nonzero_count

    statistic = float(result.statistic)
    p_value = float(result.pvalue)
    if statistic != statistic or p_value != p_value:
        return 0.0, 1.0, rank_biserial, nonzero_count
    return statistic, p_value, rank_biserial, nonzero_count


def _run_mcnemar(top1_a: np.ndarray, top1_b: np.ndarray) -> tuple[float, int, int, int, float]:
    a_success_b_fail = int(np.sum((top1_a == 1) & (top1_b == 0)))
    a_fail_b_success = int(np.sum((top1_a == 0) & (top1_b == 1)))
    discordant_pairs = a_success_b_fail + a_fail_b_success

    if discordant_pairs == 0:
        return 1.0, 0, 0, 0, 1.0

    small_tail = min(a_success_b_fail, a_fail_b_success)
    p_value = float(binomtest(small_tail, n=discordant_pairs, p=0.5, alternative="two-sided").pvalue)
    paired_odds_ratio = float((a_success_b_fail + 0.5) / (a_fail_b_success + 0.5))
    return p_value, discordant_pairs, a_success_b_fail, a_fail_b_success, paired_odds_ratio


def _build_pairwise_stat_result(
    raw_results: dict[str, list[ExamOutput]],
    tech1: str,
    tech2: str,
    scope: str = "file",
) -> PairwiseStatResult | None:
    collected = _collect_paired_scores(raw_results, tech1, tech2, scope=scope)
    if collected is None:
        return None

    _, scores1, scores2 = collected
    statistic, p_value, rank_biserial, nonzero_pair_count = _run_paired_wilcoxon(scores1, scores2)
    return PairwiseStatResult(
        technique_1=tech1,
        technique_2=tech2,
        pair_count=int(scores1.size),
        nonzero_pair_count=nonzero_pair_count,
        statistic=statistic,
        p_value=p_value,
        rank_biserial=rank_biserial,
        significant=p_value < 0.05,
    )


def _build_pairwise_topk_result(
    raw_results: dict[str, list[ExamOutput]],
    tech1: str,
    tech2: str,
    scope: str = "file",
    k: int = 1,
) -> PairwiseTopKResult | None:
    collected = _collect_paired_top_k_success(raw_results, tech1, tech2, scope=scope, k=k)
    if collected is None:
        return None

    _, top1_a, top1_b = collected
    p_value, discordant_pairs, a_success_b_fail, a_fail_b_success, paired_odds_ratio = _run_mcnemar(top1_a, top1_b)

    return PairwiseTopKResult(
        technique_1=tech1,
        technique_2=tech2,
        pair_count=int(top1_a.size),
        discordant_pairs=discordant_pairs,
        a_success_b_fail=a_success_b_fail,
        a_fail_b_success=a_fail_b_success,
        p_value=p_value,
        paired_odds_ratio=paired_odds_ratio,
        significant=p_value < 0.05,
    )


def build_pairwise_stat_results(
    raw_results: dict[str, list[ExamOutput]],
    scope: str = "file",
) -> list[PairwiseStatResult]:
    results: list[PairwiseStatResult] = []
    for tech1, tech2 in combinations(raw_results.keys(), 2):
        result = _build_pairwise_stat_result(raw_results, tech1, tech2, scope=scope)
        if result is not None:
            results.append(result)
    return results


def build_pairwise_topk_results(
    raw_results: dict[str, list[ExamOutput]],
    scope: str = "file",
    k: int = 1,
) -> list[PairwiseTopKResult]:
    results: list[PairwiseTopKResult] = []
    for tech1, tech2 in combinations(raw_results.keys(), 2):
        result = _build_pairwise_topk_result(raw_results, tech1, tech2, scope=scope, k=k)
        if result is not None:
            results.append(result)
    return results


def _print_pairwise_stat_table(
    results: list[PairwiseStatResult],
    *,
    paper_only: bool = False,
) -> None:
    title = "PAIRWISE WILCOXON SIGNED-RANK TESTS (FILE SCOPE)"
    headers = ["Method A", "Method B", "Pairs", "Nonzero", "W", "p-value", "Rank-biserial", "Sig."]
    widths = [30, 30, 8, 8, 12, 12, 14, 8]

    separator = "-" * (sum(widths) + len(widths) * 3 + 1)
    print(f"\n{title}")
    print(separator)
    print(
        f"| {headers[0]:<{widths[0]}} | {headers[1]:<{widths[1]}} | {headers[2]:<{widths[2]}} | "
        f"{headers[3]:<{widths[3]}} | {headers[4]:<{widths[4]}} | {headers[5]:<{widths[5]}} | "
        f"{headers[6]:<{widths[6]}} | {headers[7]:<{widths[7]}} |"
    )
    print(separator)

    for row in results:
        name1 = get_technique_display_name(row.technique_1, paper_only=paper_only)
        name2 = get_technique_display_name(row.technique_2, paper_only=paper_only)
        sig_label = "yes" if row.significant else "no"
        print(
            f"| {name1:<{widths[0]}} | {name2:<{widths[1]}} | {row.pair_count:<{widths[2]}} | "
            f"{row.nonzero_pair_count:<{widths[3]}} | {row.statistic:<{widths[4]}.4f} | {row.p_value:<{widths[5]}.4g} | "
            f"{row.rank_biserial:<{widths[6]}.4f} | {sig_label:<{widths[7]}} |"
        )

    print(separator)


def _print_pairwise_topk_table(
    results: list[PairwiseTopKResult],
    *,
    paper_only: bool = False,
    k: int = 1,
) -> None:
    title = f"PAIRWISE MCNEMAR TESTS (FILE SCOPE, TOP-{k})"
    headers = ["Method A", "Method B", "Pairs", "Disc.", "A-only", "B-only", "p-value", "OR(A/B)", "Sig."]
    widths = [30, 30, 8, 8, 8, 8, 12, 10, 8]

    separator = "-" * (sum(widths) + len(widths) * 3 + 1)
    print(f"\n{title}")
    print(separator)
    print(
        f"| {headers[0]:<{widths[0]}} | {headers[1]:<{widths[1]}} | {headers[2]:<{widths[2]}} | "
        f"{headers[3]:<{widths[3]}} | {headers[4]:<{widths[4]}} | {headers[5]:<{widths[5]}} | "
        f"{headers[6]:<{widths[6]}} | {headers[7]:<{widths[7]}} | {headers[8]:<{widths[8]}} |"
    )
    print(separator)

    for row in results:
        name1 = get_technique_display_name(row.technique_1, paper_only=paper_only)
        name2 = get_technique_display_name(row.technique_2, paper_only=paper_only)
        sig_label = "yes" if row.significant else "no"
        print(
            f"| {name1:<{widths[0]}} | {name2:<{widths[1]}} | {row.pair_count:<{widths[2]}} | "
            f"{row.discordant_pairs:<{widths[3]}} | {row.a_success_b_fail:<{widths[4]}} | {row.a_fail_b_success:<{widths[5]}} | "
            f"{row.p_value:<{widths[6]}.4g} | {row.paired_odds_ratio:<{widths[7]}.4f} | {sig_label:<{widths[8]}} |"
        )

    print(separator)


def print_pairwise_wilcoxon_table(
    raw_results: dict[str, list[ExamOutput]],
    paper_only: bool = False,
    scope: str = "file",
) -> list[PairwiseStatResult]:
    results = build_pairwise_stat_results(raw_results, scope=scope)
    if not results:
        print("\nPAIRWISE WILCOXON SIGNED-RANK TESTS (FILE SCOPE)")
        print("No comparable technique pairs found.")
        return []

    _print_pairwise_stat_table(results, paper_only=paper_only)
    return results


def print_pairwise_wilcoxon_latex_table(
    results: list[PairwiseStatResult],
    *,
    paper_only: bool = False,
    scope: str = "file",
) -> None:
    scope_label = "File" if scope == "file" else "Method"
    print(f"\n--- LaTeX Table Output (Pairwise Wilcoxon, {scope_label} Scope) ---")
    print(r"\begin{table}[h]")
    print(r"    \centering")
    print(r"    \begin{tabular}{l|l|r|r|r|r|c}")
    print(r"        \hline")
    print(r"        \textbf{M.A} & \textbf{M.B} & \textbf{NZ} & \textbf{W} & \textbf{p} & \textbf{R-bi} & \textbf{Sig.} \\")
    print(r"        \hline")

    for row in results:
        name1 = get_technique_display_name(row.technique_1, paper_only=paper_only).replace("_", r"\_")
        name2 = get_technique_display_name(row.technique_2, paper_only=paper_only).replace("_", r"\_")
        sig_label = "yes" if row.significant else "no"
        statistic = int(round(row.statistic))
        print(
            f"        {name1} & {name2} & {row.nonzero_pair_count} & "
            f"{statistic} & {_format_compact_p_value(row.p_value)} & {_format_fixed(row.rank_biserial, 3)} & {sig_label} \\\\"  # noqa: E501
        )

    print(r"        \hline")
    print(r"    \end{tabular}")
    print(
        rf"    \caption{{Pairwise Wilcoxon signed-rank tests for EXAM scores ({scope_label.lower()} scope). Compact headers: R-bi = rank-biserial effect size.}}"
    )
    print(rf"    \label{{tab:pairwise_wilcoxon_{scope.lower()}}}")
    print(r"\end{table}")


def print_pairwise_topk_table(
    raw_results: dict[str, list[ExamOutput]],
    paper_only: bool = False,
    scope: str = "file",
    k: int = 1,
) -> list[PairwiseTopKResult]:
    results = build_pairwise_topk_results(raw_results, scope=scope, k=k)
    if not results:
        print(f"\nPAIRWISE MCNEMAR TESTS (FILE SCOPE, TOP-{k})")
        print("No comparable technique pairs found.")
        return []

    _print_pairwise_topk_table(results, paper_only=paper_only, k=k)
    return results


def print_pairwise_topk_latex_table(
    results: list[PairwiseTopKResult],
    *,
    paper_only: bool = False,
    scope: str = "file",
    k: int = 1,
) -> None:
    scope_label = "File" if scope == "file" else "Method"
    print(f"\n--- LaTeX Table Output (Pairwise McNemar Top-{k}, {scope_label} Scope) ---")
    print(r"\begin{table}[h]")
    print(r"    \centering")
    print(r"    \begin{tabular}{l|l|r|r|r|r|r|c}")
    print(r"        \hline")
    print(r"        \textbf{M.A} & \textbf{M.B} & \textbf{Disc.} & \textbf{A-O} & \textbf{B-O} & \textbf{p} & \textbf{OR} & \textbf{Sig.} \\")
    print(r"        \hline")

    for row in results:
        name1 = get_technique_display_name(row.technique_1, paper_only=paper_only).replace("_", r"\_")
        name2 = get_technique_display_name(row.technique_2, paper_only=paper_only).replace("_", r"\_")
        sig_label = "yes" if row.significant else "no"
        print(
            f"        {name1} & {name2} & {row.discordant_pairs} & "
            f"{row.a_success_b_fail} & {row.a_fail_b_success} & {_format_compact_p_value(row.p_value)} & {_format_fixed(row.paired_odds_ratio, 3)} & {sig_label} \\\\"  # noqa: E501
        )

    print(r"        \hline")
    print(r"    \end{tabular}")
    print(
        rf"    \caption{{Pairwise McNemar tests for Top-{k} localization success ({scope_label.lower()} scope). Compact headers: OR = paired odds ratio.}}"
    )
    print(rf"    \label{{tab:pairwise_mcnemar_top{k}_{scope.lower()}}}")
    print(r"\end{table}")


def _print_ascii_scope_table(
    title: str,
    stats: dict[str, StatsSummaryEntry],
    *,
    get_count: Callable[[StatsSummaryEntry], int],
    get_exam_1: Callable[[StatsSummaryEntry], float],
    get_exam_2: Callable[[StatsSummaryEntry], float],
    get_exam_3: Callable[[StatsSummaryEntry], float],
    get_found: Callable[[StatsSummaryEntry], float],
    get_empty: Callable[[StatsSummaryEntry], float],
    get_top1: Callable[[StatsSummaryEntry], float],
    get_top3: Callable[[StatsSummaryEntry], float],
    get_top5: Callable[[StatsSummaryEntry], float],
    paper_only: bool = False,
) -> None:
    h_tech = "Method"
    h_count = "Evaluated"
    h_exam1 = "EXAM_1"
    h_exam2 = "EXAM_2"
    h_exam3 = "EXAM_3"
    h_found = "Found"
    h_empty = "Empty"
    h_topk = "Top1/Top3/Top5"

    w_tech = 30
    w_count = 10
    w_exam = 10
    w_rate = 10
    w_topk = 16

    header = (
        f"| {h_tech:<{w_tech}} | {h_count:<{w_count}} | {h_exam1:<{w_exam}} | {h_exam2:<{w_exam}} | "
        f"{h_exam3:<{w_exam}} | {h_found:<{w_rate}} | {h_empty:<{w_rate}} | {h_topk:<{w_topk}} |"
    )
    separator = "-" * len(header)

    print(f"\n{title}")
    print(separator)
    print(header)
    print(separator)

    for name, data in stats.items():
        display_name = get_technique_display_name(name, paper_only=paper_only)
        count = get_count(data)
        exam1 = get_exam_1(data)
        exam2 = get_exam_2(data)
        exam3 = get_exam_3(data)
        found = get_found(data)
        empty = get_empty(data)
        topk = f"{get_top1(data):.1f}/{get_top3(data):.1f}/{get_top5(data):.1f}"

        print(
            f"| {display_name:<{w_tech}} | {count:<{w_count}} | {exam1:<{w_exam}.4f} | {exam2:<{w_exam}.4f} | "
            f"{exam3:<{w_exam}.4f} | {found:<{w_rate}.2f} | {empty:<{w_rate}.2f} | {topk:<{w_topk}} |"
        )

    print(separator)


def print_ascii_table(stats: dict[str, StatsSummaryEntry], paper_only: bool = True):
    """Print separate ASCII tables for file scope and method scope."""
    _print_ascii_scope_table(
        "FILE SCOPE",
        stats,
        get_count=lambda d: d.count,
        get_exam_1=lambda d: d.avg_exam_file,
        get_exam_2=lambda d: d.avg_exam_found_file,
        get_exam_3=lambda d: d.avg_exam_not_empty_file,
        get_found=lambda d: d.found_rate_file,
        get_empty=lambda d: d.exist_rate_file,
        get_top1=lambda d: d.top1_success_file,
        get_top3=lambda d: d.top3_success_file,
        get_top5=lambda d: d.top5_success_file,
        paper_only=paper_only,
    )
    _print_ascii_scope_table(
        "METHOD SCOPE",
        stats,
        get_count=lambda d: d.count_method,
        get_exam_1=lambda d: d.avg_exam_method,
        get_exam_2=lambda d: d.avg_exam_found_method,
        get_exam_3=lambda d: d.avg_exam_not_empty_method,
        get_found=lambda d: d.found_rate_method,
        get_empty=lambda d: d.exist_rate_method,
        get_top1=lambda d: d.top1_success_method,
        get_top3=lambda d: d.top3_success_method,
        get_top5=lambda d: d.top5_success_method,
        paper_only=paper_only,
    )
    print()


@dataclass(frozen=True)
class CompactMetrics:
    """Compact metrics for a technique: EXAM1, Top-k, and Found/Empty rates."""
    exam_file: float
    exam_method: float
    top1_success: float
    top3_success: float
    top5_success: float
    found_rate: float
    empty_rate: float
    case_count: int


def _filter_complete_cases(raw_results: dict[str, list[ExamOutput]]) -> dict[str, list[ExamOutput]]:
    """Filter to only cases where ALL techniques have non-empty predictions.
    
    Returns filtered dict with same structure, keeping only shared indices.
    """
    if not raw_results:
        return {}
    
    # Find all unique filenames across all techniques
    all_filenames: set[str] = set()
    for scores in raw_results.values():
        all_filenames.update(s.filename for s in scores)
    
    # For each filename, check if ALL techniques have non-empty predictions
    complete_filenames: set[str] = set()
    for filename in all_filenames:
        all_non_empty = True
        for scores in raw_results.values():
            score_dict = {s.filename: s for s in scores}
            if filename not in score_dict or score_dict[filename].empty_file:
                all_non_empty = False
                break
        if all_non_empty:
            complete_filenames.add(filename)
    
    # Filter all techniques to only complete filenames
    filtered: dict[str, list[ExamOutput]] = {}
    for tech, scores in raw_results.items():
        filtered[tech] = [s for s in scores if s.filename in complete_filenames]
    
    return filtered


def _compute_compact_metrics(scores: list[ExamOutput]) -> CompactMetrics:
    """Compute compact metrics for a list of ExamOutput (file scope only)."""
    if not scores:
        return CompactMetrics(
            exam_file=0.0, exam_method=0.0, top1_success=0.0, top3_success=0.0,
            top5_success=0.0, found_rate=0.0, empty_rate=0.0, case_count=0
        )
    
    # EXAM1 (all cases)
    exam_file = sum(s.score_file for s in scores) / len(scores)
    exam_method = sum(s.score_method for s in scores) / len(scores)
    
    # Found rate
    found_count = sum(1 for s in scores if s.found_file)
    found_rate = (found_count / len(scores)) * 100.0 if scores else 0.0
    
    # Empty rate
    empty_count = sum(1 for s in scores if s.empty_file)
    empty_rate = (empty_count / len(scores)) * 100.0 if scores else 0.0
    
    # Top-k success rates (file scope)
    def top_k_rate(k: int) -> float:
        hits = sum(1 for s in scores if s.file.line_ground_truth in s.file.line_prediction[:k])
        return (hits / len(scores)) * 100.0 if scores else 0.0
    
    top1_success = top_k_rate(1)
    top3_success = top_k_rate(3)
    top5_success = top_k_rate(5)
    
    return CompactMetrics(
        exam_file=exam_file,
        exam_method=exam_method,
        top1_success=top1_success,
        top3_success=top3_success,
        top5_success=top5_success,
        found_rate=found_rate,
        empty_rate=empty_rate,
        case_count=len(scores)
    )


def print_compact_results_table(raw_results: dict[str, list[ExamOutput]], paper_only: bool = True):
    """Print compact LaTeX table with EXAM1, Top-k, and Found/Empty rates (all cases)."""
    if not raw_results:
        logger.warning("No results to display in compact table.")
        return
    
    metrics_by_tech: dict[str, CompactMetrics] = {}
    total_cases = 0
    for tech, scores in raw_results.items():
        metrics_by_tech[tech] = _compute_compact_metrics(scores)
        if scores:
            total_cases = len(scores)
    
    print("\n--- Compact Results Table (All Cases) ---")
    print(r"\begin{table}[t]")
    print(r"    \centering")
    print(r"    \small")
    print(r"    \begin{tabular}{lcccc}")
    print(r"        \toprule")
    print(r"        \textbf{Strat.} & \textbf{EX$_F$} & \textbf{EX$_M$} & \textbf{Top-1/3/5} & \textbf{F / E} \\")
    print(r"        \midrule")
    
    for tech in sorted(metrics_by_tech.keys()):
        metrics = metrics_by_tech[tech]
        clean_name = get_technique_display_name(tech, paper_only=paper_only).replace("_", r"\_")
        top_k_str = f"{metrics.top1_success:.2f} / {metrics.top3_success:.2f} / {metrics.top5_success:.2f}"
        found_empty_str = f"{metrics.found_rate:.2f} / {metrics.empty_rate:.2f}"
        
        print(
            f"        {clean_name} & {metrics.exam_file:.3f} & {metrics.exam_method:.3f} & {top_k_str} & {found_empty_str} \\\\"
        )
    
    print(r"        \bottomrule")
    print(r"    \end{tabular}")
    print(
        f"    \\caption{{Fault localization performance across strategies ({total_cases} programs). "
        f"EX$_F$ and EX$_M$ report EXAM scores under file and method scope, respectively (lower is better). "
        f"Top-$k$ shows localization success rates as Top-1 / Top-3 / Top-5 (\\%). "
        f"F / E denotes percentage of cases where fault is found (F) and where method returns no output (E).}}"
    )
    print(r"    \label{tab:compact_results_all}")
    print(r"\end{table}")


def print_complete_cases_table(raw_results: dict[str, list[ExamOutput]], paper_only: bool = True):
    """Print compact LaTeX table with EXAM1, Top-k, and Found/Empty rates (complete cases only)."""
    if not raw_results:
        logger.warning("No results to display in complete cases table.")
        return
    
    filtered_results = _filter_complete_cases(raw_results)
    
    if not filtered_results or not any(filtered_results.values()):
        logger.warning("No complete cases found (all techniques with non-empty predictions).")
        return
    
    metrics_by_tech: dict[str, CompactMetrics] = {}
    total_cases = 0
    for tech, scores in filtered_results.items():
        metrics_by_tech[tech] = _compute_compact_metrics(scores)
        if scores:
            total_cases = len(scores)
    
    print("\n--- Compact Results Table (Complete Cases Only) ---")
    print(r"\begin{table}[t]")
    print(r"    \centering")
    print(r"    \small")
    print(r"    \begin{tabular}{lcccc}")
    print(r"        \toprule")
    print(r"        \textbf{Strat.} & \textbf{EX$_F$} & \textbf{EX$_M$} & \textbf{Top-1/3/5} & \textbf{F / E} \\")
    print(r"        \midrule")
    
    for tech in sorted(metrics_by_tech.keys()):
        metrics = metrics_by_tech[tech]
        clean_name = get_technique_display_name(tech, paper_only=paper_only).replace("_", r"\_")
        top_k_str = f"{metrics.top1_success:.2f} / {metrics.top3_success:.2f} / {metrics.top5_success:.2f}"
        found_empty_str = f"{metrics.found_rate:.2f} / {metrics.empty_rate:.2f}"
        
        print(
            f"        {clean_name} & {metrics.exam_file:.3f} & {metrics.exam_method:.3f} & {top_k_str} & {found_empty_str} \\\\"
        )
    
    print(r"        \bottomrule")
    print(r"    \end{tabular}")
    print(
        f"    \\caption{{Fault localization performance across strategies (complete cases: {total_cases} programs where all methods returned non-empty output). "
        f"EX$_F$ and EX$_M$ report EXAM scores under file and method scope, respectively (lower is better). "
        f"Top-$k$ shows localization success rates as Top-1 / Top-3 / Top-5 (\\%). "
        f"F / E denotes percentage of cases where fault is found (F) and where method returns no output (E).}}"
    )
    print(r"    \label{tab:compact_results_complete}")
    print(r"\end{table}")


def print_latex_table(stats: dict[str, StatsSummaryEntry], paper_only: bool = True):
    """Print dual-scope LaTeX tables."""
    file_evaluated = next(iter(stats.values())).count if stats else 0
    method_evaluated = next(iter(stats.values())).count_method if stats else 0

    print("\n--- LaTeX Table Output (File-Wide Scope) ---")
    print(r"\begin{table}[h]")
    print(r"    \centering")
    print(r"    \begin{tabular}{l|c|c|c|c|c}")
    print(r"        \hline")
    print(r"        \textbf{Technique} & \textbf{EXAM$_1$} & \textbf{EXAM$_2$} & \textbf{EXAM$_3$} & \textbf{Found(\%)} & \textbf{Empty(\%)} \\")
    print(r"        \hline")

    for name, data in stats.items():
        clean_name = get_technique_display_name(name, paper_only=paper_only).replace("_", r"\_")
        print(
            f"        {clean_name} & {data.avg_exam_file:.4f} & {data.avg_exam_found_file:.4f} & {data.avg_exam_not_empty_file:.4f} & {data.found_rate_file:.2f} & {data.exist_rate_file * 100.0:.2f} \\\\"  # noqa: E501
        )

    print(r"        \hline")
    print(r"    \end{tabular}")
    print(
        f"    \\caption{{Comparison of Fault Localization Techniques (File-Wide Scope). Evaluated on {file_evaluated} examples. EXAM$_1$: all cases; EXAM$_2$: found-only cases; EXAM$_3$: non-empty prediction cases.}}"  # noqa: E501
    )
    print(r"    \label{tab:fl_results_file}")
    print(r"\end{table}")

    print("\n--- LaTeX Table Output (Method-Scoped Scope) ---")
    print(r"\begin{table}[h]")
    print(r"    \centering")
    print(r"    \begin{tabular}{l|c|c|c|c|c}")
    print(r"        \hline")
    print(r"        \textbf{Technique} & \textbf{EXAM$_1$} & \textbf{EXAM$_2$} & \textbf{EXAM$_3$} & \textbf{Found(\%)} & \textbf{Empty(\%)} \\")
    print(r"        \hline")

    for name, data in stats.items():
        clean_name = get_technique_display_name(name, paper_only=paper_only).replace("_", r"\_")
        print(
            f"        {clean_name} & {data.avg_exam_method:.4f} & {data.avg_exam_found_method:.4f} & {data.avg_exam_not_empty_method:.4f} & {data.found_rate_method:.2f} & {data.exist_rate_method * 100.0:.2f} \\\\"  # noqa: E501
        )

    print(r"        \hline")
    print(r"    \end{tabular}")
    print(
        f"    \\caption{{Comparison of Fault Localization Techniques (Method-Scoped Scope). Evaluated on {method_evaluated} examples. EXAM$_1$: all cases; EXAM$_2$: found-only cases; EXAM$_3$: non-empty prediction cases.}}"  # noqa: E501
    )
    print(r"    \label{tab:fl_results_method}")
    print(r"\end{table}")

    print("\n--- LaTeX Table Output (Top-k File Scope) ---")
    print(r"\begin{table}[h]")
    print(r"    \centering")
    print(r"    \begin{tabular}{l|c|c|c}")
    print(r"        \hline")
    print(r"        \textbf{Technique} & \textbf{Top-1(\%)} & \textbf{Top-3(\%)} & \textbf{Top-5(\%)} \\")
    print(r"        \hline")

    for name, data in stats.items():
        clean_name = get_technique_display_name(name, paper_only=paper_only).replace("_", r"\_")
        print(
            f"        {clean_name} & {data.top1_success_file:.2f} & {data.top3_success_file:.2f} & {data.top5_success_file:.2f} \\\\"  # noqa: E501
        )

    print(r"        \hline")
    print(r"    \end{tabular}")
    print(
        rf"    \caption{{Top-k localization success in file scope. Evaluated on {file_evaluated} examples.}}"  # noqa: E501
    )
    print(r"    \label{tab:fl_topk_file}")
    print(r"\end{table}")

    print("\n--- LaTeX Table Output (Top-k Method Scope) ---")
    print(r"\begin{table}[h]")
    print(r"    \centering")
    print(r"    \begin{tabular}{l|c|c|c}")
    print(r"        \hline")
    print(r"        \textbf{Technique} & \textbf{Top-1(\%)} & \textbf{Top-3(\%)} & \textbf{Top-5(\%)} \\")
    print(r"        \hline")

    for name, data in stats.items():
        clean_name = get_technique_display_name(name, paper_only=paper_only).replace("_", r"\_")
        print(
            f"        {clean_name} & {data.top1_success_method:.2f} & {data.top3_success_method:.2f} & {data.top5_success_method:.2f} \\\\"  # noqa: E501
        )

    print(r"        \hline")
    print(r"    \end{tabular}")
    print(
        rf"    \caption{{Top-k localization success in method scope. Evaluated on {method_evaluated} examples.}}"  # noqa: E501
    )
    print(r"    \label{tab:fl_topk_method}")
    print(r"\end{table}")
    print("--------------------------\n")


def _plot_scope(raw_results: dict[str, list[ExamOutput]], output_prefix: Path, scope: str, title: str, paper_only: bool = False):
    labels = [tech for tech, vals in raw_results.items() if vals]
    display_labels = [get_technique_display_name(tech, paper_only=paper_only) for tech in labels]
    if not labels:
        return

    # Paper-friendly sizing for two-column layouts.
    figure_size = (7.0, 3.9)
    label_font = 14
    tick_font = 14
    legend_font = 14
    # Okabe-Ito palette for color-blind accessibility.
    palette = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00", "#56B4E9", "#F0E442", "#000000"]
    technique_colors = {tech: palette[i % len(palette)] for i, tech in enumerate(labels)}
    line_styles: list[Any] = ["-", "--", "-.", ":", (0, (3, 1, 1, 1)), (0, (5, 1)), (0, (1, 1)), (0, (3, 2, 1, 2))]
    technique_line_styles: dict[str, Any] = {tech: line_styles[i % len(line_styles)] for i, tech in enumerate(labels)}
    line_widths = [3.4, 3.0, 2.8, 2.6, 2.4, 3.2, 2.2, 2.9]
    technique_line_widths = {tech: line_widths[i % len(line_widths)] for i, tech in enumerate(labels)}
    median_color = "#CC79A7"
    mean_color = "#D55E00"

    get_score: Callable[[ExamOutput], float]
    get_found: Callable[[ExamOutput], bool]
    if scope == "file":
        get_score = lambda x: x.score_file
        get_found = lambda x: x.found_file
    else:
        get_score = lambda x: x.score_method
        get_found = lambda x: x.found_method

    box_data = [np.array([get_score(x) for x in raw_results[tech]]) for tech in labels]
    fig1, ax1 = cast(Any, plt.subplots(1, 1, figsize=figure_size))  # type: ignore[reportUnknownMemberType]
    boxplot_artists = ax1.boxplot(
        box_data,
        tick_labels=display_labels,
        orientation="vertical",
        showfliers=False,
        showmeans=True,
        widths=0.45,
        patch_artist=True,
        whiskerprops={"color": "#4D4D4D", "linewidth": 1.1},
        capprops={"color": "#4D4D4D", "linewidth": 1.1},
        meanprops={
            "marker": "D",
            "markerfacecolor": mean_color,
            "markeredgecolor": mean_color,
            "markersize": 5,
        },
        medianprops={"color": median_color, "linewidth": 1.6},
    )
    for box, tech in zip(boxplot_artists["boxes"], labels):
        box.set_facecolor("white")
        box.set_edgecolor("#4D4D4D")
        box.set_alpha(1.0)
    #ax1.set_title(f"{title}", fontsize=title_font, fontweight="bold")
    ax1.set_ylabel("EXAM Score", fontsize=label_font)
    ax1.set_xlabel("Technique", fontsize=label_font)
    ax1.set_ylim(-0.02, 1.05)
    ax1.grid(axis="y", linestyle="--", alpha=0.35, color="#9E9E9E")
    ax1.tick_params(axis="x", rotation=20, labelsize=tick_font)
    ax1.tick_params(axis="y", labelsize=tick_font)
    summary_legend_handles = [
        Line2D([0], [0], color=median_color, lw=1.8, label="Median"),
        Line2D(
            [0],
            [0],
            marker="D",
            linestyle="None",
            markerfacecolor=mean_color,
            markeredgecolor=mean_color,
            markersize=5,
            label="Mean",
        ),
    ]
    ax1.legend(handles=summary_legend_handles, loc="upper right", fontsize=legend_font)

    distribution_png_file = Path(f"{output_prefix}_distribution.png")
    distribution_pdf_file = Path(f"{output_prefix}_distribution.pdf")
    plt.tight_layout()
    fig1.savefig(distribution_png_file, dpi=300, bbox_inches="tight")
    fig1.savefig(distribution_pdf_file, bbox_inches="tight")
    plt.close(fig1)

    fig2, ax2 = cast(Any, plt.subplots(1, 1, figsize=figure_size))  # type: ignore[reportUnknownMemberType]
    #ax2.set_title(f"{title}", fontsize=title_font, fontweight="bold")

    for tech in labels:
        tech_data = sorted(raw_results[tech], key=get_score)
        scores = [get_score(x) for x in tech_data]
        found_flags = np.array([1 if get_found(x) else 0 for x in tech_data])
        y_vals = np.cumsum(found_flags) / len(raw_results[tech])
        plot_x = scores + [1.0]
        plot_y = list(y_vals) + [float(y_vals[-1])]
        ax2.step(
            plot_x,
            plot_y,
            where="post",
            label=get_technique_display_name(tech, paper_only=paper_only),
            lw=technique_line_widths[tech],
            color=technique_colors[tech],
            linestyle=technique_line_styles[tech],
        )[0]
        #ax2.text(1.03, y_vals[-1], f"{(y_vals[-1] * 100):.1f}%", color=line.get_color(), va="center", fontsize=annotation_font)

    for thresh in [0.01, 0.05, 0.10, 0.25, 0.50]:
        ax2.axvline(x=thresh, color="#7F7F7F", linestyle="--", alpha=0.35)

    ax2.set_xlabel("EXAM Score Threshold", fontsize=label_font)
    ax2.set_ylabel("Faults Found (%)", fontsize=label_font)
    ax2.set_xlim(0, 1.0)
    ax2.margins(x=0)
    ax2.set_ylim(0, 1.05)
    ax2.grid(True, linestyle=":", alpha=0.45, color="#9E9E9E")
    ax2.tick_params(axis="x", labelsize=tick_font)
    ax2.tick_params(axis="y", labelsize=tick_font)
    ax2.legend(loc="lower right", fontsize=legend_font)

    success_png_file = Path(f"{output_prefix}_success.png")
    success_pdf_file = Path(f"{output_prefix}_success.pdf")
    plt.tight_layout()
    fig2.savefig(success_png_file, dpi=300, bbox_inches="tight")
    fig2.savefig(success_pdf_file, bbox_inches="tight")
    plt.close(fig2)
    print(
        "Plots saved to: "
        f"{distribution_png_file}, {distribution_pdf_file}, {success_png_file}, and {success_pdf_file}"
    )


def generate_plots(raw_results: dict[str, list[ExamOutput]], output_path: Path, paper_only: bool = False):
    """Generate file-scoped EXAM plots."""
    file_prefix = output_path / "benchmark_hybrid_analysis_FILE"
    _plot_scope(raw_results, file_prefix, scope="file", title="File-Scoped EXAM", paper_only=paper_only)


def generate_dual_scope_plots(raw_results: dict[str, list[ExamOutput]], output_path: Path, paper_only: bool = False):
    """Generate file-scoped and method-scoped EXAM plots."""
    generate_plots(raw_results, output_path, paper_only=paper_only)
    method_prefix = output_path / "benchmark_hybrid_analysis_METHOD"
    _plot_scope(raw_results, method_prefix, scope="method", title="Method-Scoped EXAM", paper_only=paper_only)


def compare_two_methods(raw_results: dict[str, list[ExamOutput]], tech1: str, tech2: str):
    """Compare two techniques on common files using paired Wilcoxon signed-rank testing."""
    collected = _collect_paired_scores(raw_results, tech1, tech2, scope="file")
    if collected is None:
        return

    common_files, scores1, scores2 = collected

    print(f"\n--- Statistical Comparison between {tech1} and {tech2} ---")
    print(f"Comparing {len(common_files)} common files.")

    statistic, p_val, rank_biserial, nonzero_pair_count = _run_paired_wilcoxon(scores1, scores2)

    print("Test used: Wilcoxon signed-rank test")
    print("Justification: The samples are paired by filename and EXAM scores are not assumed to be normal.")
    print(f"Statistic: {statistic:.4f}, p-value: {p_val:.4f}")
    print(f"Non-zero paired differences: {nonzero_pair_count}/{len(common_files)}")
    print(f"Matched rank-biserial: {rank_biserial:.4f}")

    if p_val < 0.05:
        print(f"Result: Significant difference (p < 0.05) (p_val={p_val:.4f})")
        mean1 = np.mean(scores1)
        mean2 = np.mean(scores2)
        better = tech1 if mean1 < mean2 else tech2
        print(f"{better} has lower average EXAM score ({mean1:.4f} vs {mean2:.4f})")
    else:
        print(f"Result: No significant difference (p >= 0.05) (p_val={p_val:.4f})")

    dict1 = {x.filename: x for x in raw_results[tech1]}
    dict2 = {x.filename: x for x in raw_results[tech2]}

    print("\n--- Debugging Overview ---")
    found1 = [dict1[f].found for f in common_files]
    found2 = [dict2[f].found for f in common_files]

    only1 = [f for f, (f1, f2) in zip(common_files, zip(found1, found2)) if f1 and not f2]
    only2 = [f for f, (f1, f2) in zip(common_files, zip(found1, found2)) if not f1 and f2]
    both = [f for f, (f1, f2) in zip(common_files, zip(found1, found2)) if f1 and f2]
    neither = [f for f, (f1, f2) in zip(common_files, zip(found1, found2)) if not f1 and not f2]

    print(f"Files where {tech1} found fault but {tech2} did not: {len(only1)} files")
    print(f"Files where {tech2} found fault but {tech1} did not: {len(only2)} files")
    print(f"Files where both found: {len(both)}")
    print(f"Files where neither found: {len(neither)}")

    if only1:
        print(f"\nSample {tech1}-only successes:")
        for f in only1[:5]:
            print(f"  {f}: {tech1} score={dict1[f].score:.4f}, {tech2} score={dict2[f].score:.4f}")

    if only2:
        print(f"\nSample {tech2}-only successes:")
        for f in only2[:5]:
            print(f"  {f}: {tech1} score={dict1[f].score:.4f}, {tech2} score={dict2[f].score:.4f}")

    if neither:
        print(f"\nSample {tech1} & {tech2} - both insucesses:")
        for f in neither[:5]:
            print(f"  {f}: {tech1} score={dict1[f].score:.4f}, {tech2} score={dict2[f].score:.4f}")