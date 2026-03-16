import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import gaussian_kde, ttest_ind, mannwhitneyu, shapiro  # type: ignore
from pathlib import Path
from matplotlib.patches import Patch
from matplotlib.lines import Line2D  # type: ignore
from typing import Dict, List, Any
from fl_eval.metrics.scoring import ExamOutput

def print_ascii_table(stats: Dict[str, Dict[str, Any]]):
    """Prints a clean ASCII table of the results."""
    h_tech = "Technique"
    h_count = "Evaluated"
    h_avg = "Avg EXAM"
    h_found = "Fault Found %"
    h_exist = "Empty Answer %"
    
    w_tech = 30
    w_count = 12
    w_avg = 15
    w_found = 15
    w_exist = 16
    
    header = f"| {h_tech:<{w_tech}} | {h_count:<{w_count}} | {h_avg:<{w_avg}} | {h_found:<{w_found}} | {h_exist:<{w_exist}}"
    separator = "-" * len(header)
    print("\n" + separator)
    print(header)
    print(separator)
    
    for name, data in stats.items():
        count = str(data['count'])
        avg = f"{data['avg_exam']:.4f}"
        found = f"{data['found_rate']:.2f}"
        exist = f"{data['exist_rate']:.2f}"
        print(f"| {name:<{w_tech}} | {count:<{w_count}} | {avg:<{w_avg}} | {found:<{w_found}} | {exist:<{w_exist}}")
    print(separator + "\n")

def print_latex_table(stats: Dict[str, Dict[str, Any]]):
    """Prints a LaTeX ready table of the results."""
    print("\n--- LaTeX Table Output ---")
    print(r"\begin{table}[h]")
    print(r"    \centering")
    print(r"    \begin{tabular}{l|c|c|c}")
    print(r"        \hline")
    print(r"        \textbf{Technique} & \textbf{Evaluated} & \textbf{Avg EXAM} & \textbf{Fault Found (\%)} \\")
    print(r"        \hline")
    
    for name, data in stats.items():
        # Escape underscores for Latex (e.g., counter_base -> counter\_base)
        clean_name = name.replace("_", r"\_")
        count = data['count']
        avg = f"{data['avg_exam']:.4f}"
        found = f"{data['found_rate']:.2f}"
        print(f"        {clean_name} & {count} & {avg} & {found} \\\\")
        
    print(r"        \hline")
    print(r"    \end{tabular}")
    print(r"    \caption{Comparison of Fault Localization Techniques}")
    print(r"    \label{tab:fl_results}")
    print(r"\end{table}")
    print("--------------------------\n")

def generate_plots(raw_results: Dict[str, List[ExamOutput]], output_path: Path): 
    techniques = list(raw_results.keys())
    labels = [t for t in techniques if raw_results[t]]
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 8))  # type: ignore
    fig.suptitle('Fault Localization Benchmark: Comprehensive Analysis', fontsize=18, fontweight='bold')  # type: ignore

    y_grid = np.linspace(0, 1, 500)
    scale_factor = 0.4 

    for i, tech in enumerate(labels):
        data = raw_results[tech]
        all_scores = np.array([x.score for x in data])
        found_scores = np.array([x.score for x in data if x.found])
        not_found_scores = np.array([x.score for x in data if not x.found])
        total_count = len(data)

        # --- 1. Draw Density Background ---
        def draw_half_violin(ax: Any, scores: Any, pos: int, side: str = 'left'):
            if len(scores) == 0: return
            color = '#2ecc71' if side == 'left' else '#e74c3c'
            weight = len(scores) / total_count
            
            if np.all(scores == scores[0]): # Zero variance case
                val = scores[0]
                ax.hlines(val, pos, pos + (scale_factor * weight if side == 'right' else -scale_factor * weight), 
                          colors=color, lw=6, alpha=0.6)
            else:
                try:
                    kde = gaussian_kde(scores, bw_method='silverman')
                    dens: np.ndarray = kde.evaluate(y_grid)  # type: ignore
                    dens = (dens / (max(dens) + 1e-9)) * scale_factor * weight # type: ignore
                    if side == 'left':
                        ax.fill_betweenx(y_grid, pos - dens, pos, color=color, alpha=0.5)
                    else:
                        ax.fill_betweenx(y_grid, pos, pos + dens, color=color, alpha=0.5)
                except: pass

        draw_half_violin(ax1, found_scores, i, side='left')
        draw_half_violin(ax1, not_found_scores, i, side='right')

        # --- 2. Overlay Overall Box Plot ---
        # This shows the trend of ALL data (Found + Not Found combined)
        ax1.boxplot(all_scores, positions=[i], vert=True, widths=0.25,
                    showfliers=False, # Keeps the plot clean
                    patch_artist=True,
                    showmeans=True,
                    meanprops=dict(marker='D', markerfacecolor='gold', 
                                  markeredgecolor='black', markersize=8),
                    boxprops=dict(facecolor='white', color='black', alpha=0.5, linewidth=2.5),
                    medianprops=dict(color='blue', linewidth=2),
                    whiskerprops=dict(color='black', linewidth=2),
                    capprops=dict(color='black', linewidth=2))

    # Styling ax1
    ax1.set_title('Density Breakdown with Overall Box Plot Overlay', fontsize=14)
    ax1.set_xticks(range(len(labels)))
    ax1.set_xticklabels(labels, rotation=15)
    ax1.set_ylabel('EXAM Score (Lower is Better)', fontsize=12)
    ax1.set_ylim(-0.02, 1.05)
    ax1.grid(axis='y', linestyle='--', alpha=0.3)
    
    
    legend_elements = [
        Patch(facecolor='#2ecc71', alpha=0.6, label='Found Density'),
        Patch(facecolor='#e74c3c', alpha=0.6, label='Not Found Density'),
        Line2D([0], [0], color='blue', lw=2, label='Median Score'),
        Line2D([0], [0], marker='D', color='w', markerfacecolor='gold', 
                   markeredgecolor='black', markersize=10, label='Mean Score')
    ]
    
    
    ax1.legend(handles=legend_elements, loc='upper right')
    
    # --- Plot 2: ECDF with Numeric Success Annotations ---
    for tech in labels:
        tech_data = sorted(raw_results[tech], key=lambda x: x.score)
        scores = [x.score for x in tech_data]
        found_flags = [1 if x.found else 0 for x in tech_data]
        
        # Calculate cumulative percentage
        y_vals = np.cumsum(found_flags) / len(raw_results[tech])
        
        # --- THE FIX: Force line to span to 1.0 ---
        # Add a final point at x=1.0 with the last known y-value
        plot_x = scores + [1.0]
        plot_y = list(y_vals) + [y_vals[-1]]
        
        line, = ax2.step(plot_x, plot_y, where='post', label=tech, lw=2.5)
        
        # Final Numeric Label at the very edge (x=1.0)
        final_pct = y_vals[-1] * 100
        ax2.text(1.01, y_vals[-1], f'{final_pct:.1f}%', 
                color=line.get_color(), fontweight='bold', va='center', fontsize=10)

    # Define the 'Critical Efforts' (e.g., 1%, 5%, 10% of code)
    critical_thresholds = [0.01, 0.05, 0.10, 0.25, 0.50]
    for thresh in critical_thresholds:
        ax2.axvline(x=thresh, color='gray', linestyle='--', alpha=0.3)
        ax2.text(thresh, 0.02, f' Top-{int(thresh*100)}%', rotation=90, fontsize=9, alpha=0.7)

    ax2.set_title('Success Rate vs. Inspection Effort', fontsize=14)
    ax2.set_xlabel('EXAM Score Threshold (Effort)', fontsize=12)
    ax2.set_ylabel('% of Total Faults Found', fontsize=12)
    ax2.set_xlim(0, 1.1) # Extra space for the text labels
    ax2.set_ylim(0, 1.05)
    ax2.grid(True, linestyle=':', alpha=0.6)
    ax2.legend(loc='lower right')

    plt.tight_layout()
    filename = output_path / "benchmark_hybrid_analysis.png"
    plt.savefig(filename)  # type: ignore
    print(f"Final hybrid plots saved to: {filename}")


def compare_two_methods(raw_results: Dict[str, List[ExamOutput]], tech1: str, tech2: str):
    """
    Compare two fault localization techniques statistically and provide debugging insights.
    """
    if tech1 not in raw_results or tech2 not in raw_results:
        print(f"Error: One or both techniques ({tech1}, {tech2}) not found in results.")
        return
    
    data1 = raw_results[tech1]
    data2 = raw_results[tech2]
    
    if not data1 or not data2:
        print(f"Error: No data for {tech1} or {tech2}.")
        return
    
    scores1 = np.array([x.score for x in data1])
    scores2 = np.array([x.score for x in data2])
    
    print(f"\n--- Statistical Comparison between {tech1} and {tech2} ---")
    
    # Check normality
    _, p1 = shapiro(scores1)
    _, p2 = shapiro(scores2)
    normal1 = p1 > 0.05
    normal2 = p2 > 0.05
    
    print(f"Normality test (Shapiro-Wilk): {tech1} p={p1:.4f} ({'normal' if normal1 else 'not normal'}), {tech2} p={p2:.4f} ({'normal' if normal2 else 'not normal'})")
    
    # Choose test
    if normal1 and normal2:
        # Assume equal variances? Could test with Levene, but for simplicity, use unequal
        stat, p_val = ttest_ind(scores1, scores2, equal_var=False)
        test_name = "Welch's t-test"
        justification = "Both distributions are approximately normal, so we use Welch's t-test (unequal variances) to compare means."
    else:
        stat, p_val = mannwhitneyu(scores1, scores2, alternative='two-sided')
        test_name = "Mann-Whitney U test"
        justification = "At least one distribution is not normal, so we use the non-parametric Mann-Whitney U test to compare distributions."
    
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
        print("Result: No significant difference (p >= 0.05) (p_val={p_val:.4f})")
    
    # Debugging overview
    print(f"\n--- Debugging Overview ---")
    found1 = [x.found for x in data1]
    found2 = [x.found for x in data2]
    
    only1 = [i for i, (f1, f2) in enumerate(zip(found1, found2)) if f1 and not f2]
    only2 = [i for i, (f1, f2) in enumerate(zip(found1, found2)) if not f1 and f2]
    both = [i for i, (f1, f2) in enumerate(zip(found1, found2)) if f1 and f2]
    neither = [i for i, (f1, f2) in enumerate(zip(found1, found2)) if not f1 and not f2]
    
    print(f"Test cases where {tech1} found fault but {tech2} did not: {len(only1)} cases (indices: {only1[:10]}{'...' if len(only1) > 10 else ''})")
    print(f"Test cases where {tech2} found fault but {tech1} did not: {len(only2)} cases (indices: {only2[:10]}{'...' if len(only2) > 10 else ''})")
    print(f"Test cases where both found: {len(both)}")
    print(f"Test cases where neither found: {len(neither)}")
    
    if only1:
        print(f"\nSample {tech1}-only successes:")
        for i in only1[:5]:
            print(f"  Case {i}: {tech1} score={data1[i].score:.4f}, {tech2} score={data2[i].score:.4f}")
    
    if only2:
        print(f"\nSample {tech2}-only successes:")
        for i in only2[:5]:
            print(f"  Case {i}: {tech1} score={data1[i].score:.4f}, {tech2} score={data2[i].score:.4f}")