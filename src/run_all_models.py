import argparse
import shutil
from pathlib import Path
from fl_eval.util.run_parallel_or_seq import run_parallel_or_seq, shutdown_parallel_executor
from fl_eval.metrics.scoring import ExamOutput
from fl_eval.metrics.summary_stats import StatsSummaryEntry, build_summary_entry
import config as gl
from logging_config import get_logger
from run_1_model import (
    get_techniques_for_all_models,
    _setup_evaluation,  # type: ignore
    _process_mutation,  # type: ignore
)
from analysis.data_analysis import print_ascii_table, print_latex_table, generate_plots

logger = get_logger(__name__)

def run_benchmark(base_path: Path, sequential: bool = False) -> None:
    try:
        techniques_to_run = get_techniques_for_all_models()
        logger.info(f"Starting Benchmark on: {base_path}")
        logger.info(f"Techniques to run: {techniques_to_run}")
        raw_results: dict[str, list[ExamOutput]] = {}
        stats_summary: dict[str, StatsSummaryEntry] = {}

        for tech_name in techniques_to_run:
            logger.info(f"\n--- Running {tech_name.upper()} ---")
            setup_res = _setup_evaluation(tech_name, base_path)
            if not setup_res:
                logger.warning(f"Skipping {tech_name} due to setup failure.")
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
                base_path,
                parallel=not sequential
            )
            scores_clean = [s for s in scores_dirty if s is not None]
            raw_results[tech_name] = scores_clean
            stats_summary[tech_name] = build_summary_entry(scores_clean)
        if not stats_summary:
            logger.info("No results collected.")
            return
        print_ascii_table(stats_summary)
        print_latex_table(stats_summary)
        try:
            generate_plots(raw_results, base_path.parent)  # type: ignore
        except Exception as e:
            logger.error(f"Could not generate plots: {e}")
    finally:
        shutdown_parallel_executor(wait=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark ALL Fault Localization techniques.")
    parser.add_argument(
        "data_path", 
        type=Path,
        help="Path to the directory containing 'killed' and 'original' folders."
    )

    parser.add_argument(
      "--clean-cache",
      action="store_true",
      help="Clean cached results before running"
    )

    parser.add_argument(
      "--sequential",
      action="store_true",
      help="Run evaluations sequentially"
    )
    
    args = parser.parse_args()
    if not args.data_path.exists():
        logger.error(f"Path not found: {args.data_path}")

    # Compute dataset-specific cache directory
    dataset_cache_dir = gl.get_dataset_cache_dir(args.data_path)
    if args.clean_cache:
        logger.info(f"Cleaning: Results Cache for dataset '{args.data_path.name}'")
        if dataset_cache_dir.exists():
            try:
                shutil.rmtree(dataset_cache_dir)
                logger.info(f"Removed dataset cache directory: {dataset_cache_dir}")
            except OSError as e:
                logger.error(f"Could not remove cache directory {dataset_cache_dir}: {e}")
        else:
            logger.warning(f"No cache directory found at: {dataset_cache_dir}")
    else:
        logger.info(f"Using cached results if any at {dataset_cache_dir}")
  
    run_benchmark(args.data_path, args.sequential)