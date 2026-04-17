import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from scipy.stats import ttest_ind, mannwhitneyu, shapiro  # type: ignore
from pathlib import Path
from typing import Any, Callable, cast
from fl_eval.metrics.scoring import ExamOutput
from fl_eval.metrics.summary_stats import StatsSummaryEntry
from runners.run_model_common import get_technique_display_name
from logging_config import get_logger

logger = get_logger(__name__)


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