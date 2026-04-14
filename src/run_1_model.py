
import argparse
from pathlib import Path

from logging_config import get_logger
from fl_eval.metrics.scoring import ExamOutput
from fl_eval.metrics.summary_stats import StatsSummaryEntry
from fl_eval.util.run_model_common import (
    TECHNIQUE_MAP,
    add_run_control_args,
    generate_report,
    prepare_dataset_cache,
)
from run_1_model_1_example import compute_metrics_one_example

from fl_eval.util.run_parallel_or_seq import run_parallel_or_seq

logger = get_logger(__name__)

def _evaluate_single_mutant(
    mutant_dfy_path: Path,
    flt_name: str,
    enable_pretty_output: bool,
) -> ExamOutput | None:
    try:
        _, score, _, _, _ = compute_metrics_one_example(
            flt_name,
            mutant_dfy_path,
            enable_pretty_output=enable_pretty_output,
        )
        return score
    except Exception as e:
        logger.error("Error processing %s: %s", mutant_dfy_path.name, e)
        return None


# --- Orchestrator Function ---
def compute_metrics_one_dataset(
    flt_name: str,
    base_path: Path,
    sequential: bool = False,
    enable_pretty_output: bool = False,
) -> tuple[StatsSummaryEntry, list[ExamOutput]] | None:
    """
    Receives a technique name and directory, iterates through mutation files, 
    computes EXAM scores, and reports the average.
    
    Args:
        flt_name: Name of the fault localization technique
        base_path: Path to the dataset directory containing 'killed' and 'original' subdirectories
        sequential: If True, run evaluations sequentially; otherwise run in parallel
    """
    if flt_name not in TECHNIQUE_MAP:
        logger.error("Fault Localization Technique '%s' not recognized.", flt_name)
        logger.error("Available techniques: %s", list(TECHNIQUE_MAP.keys()))
        return None

    killed_dir = base_path / "killed"
    if not killed_dir.exists():
        logger.error("Killed directory not found: %s", killed_dir)
        return None

    if enable_pretty_output and not sequential:
        logger.warning(
            "Pretty output requested in parallel mode; disabling to avoid interleaved terminal output. "
            "Use --sequential with --pretty-output."
        )
        enable_pretty_output = False

    diff_paths = sorted(killed_dir.glob("*.txt"))
    mutant_paths: list[Path] = []
    for diff_path in diff_paths:
        canonical_mutant = killed_dir / f"{diff_path.stem}.dfy"
        if canonical_mutant.exists():
            mutant_paths.append(canonical_mutant)
            continue

        fallback_test_mutant = killed_dir / f"{diff_path.stem}.test.dfy"
        if fallback_test_mutant.exists():
            mutant_paths.append(fallback_test_mutant)
            continue

        logger.warning("No mutant .dfy found for diff %s; skipping.", diff_path.name)

    all_scores = run_parallel_or_seq(
        mutant_paths,
        _evaluate_single_mutant,
        f"Get metrics for {flt_name}",
        flt_name,
        enable_pretty_output,
        parallel=not sequential,
    )
    all_scores_clean: list[ExamOutput] = [x for x in all_scores if x is not None]
    summary = generate_report(flt_name, all_scores_clean)

    return summary, all_scores_clean



if __name__ == "__main__":
    # Define a clear usage example for the epilog
    USAGE_EXAMPLE = """"
How to use:
  Run the script from the project root directory.

    Example 1: Evaluate the 'random' technique using data in 'datasets/pos_test'
        $ python src/main.py random datasets/pos_test

  Example 2: Evaluate a hypothetical 'tarantula' technique using data in 'data/mutants'
    $ python src/main.py tarantula data/mutants
"""
    
    parser = argparse.ArgumentParser(
        description="Compute Fault Localization metrics (EXAM score) for a given technique.",
        formatter_class=argparse.RawTextHelpFormatter, # Required to correctly format the multiline epilog
        epilog=USAGE_EXAMPLE
    )
    
    parser.add_argument(
        "technique_name", 
        type=str, 
        choices=TECHNIQUE_MAP.keys(),
        help="The name of the Fault Localization technique to evaluate (e.g., 'random')."
    )

    parser.add_argument(
        "data_path", 
        type=Path,
        help="The path to the parent directory containing the 'killed' and 'original' folders (e.g., datasets/pos_test)."
    )

    add_run_control_args(parser)

    parser.add_argument(
        "--pretty-output",
        action="store_true",
        help="Forward rich single-file trace output; only effective with --sequential.",
    )
     
    args = parser.parse_args()
    

    if not prepare_dataset_cache(args.data_path, args.clean_cache):
        parser.print_help()
    else:
        compute_metrics_one_dataset(
            args.technique_name,
            args.data_path,
            args.sequential,
            enable_pretty_output=args.pretty_output,
        )
