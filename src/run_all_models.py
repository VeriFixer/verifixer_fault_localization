import argparse
import shutil
from pathlib import Path
from typing import Any
from fl_eval.util.run_parallel_or_seq import run_parallel_or_seq
from fl_eval.metrics.scoring import ExamOutput
import config as gl
from logging_config import get_logger
from run_1_model import (
        TECHNIQUE_MAP, 
        _setup_evaluation,  # type: ignore
        _process_mutation  # type: ignore
    )
from analysis.data_analysis import print_ascii_table, print_latex_table, generate_plots

logger = get_logger(__name__)

def run_benchmark(base_path: Path, sequential: bool = False) -> None:
    logger.info(f"Starting Benchmark on: {base_path}")
    logger.info(f"Techniques to run: {list(TECHNIQUE_MAP.keys())}")
    raw_results: dict[str, list[ExamOutput]] = {}
    stats_summary: dict[str, dict[str, Any]] = {}
    
    for tech_name in TECHNIQUE_MAP:
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
            parallel= not sequential
        )
        scores_clean = [s for s in scores_dirty if s is not None]
        raw_results[tech_name] = scores_clean
        if scores_clean:
            avg = sum([s.score for s in scores_clean]) / len(scores_clean)
            found_pct = (sum([s.found for s in scores_clean]) / len(scores_clean)) * 100
            exist = sum([s.empty for s in scores_clean]) / len(scores_clean)
        else:
            avg = 0.0
            found_pct = 0.0
            exist = 0.0
        stats_summary[tech_name] = {
            'count': len(scores_clean),
            'avg_exam': avg,
            'found_rate': found_pct,
            'exist_rate' : exist
        }
    if not stats_summary:
        logger.info("No results collected.")
        return
    print_ascii_table(stats_summary)  # type: ignore
    print_latex_table(stats_summary)  # type: ignore
    try:
        generate_plots(raw_results, base_path.parent)  # type: ignore
    except Exception as e:
        logger.error(f"Could not generate plots: {e}")

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

    cache_dir = gl.CACHE_DIR
    if args.clean_cache:
        logger.info("Cleaning: Results Cache")
        if cache_dir.exists():
            try:
                shutil.rmtree(cache_dir)
                logger.info(f"Removed cache directory: {cache_dir}")
            except OSError as e:
                logger.error(f"Could not remove cache directory {cache_dir}: {e}")
        else:
            logger.warning(f"No cache directory found at: {cache_dir}")
    else:
        logger.info(f"Using cached results if any at {cache_dir}")
  
    run_benchmark(args.data_path, args.sequential)