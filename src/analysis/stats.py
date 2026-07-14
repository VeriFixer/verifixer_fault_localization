import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fl_eval.metrics.scoring import ExamOutput
from analysis.data_analysis import (
    build_pairwise_stat_results,
    build_pairwise_topk_results,
    print_pairwise_topk_latex_table,
    print_pairwise_topk_table,
    print_pairwise_wilcoxon_latex_table,
    print_pairwise_wilcoxon_table,
)


STATISTICS_TECHNIQUES = ["RAND", "CNTB", "CNTS", "CNTM", "LLM", "SNAP"]


def run_file_scope_statistics(
    raw_results: dict[str, list[ExamOutput]],
    paper_only: bool = False,
) -> None:
    """Print file-scope Wilcoxon and Top-1 McNemar results in fixed order."""
    ordered_results = {
        technique: raw_results[technique]
        for technique in STATISTICS_TECHNIQUES
        if technique in raw_results and raw_results[technique]
    }
    if len(ordered_results) < 2:
        print("\nNo comparable technique pairs found for file-scope statistics.")
        return

    wilcoxon_results = build_pairwise_stat_results(ordered_results, scope="file")
    if wilcoxon_results:
        print_pairwise_wilcoxon_table(ordered_results, paper_only=paper_only, scope="file")
        print_pairwise_wilcoxon_latex_table(
            wilcoxon_results,
            paper_only=paper_only,
            scope="file",
        )
    else:
        print_pairwise_wilcoxon_table(ordered_results, paper_only=paper_only, scope="file")

    mcnemar_results = build_pairwise_topk_results(ordered_results, scope="file", k=1)
    if mcnemar_results:
        print_pairwise_topk_table(ordered_results, paper_only=paper_only, scope="file", k=1)
        print_pairwise_topk_latex_table(
            mcnemar_results,
            paper_only=paper_only,
            scope="file",
            k=1,
        )
    else:
        print_pairwise_topk_table(ordered_results, paper_only=paper_only, scope="file", k=1)


def main() -> int:
    from runners.run_1_model import compute_metrics_one_dataset
    from runners.run_common import parse_common_runner_args
    from runners.run_model_common import prepare_dataset_cache
    from fl_eval.execution.parallel_executor import shutdown_parallel_executor
    from logging_config import get_logger

    logger = get_logger(__name__)

    args = parse_common_runner_args(
        "Run file-scope Wilcoxon and Top-1 McNemar statistical tests for the fixed "
        f"technique order ({', '.join(STATISTICS_TECHNIQUES)})."
    )
    if not prepare_dataset_cache(args.data_path, args.clean_cache):
        return 1

    raw_results: dict[str, list[ExamOutput]] = {}
    try:
        for tech_name in STATISTICS_TECHNIQUES:
            logger.info(f"\n--- Running {tech_name.upper()} ---")
            metrics_output = compute_metrics_one_dataset(
                tech_name,
                args.data_path,
                args.sequential,
                reduce=args.reduce,
                show_llm_costs=False,
            )
            if metrics_output is None:
                logger.warning(f"Skipping {tech_name} due to setup failure.")
                continue
            _, scores_clean, _ = metrics_output
            raw_results[tech_name] = scores_clean
    finally:
        shutdown_parallel_executor(wait=True)

    if not raw_results:
        logger.info("No results collected; no statistics generated.")
        return 1

    run_file_scope_statistics(raw_results, paper_only=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
