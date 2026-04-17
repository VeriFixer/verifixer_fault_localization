import argparse
from pathlib import Path

import config as gl
from analysis.data_analysis import generate_plots, print_ascii_table, print_latex_table
from fl_eval.metrics.scoring import ExamOutput
from fl_eval.metrics.summary_stats import StatsSummaryEntry
from runners.run_model_common import (
    get_techniques_for_all_models,
    get_techniques_for_cntm_ablation,
    get_techniques_for_health_check,
    get_techniques_for_paper_only,
    prepare_dataset_cache,
)
from fl_eval.execution.parallel_executor import shutdown_parallel_executor
from logging_config import get_logger
from runners.run_1_model import compute_metrics_one_dataset

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


def run_models_for_techniques(
    base_path: Path,
    techniques_to_run: list[str],
    sequential: bool = False,
    use_paper_names: bool = False,
) -> None:
    try:
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

        print_ascii_table(stats_summary, paper_only=use_paper_names)
        print_latex_table(stats_summary, paper_only=use_paper_names)
        _log_benchmark_llm_cost_totals(llm_cost_totals_by_technique)

        try:
            images_dir = gl.IMAGES_DIR
            images_dir.mkdir(parents=True, exist_ok=True)
            generate_plots(raw_results, images_dir, paper_only=use_paper_names)  # type: ignore[arg-type]
            logger.info(f"Plot artifacts saved to: {images_dir}")
        except Exception as e:
            logger.error(f"Could not generate plots: {e}")
    finally:
        shutdown_parallel_executor(wait=True)


def _get_techniques_for_set(models_set: str) -> list[str]:
    if models_set == "all":
        return get_techniques_for_all_models()
    if models_set == "paper":
        return get_techniques_for_paper_only()
    if models_set == "health-check":
        return get_techniques_for_health_check()
    if models_set == "cntm-ablation":
        return get_techniques_for_cntm_ablation()
    raise ValueError(f"Unsupported models set: {models_set}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run selected Fault Localization technique sets on a dataset."
    )
    parser.add_argument(
        "data_path",
        type=Path,
        help="Path to dataset directory (containing 'killed' and 'original' folders).",
    )
    parser.add_argument(
        "--models-set",
        type=str,
        default="all",
        choices=["all", "paper", "health-check", "cntm-ablation"],
        help="Predefined technique set to run.",
    )
    parser.add_argument(
        "--clean-cache",
        action="store_true",
        help="Clean cached results before running",
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Run evaluations sequentially",
    )
    parser.add_argument(
        "--use-paper-names",
        action="store_true",
        help="Use publication aliases in tables/plots.",
    )

    args = parser.parse_args()
    if not prepare_dataset_cache(args.data_path, args.clean_cache):
        return 1

    techniques_to_run = _get_techniques_for_set(args.models_set)
    run_models_for_techniques(
        args.data_path,
        techniques_to_run,
        sequential=args.sequential,
        use_paper_names=args.use_paper_names,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
