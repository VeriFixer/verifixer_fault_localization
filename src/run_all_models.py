import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import gaussian_kde
from fl_eval.util.run_parallel_or_seq import run_parallel_or_seq
from fl_eval.util.globals import RUN_PARALLEL
from run_1_model import (
        TECHNIQUE_MAP, 
        _setup_evaluation, 
        _process_mutation
    )

def _print_ascii_table(stats: Dict[str, dict]):
    """Prints a clean ASCII table of the results."""
    h_tech = "Technique"
    h_count = "Evaluated"
    h_avg = "Avg EXAM"
    h_found = "Fault Found %"
    
    w_tech = 20
    w_count = 12
    w_avg = 15
    w_found = 15
    
    header = f"| {h_tech:<{w_tech}} | {h_count:<{w_count}} | {h_avg:<{w_avg}} | {h_found:<{w_found}} |"
    separator = "-" * len(header)
    print("\n" + separator)
    print(header)
    print(separator)
    
    for name, data in stats.items():
        count = str(data['count'])
        avg = f"{data['avg_exam']:.4f}"
        found = f"{data['found_rate']:.2f}"
        print(f"| {name:<{w_tech}} | {count:<{w_count}} | {avg:<{w_avg}} | {found:<{w_found}} |")
    print(separator + "\n")

def _print_latex_table(stats: Dict[str, dict]):
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


import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import gaussian_kde
from pathlib import Path
from matplotlib.patches import Patch

def _generate_plots(raw_results: Dict[str, List[tuple[bool, float]]], output_path: Path): 
    techniques = list(raw_results.keys())
    labels = [t for t in techniques if raw_results[t]]
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 8))
    fig.suptitle('Fault Localization Benchmark: Comprehensive Analysis', fontsize=18, fontweight='bold')

    y_grid = np.linspace(0, 1, 500)
    scale_factor = 0.4 

    for i, tech in enumerate(labels):
        data = raw_results[tech]
        all_scores = np.array([x[1] for x in data])
        found_scores = np.array([x[1] for x in data if x[0]])
        not_found_scores = np.array([x[1] for x in data if not x[0]])
        total_count = len(data)

        # --- 1. Draw Density Background ---
        def draw_half_violin(ax, scores, pos, side='left'):
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
                    dens = kde.evaluate(y_grid)
                    dens = (dens / (max(dens) + 1e-9)) * scale_factor * weight
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
        plt.Line2D([0], [0], color='blue', lw=2, label='Median Score'),
        plt.Line2D([0], [0], marker='D', color='w', markerfacecolor='gold', 
                   markeredgecolor='black', markersize=10, label='Mean Score')
    ]
    
    
    ax1.legend(handles=legend_elements, loc='upper right')

    # --- Plot 2: ECDF with Numeric Success Annotations ---
    for tech in labels:
        tech_data = sorted(raw_results[tech], key=lambda x: x[1])
        scores = [x[1] for x in tech_data]
        found_flags = [1 if x[0] else 0 for x in tech_data]
        
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
    plt.savefig(filename)
    print(f"Final hybrid plots saved to: {filename}")


def run_benchmark(base_path: Path):
    print(f"Starting Benchmark on: {base_path}")
    print(f"Techniques to run: {list(TECHNIQUE_MAP.keys())}")
    raw_results = {}
    stats_summary = {}
    
    for tech_name in TECHNIQUE_MAP:
        print(f"\n--- Running {tech_name.upper()} ---")
        setup_res = _setup_evaluation(tech_name, base_path)
        if not setup_res:
            print(f"Skipping {tech_name} due to setup failure.")
            continue
        fl_technique, killed_dir, original_dir = setup_res
        diff_paths = list(killed_dir.glob("*.txt"))
        scores_dirty = run_parallel_or_seq(
            diff_paths, 
            _process_mutation, 
            f"Eval {tech_name}", 
            fl_technique, 
            killed_dir, 
            original_dir,
            parallel= RUN_PARALLEL
        )
        scores_clean = [s for s in scores_dirty if s is not None]
        raw_results[tech_name] = scores_clean
        if scores_clean:
            avg = sum([s[1] for s in scores_clean]) / len(scores_clean)
            found_pct = (sum([1 for s in scores_clean if s[0]]) / len(scores_clean)) * 100
        else:
            avg = 0.0
            found_pct = 0.0
        stats_summary[tech_name] = {
            'count': len(scores_clean),
            'avg_exam': avg,
            'found_rate': found_pct
        }
    if not stats_summary:
        print("No results collected.")
        return
    _print_ascii_table(stats_summary)
    _print_latex_table(stats_summary)
    try:
        _generate_plots(raw_results, base_path.parent)
    except Exception as e:
        print(f"Could not generate plots: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark ALL Fault Localization techniques.")
    parser.add_argument(
        "data_path", 
        type=Path,
        help="Path to the directory containing 'killed' and 'original' folders."
    )
    
    args = parser.parse_args()
    if args.data_path.exists():
        run_benchmark(args.data_path)
    else:
        print(f"Path not found: {args.data_path}")