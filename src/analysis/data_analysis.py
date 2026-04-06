import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import ttest_ind, mannwhitneyu, shapiro  # type: ignore
from pathlib import Path
from typing import Any, Callable, cast
from fl_eval.metrics.scoring import ExamOutput
from fl_eval.metrics.summary_stats import StatsSummaryEntry
from logging_config import get_logger

logger = get_logger(__name__)


def print_ascii_table(stats: dict[str, StatsSummaryEntry]):
    """Print a dual-scope ASCII table."""
    h_tech = "Technique"
    h_count = "Evaluated"
    h_avg_file = "Avg EXAM (File)"
    h_avg_file_pred = "Avg EXAM (Pred != Empty, File)"
    h_found_file = "Fault Found % (File)"
    h_exist_file = "Empty Answer % (File)"
    h_avg_method = "Avg EXAM (Method)"
    h_avg_method_pred = "Avg EXAM (Pred != Empty, Method)"
    h_found_method = "Fault Found % (Method)"
    h_exist_method = "Empty Answer % (Method)"

    w_tech = 30
    w_count = 12
    w_avg = 17
    w_avg_pred = 32
    w_found = 21
    w_exist = 21

    header1 = f"| {h_tech:<{w_tech}} | {h_count:<{w_count}} | {h_avg_file:<{w_avg}} | {h_avg_file_pred:<{w_avg_pred}} | {h_found_file:<{w_found}} | {h_exist_file:<{w_exist}}"
    header2 = f"| {' ':<{w_tech}} | {' ':<{w_count}} | {h_avg_method:<{w_avg}} | {h_avg_method_pred:<{w_avg_pred}} | {h_found_method:<{w_found}} | {h_exist_method:<{w_exist}}"

    separator = "-" * max(len(header1), len(header2))
    print("\n" + separator)
    print(header1)
    print(header2)
    print(separator)

    for name, data in stats.items():
        count = str(data.count)
        avg_file = f"{data.avg_exam_file:.4f}"
        avg_file_pred = f"{data.avg_exam_score_pred_not_empty:.4f}"
        found_file = f"{data.found_rate_file:.2f}"
        exist_file = f"{data.exist_rate_file:.2f}"

        avg_method = f"{data.avg_exam_method:.4f}"
        avg_method_pred = f"{data.avg_exam_score_pred_not_empty_method:.4f}"
        found_method = f"{data.found_rate_method:.2f}"
        exist_method = f"{data.exist_rate_method:.2f}"

        print(
            f"| {name:<{w_tech}} | {count:<{w_count}} | {avg_file:<{w_avg}} | {avg_file_pred:<{w_avg_pred}} | {found_file:<{w_found}} | {exist_file:<{w_exist}}"
        )
        print(
            f"| {' ':<{w_tech}} | {' ':<{w_count}} | {avg_method:<{w_avg}} | {avg_method_pred:<{w_avg_pred}} | {found_method:<{w_found}} | {exist_method:<{w_exist}}"
        )

    print(separator + "\n")


def print_latex_table(stats: dict[str, StatsSummaryEntry]):
    """Print dual-scope LaTeX tables."""
    print("\n--- LaTeX Table Output (File-Wide Scope) ---")
    print(r"\begin{table}[h]")
    print(r"    \centering")
    print(r"    \begin{tabular}{l|c|c|c|c}")
    print(r"        \hline")
    print(r"        \textbf{Technique} & \textbf{Evaluated} & \textbf{Avg EXAM} & \textbf{Avg EXAM (Pred != Empty)} & \textbf{Fault Found (\%)} \\")
    print(r"        \hline")

    for name, data in stats.items():
        clean_name = name.replace("_", r"\_")
        print(
            f"        {clean_name} & {data.count} & {data.avg_exam_file:.4f} & {data.avg_exam_score_pred_not_empty:.4f} & {data.found_rate_file:.2f} \\\\"  # noqa: E501
        )

    print(r"        \hline")
    print(r"    \end{tabular}")
    print(r"    \caption{Comparison of Fault Localization Techniques (File-Wide Scope)}")
    print(r"    \label{tab:fl_results_file}")
    print(r"\end{table}")

    print("\n--- LaTeX Table Output (Method-Scoped Scope) ---")
    print(r"\begin{table}[h]")
    print(r"    \centering")
    print(r"    \begin{tabular}{l|c|c|c|c}")
    print(r"        \hline")
    print(r"        \textbf{Technique} & \textbf{Evaluated} & \textbf{Avg EXAM} & \textbf{Avg EXAM (Pred != Empty)} & \textbf{Fault Found (\%)} \\")
    print(r"        \hline")

    for name, data in stats.items():
        clean_name = name.replace("_", r"\_")
        print(
            f"        {clean_name} & {data.count_method} & {data.avg_exam_method:.4f} & {data.avg_exam_score_pred_not_empty_method:.4f} & {data.found_rate_method:.2f} \\\\"  # noqa: E501
        )

    print(r"        \hline")
    print(r"    \end{tabular}")
    print(r"    \caption{Comparison of Fault Localization Techniques (Method-Scoped Scope)}")
    print(r"    \label{tab:fl_results_method}")
    print(r"\end{table}")
    print("--------------------------\n")


def _plot_scope(raw_results: dict[str, list[ExamOutput]], output_file: Path, scope: str, title: str):
    labels = [tech for tech, vals in raw_results.items() if vals]
    if not labels:
        return

    fig, (ax1, ax2) = cast(Any, plt.subplots(1, 2, figsize=(20, 8)))  # type: ignore[reportUnknownMemberType]
    fig.suptitle(title, fontsize=18, fontweight="bold")

    get_score: Callable[[ExamOutput], float]
    get_found: Callable[[ExamOutput], bool]
    if scope == "file":
        get_score = lambda x: x.score_file
        get_found = lambda x: x.found_file
    else:
        get_score = lambda x: x.score_method
        get_found = lambda x: x.found_method

    box_data = [np.array([get_score(x) for x in raw_results[tech]]) for tech in labels]
    ax1.boxplot(
        box_data,
        tick_labels=labels,
        orientation="vertical",
        showfliers=False,
        showmeans=True,
        widths=0.45,
    )
    ax1.set_title("Score Distribution")
    ax1.set_ylabel("EXAM Score (Lower is Better)")
    ax1.set_ylim(-0.02, 1.05)
    ax1.grid(axis="y", linestyle="--", alpha=0.3)
    ax1.tick_params(axis="x", rotation=15)

    for tech in labels:
        tech_data = sorted(raw_results[tech], key=get_score)
        scores = [get_score(x) for x in tech_data]
        found_flags = np.array([1 if get_found(x) else 0 for x in tech_data])
        y_vals = np.cumsum(found_flags) / len(raw_results[tech])
        plot_x = scores + [1.0]
        plot_y = list(y_vals) + [float(y_vals[-1])]
        line = ax2.step(plot_x, plot_y, where="post", label=tech, lw=2.0)[0]
        ax2.text(1.01, y_vals[-1], f"{(y_vals[-1] * 100):.1f}%", color=line.get_color(), va="center", fontsize=9)

    for thresh in [0.01, 0.05, 0.10, 0.25, 0.50]:
        ax2.axvline(x=thresh, color="gray", linestyle="--", alpha=0.3)

    ax2.set_title("Success Rate vs. Inspection Effort")
    ax2.set_xlabel("EXAM Score Threshold (Effort)")
    ax2.set_ylabel("% of Total Faults Found")
    ax2.set_xlim(0, 1.1)
    ax2.set_ylim(0, 1.05)
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.legend(loc="lower right")

    plt.tight_layout()
    plt.savefig(output_file)  # type: ignore
    plt.close(fig)
    print(f"Final hybrid plots saved to: {output_file}")


def generate_plots(raw_results: dict[str, list[ExamOutput]], output_path: Path):
    """Generate file-scoped EXAM plots."""
    filename = output_path / "benchmark_hybrid_analysis_FILE.png"
    _plot_scope(raw_results, filename, scope="file", title="File-Scoped EXAM: Comprehensive Analysis")


def generate_dual_scope_plots(raw_results: dict[str, list[ExamOutput]], output_path: Path):
    """Generate file-scoped and method-scoped EXAM plots."""
    generate_plots(raw_results, output_path)
    method_filename = output_path / "benchmark_hybrid_analysis_METHOD.png"
    _plot_scope(raw_results, method_filename, scope="method", title="Method-Scoped EXAM: Comprehensive Analysis")


def compare_two_methods(raw_results: dict[str, list[ExamOutput]], tech1: str, tech2: str):
    """Compare two techniques on common files using file-scoped EXAM scores."""
    if tech1 not in raw_results or tech2 not in raw_results:
        logger.error(f"One or both techniques ({tech1}, {tech2}) not found in results.")
        return

    data1 = raw_results[tech1]
    data2 = raw_results[tech2]

    if not data1 or not data2:
        logger.error(f"No data for {tech1} or {tech2}.")
        return

    dict1 = {x.filename: x for x in data1}
    dict2 = {x.filename: x for x in data2}
    common_files = set(dict1.keys()) & set(dict2.keys())

    if not common_files:
        print(f"No common files between {tech1} and {tech2}.")
        return

    scores1 = np.array([dict1[f].score for f in common_files])
    scores2 = np.array([dict2[f].score for f in common_files])

    print(f"\n--- Statistical Comparison between {tech1} and {tech2} ---")
    print(f"Comparing {len(common_files)} common files.")

    shapiro_1: Any = shapiro(scores1)
    shapiro_2: Any = shapiro(scores2)
    p1 = float(shapiro_1.pvalue)
    p2 = float(shapiro_2.pvalue)
    normal1 = p1 > 0.05
    normal2 = p2 > 0.05

    print(
        f"Normality test (Shapiro-Wilk): {tech1} p={p1:.4f} ({'normal' if normal1 else 'not normal'}), "
        f"{tech2} p={p2:.4f} ({'normal' if normal2 else 'not normal'})"
    )

    if normal1 and normal2:
        test_res: Any = ttest_ind(scores1, scores2, equal_var=False)
        test_name = "Welch's t-test"
        justification = "Both distributions are approximately normal, so we use Welch's t-test (unequal variances) to compare means."
        stat = float(test_res.statistic)
        p_val = float(test_res.pvalue)
    else:
        test_res = mannwhitneyu(scores1, scores2, alternative="two-sided")
        test_name = "Mann-Whitney U test"
        justification = "At least one distribution is not normal, so we use the non-parametric Mann-Whitney U test to compare distributions."
        stat = float(test_res.statistic)
        p_val = float(test_res.pvalue)

    if stat != stat or p_val != p_val:
        stat = 0.0
        p_val = 1.0

    print(f"Test used: {test_name}")
    print(f"Justification: {justification}")
    print(f"Statistic: {stat:.4f}, p-value: {p_val:.4f}")

    if p_val < 0.05:
        print(f"Result: Significant difference (p < 0.05) (p_val={p_val:.4f})")
        mean1 = np.mean(scores1)
        mean2 = np.mean(scores2)
        better = tech1 if mean1 < mean2 else tech2
        print(f"{better} has lower average EXAM score ({mean1:.4f} vs {mean2:.4f})")
    else:
        print(f"Result: No significant difference (p >= 0.05) (p_val={p_val:.4f})")

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