import argparse
from pathlib import Path
from fl_eval.util.run_parallel_or_seq import shutdown_parallel_executor
from fl_eval.metrics.scoring import ExamOutput
from fl_eval.metrics.summary_stats import StatsSummaryEntry
from fl_eval.util.run_model_common import (
    add_run_control_args,
    get_techniques_for_all_models,
    get_techniques_for_health_check,
    prepare_dataset_cache,
)
from run_1_model import compute_metrics_one_dataset
from logging_config import get_logger
from analysis.data_analysis import print_ascii_table, print_latex_table, generate_plots
import config as gl

logger = get_logger(__name__)

def compute_metrics(base_path: Path, sequential: bool = False, health_check: bool = False) -> None:
    try:
        techniques_to_run = (
            get_techniques_for_health_check()
            if health_check
            else get_techniques_for_all_models()
        )
        logger.info(f"Starting Benchmark on: {base_path}")
        logger.info(f"Techniques to run: {techniques_to_run}")
        raw_results: dict[str, list[ExamOutput]] = {}
        stats_summary: dict[str, StatsSummaryEntry] = {}

        for tech_name in techniques_to_run:
            logger.info(f"\n--- Running {tech_name.upper()} ---")
            metrics_output = compute_metrics_one_dataset(tech_name, base_path, sequential)
            if metrics_output is None:
                logger.warning(f"Skipping {tech_name} due to setup failure.")
                continue

            summary, scores_clean = metrics_output
            raw_results[tech_name] = scores_clean
            stats_summary[tech_name] = summary
        if not stats_summary:
            logger.info("No results collected.")
            return
        print_ascii_table(stats_summary)
        print_latex_table(stats_summary)
        try:
            images_dir = gl.BASE_PATH / "images"
            images_dir.mkdir(parents=True, exist_ok=True)
            generate_plots(raw_results, images_dir)  # type: ignore
            logger.info(f"Plot artifacts saved to: {images_dir}")
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
    add_run_control_args(parser)

    parser.add_argument(
      "--health-check",
      action="store_true",
      help="Run reduced technique set for repository health checks (skips slow techniques)."
    )

    args = parser.parse_args()
    if prepare_dataset_cache(args.data_path, args.clean_cache):
        compute_metrics(args.data_path, args.sequential, args.health_check)
