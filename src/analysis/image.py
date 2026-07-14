import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fl_eval.metrics.scoring import ExamOutput
from analysis.data_analysis import generate_plots


IMAGE_TECHNIQUES = ["RAND", "CNTB", "CNTS", "CNTM", "LLM", "SNAP"]


def generate_file_scope_images(
    raw_results: dict[str, list[ExamOutput]],
    output_path: Path,
    paper_only: bool = False,
) -> None:
    """Generate file-scope images for the fixed paper technique order."""
    ordered_results = {
        technique: raw_results[technique]
        for technique in IMAGE_TECHNIQUES
        if technique in raw_results and raw_results[technique]
    }
    if not ordered_results:
        return

    generate_plots(ordered_results, output_path, paper_only=paper_only)


def main() -> int:
    import config as gl
    from runners.run_1_model import compute_metrics_one_dataset
    from runners.run_common import parse_common_runner_args
    from runners.run_model_common import prepare_dataset_cache
    from fl_eval.execution.parallel_executor import shutdown_parallel_executor
    from logging_config import get_logger

    logger = get_logger(__name__)

    args = parse_common_runner_args(
        "Generate file-scope images for the fixed technique order "
        f"({', '.join(IMAGE_TECHNIQUES)})."
    )
    if not prepare_dataset_cache(args.data_path, args.clean_cache):
        return 1

    raw_results: dict[str, list[ExamOutput]] = {}
    try:
        for tech_name in IMAGE_TECHNIQUES:
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
        logger.info("No results collected; no images generated.")
        return 1

    images_dir = gl.IMAGES_DIR
    images_dir.mkdir(parents=True, exist_ok=True)
    generate_file_scope_images(raw_results, images_dir, paper_only=False)
    logger.info(f"Plot artifacts saved to: {images_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
