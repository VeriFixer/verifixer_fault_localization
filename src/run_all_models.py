import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt
import numpy as np

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


def _generate_plots(raw_results: Dict[str, List[tuple[bool, float]]], output_path: Path): 
    """
    Generates a combined figure with a distribution plot (Box Plot overlayed with Violin Plot) 
    and a Bar Chart.
    """
    import matplotlib.pyplot as plt
    import numpy as np
    from pathlib import Path

    techniques = list(raw_results.keys())
    
    # Extract data, filtering out techniques with no results
    scores_data = []
    labels = []
    
    for tech in techniques:
        data = [x[1] for x in raw_results[tech]]
        if data:
            scores_data.append(data)
            labels.append(tech)
    
    if not scores_data:
        print("No data available to plot.")
        return

    # --- Setup Figure: Two subplots (Distribution + Bar Chart) ---
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle('Fault Localization Benchmark Results', fontsize=16)
    
    # 1. Distribution Plot: Violin Plot with Box Plot Overlay
    # --- A. Violin Plot (Background) ---
    # Use different colors for better contrast
    violin_colors = ['#88CCEE', '#CC6677', '#DDCC77', '#117733', '#332288', '#AA4499'] * len(labels)
    
    parts = ax1.violinplot(
        scores_data, 
        showmeans=False, 
        showmedians=False, # We let the boxplot show the median
        showextrema=False, # We let the boxplot show the extrema/whiskers
        widths=0.9
    )
    
    # Customize Violin Colors and Opacity
    for i, pc in enumerate(parts['bodies']):
        pc.set_facecolor(violin_colors[i])
        pc.set_edgecolor('black')
        pc.set_alpha(0.5) # Lower alpha to allow boxplot to show through
        
    # --- B. Box Plot (Overlay) ---
    # Plotting this *after* the violin plot ensures it is rendered on top
    box_plot = ax1.boxplot(
        scores_data, 
        vert=True, 
        patch_artist=True, # Allows filling boxes with color
        medianprops={'color': 'red', 'linewidth': 2},
        whiskerprops={'color': 'black'},
        capprops={'color': 'black'},
        flierprops={'marker': 'o', 'markerfacecolor': 'black', 'markeredgecolor': 'black', 'markersize': 5, 'alpha': 0.7}
    )
    
    # Set box colors (e.g., lighter shade of the violin color for contrast)
    box_colors = ['#AADDEE', '#FFBBCC', '#FFEECB', '#BBFFCC', '#BBCCFF', '#FFAAFF'] * len(labels)
    for i, patch in enumerate(box_plot['boxes']):
        patch.set_facecolor(box_colors[i])
        patch.set_edgecolor('black')
        patch.set_alpha(0.7)

    ax1.set_title('Score Distribution (Violin + Box Plot)')
    ax1.set_ylabel('EXAM Score (Lower is Better)')
    ax1.set_xticks(np.arange(1, len(labels) + 1))
    ax1.set_xticklabels(labels)
    ax1.grid(True, linestyle='--', alpha=0.6)

    # 2. Bar Chart (Average Performance)
    avgs = [np.mean(d) for d in scores_data]
    x_pos = np.arange(len(labels))
    
    bars = ax2.bar(x_pos, avgs, align='center', alpha=0.8, color='#4682B4', capsize=10)
    ax2.set_xticks(x_pos)
    ax2.set_xticklabels(labels)
    ax2.set_ylabel('Average EXAM Score')
    ax2.set_title('Average Performance Comparison')
    ax2.grid(axis='y', linestyle='--', alpha=0.5)
    
    # Add values on top of bars
    for bar in bars:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.4f}', ha='center', va='bottom')

    plt.tight_layout()
    # Save file
    filename = output_path / "benchmark_combined_distribution.png"
    plt.savefig(filename)
    print(f"Graphs saved to: {filename}") 

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
            RUN_PARALLEL, 
            f"Eval {tech_name}", 
            diff_paths, 
            _process_mutation, 
            fl_technique, 
            killed_dir, 
            original_dir
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