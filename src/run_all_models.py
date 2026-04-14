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


def _merge_llm_cost_totals(
    aggregate: dict[str, float],
    totals: dict[str, int | float | str],
) -> None:
    numeric_fields = [
        "total_prompts",
        "total_chars_prompted",
        "total_chars_response",
        "total_tokens_input",
        "total_tokens_output",
        "total_tokens_output_reason",
        "cost_input_usd",
        "cost_output_usd",
        "cost_output_reason_usd",
        "total_cost_usd",
        "mutants_total",
        "mutants_with_llm_cost",
    ]
    for key in numeric_fields:
        value = totals.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            aggregate[key] = aggregate.get(key, 0.0) + float(value)


def _log_benchmark_llm_cost_totals(
    llm_totals_by_technique: dict[str, dict[str, int | float | str]],
) -> None:
    if not llm_totals_by_technique:
        return

    aggregate: dict[str, float] = {}
    for totals in llm_totals_by_technique.values():
        _merge_llm_cost_totals(aggregate, totals)

    logger.info("\n" + "=" * 76)
    logger.info(f"{'LLM BENCHMARK COST TOTAL':^76}")
    logger.info("=" * 76)
    logger.info(f"{'Techniques with LLM cost':38}: {len(llm_totals_by_technique)}")
    logger.info(
        f"{'Mutants with LLM cost metadata':38}: "
        f"{int(round(aggregate.get('mutants_with_llm_cost', 0.0)))}/"
        f"{int(round(aggregate.get('mutants_total', 0.0)))}"
    )
    logger.info("-" * 76)
    logger.info(f"{'Total Prompts':38}: {int(round(aggregate.get('total_prompts', 0.0)))}")
    logger.info(f"{'Total Chars Prompted':38}: {int(round(aggregate.get('total_chars_prompted', 0.0)))}")
    logger.info(f"{'Total Chars Response':38}: {int(round(aggregate.get('total_chars_response', 0.0)))}")
    logger.info(f"{'Total Tokens Input':38}: {aggregate.get('total_tokens_input', 0.0):.2f}")
    logger.info(f"{'Total Tokens Output':38}: {aggregate.get('total_tokens_output', 0.0):.2f}")
    logger.info(
        f"{'Total Tokens Output Reason':38}: "
        f"{aggregate.get('total_tokens_output_reason', 0.0):.2f}"
    )
    logger.info(f"{'Cost Input ($)':38}: {aggregate.get('cost_input_usd', 0.0):.6f}")
    logger.info(f"{'Cost Output ($)':38}: {aggregate.get('cost_output_usd', 0.0):.6f}")
    logger.info(
        f"{'Cost Output Reason ($)':38}: "
        f"{aggregate.get('cost_output_reason_usd', 0.0):.6f}"
    )
    logger.info(f"{'Total Cost ($)':38}: {aggregate.get('total_cost_usd', 0.0):.6f}")
    logger.info("=" * 76)

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
        llm_cost_totals_by_technique: dict[str, dict[str, int | float | str]] = {}

        for tech_name in techniques_to_run:
            logger.info(f"\n--- Running {tech_name.upper()} ---")
            metrics_output = compute_metrics_one_dataset(tech_name, base_path, sequential)
            if metrics_output is None:
                logger.warning(f"Skipping {tech_name} due to setup failure.")
                continue

            summary, scores_clean, llm_cost_totals = metrics_output
            raw_results[tech_name] = scores_clean
            stats_summary[tech_name] = summary
            if llm_cost_totals is not None:
                llm_cost_totals_by_technique[tech_name] = llm_cost_totals
        if not stats_summary:
            logger.info("No results collected.")
            return
        print_ascii_table(stats_summary)
        print_latex_table(stats_summary)
        _log_benchmark_llm_cost_totals(llm_cost_totals_by_technique)
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
    parser = argparse.ArgumentParser(
        description="Benchmark ALL Fault Localization techniques. For LLM-based techniques, set LLM_REAL_MODEL_NAME env var to select model (e.g., 'qwen3-coder-480b')."
    )
    parser.add_argument(
        "data_path",
        type=Path,
        help="Path to dataset directory (containing 'killed' and 'original' folders). For LLM: set LLM_REAL_MODEL_NAME env var to select model."
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
