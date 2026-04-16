
import argparse
import json
import logging
from pathlib import Path
from typing import Any

import config as gl
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

LLM_TECHNIQUES = {"LLM", "LLM_NO_API"}


def _enable_model_file_logging(technique_name: str) -> None:
    """Mirror logs to run_artifacts/models_log/<technique_name>.log."""
    logs_dir = gl.BASE_PATH / "run_artifacts" / "models_log"
    log_file = logs_dir / f"{technique_name}.log"

    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.warning("Could not create model log directory %s: %s", logs_dir, e)
        return

    root_logger = logging.getLogger()
    target_path = str(log_file.resolve())
    for handler in root_logger.handlers:
        if isinstance(handler, logging.FileHandler):
            existing_path = str(Path(handler.baseFilename).resolve())
            if existing_path == target_path:
                return

    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)-8s] [%(name)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(root_logger.level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    logger.info("Model log file enabled: %s", log_file)


def _is_llm_technique(flt_name: str) -> bool:
    """Check if a technique is LLM-based and requires sequential execution."""
    return  flt_name in  LLM_TECHNIQUES


LLM_COST_NUMERIC_FIELDS = [
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
]


def _sum_llm_costs_from_cache(
    base_path: Path,
    flt_name: str,
    mutant_paths: list[Path],
) -> dict[str, int | float | str] | None:
    dataset_cache_dir = gl.get_dataset_cache_dir(base_path)
    technique_cache_dir = dataset_cache_dir / flt_name

    totals: dict[str, float] = {key: 0.0 for key in LLM_COST_NUMERIC_FIELDS}
    mutants_with_llm_cost = 0
    model_name = ""
    model_id = ""

    for mutant_path in mutant_paths:
        cache_file = technique_cache_dir / f"{mutant_path.name}.json"
        if not cache_file.exists():
            continue

        try:
            with cache_file.open("r", encoding="utf-8") as f:
                payload: Any = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Could not read cache file %s: %s", cache_file, e)
            continue

        if not isinstance(payload, dict):
            continue

        execution_metadata = payload.get("execution_metadata")
        if not isinstance(execution_metadata, dict):
            continue

        llm_cost = execution_metadata.get("llm_cost")
        if not isinstance(llm_cost, dict):
            continue

        mutants_with_llm_cost += 1
        raw_model_name = llm_cost.get("model_name")
        raw_model_id = llm_cost.get("model_id")
        if isinstance(raw_model_name, str) and raw_model_name:
            model_name = raw_model_name
        if isinstance(raw_model_id, str) and raw_model_id:
            model_id = raw_model_id

        for key in LLM_COST_NUMERIC_FIELDS:
            value = llm_cost.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                totals[key] += float(value)

    if mutants_with_llm_cost == 0:
        return None

    return {
        "model_name": model_name,
        "model_id": model_id,
        "mutants_total": len(mutant_paths),
        "mutants_with_llm_cost": mutants_with_llm_cost,
        "total_prompts": int(round(totals["total_prompts"])),
        "total_chars_prompted": int(round(totals["total_chars_prompted"])),
        "total_chars_response": int(round(totals["total_chars_response"])),
        "total_tokens_input": totals["total_tokens_input"],
        "total_tokens_output": totals["total_tokens_output"],
        "total_tokens_output_reason": totals["total_tokens_output_reason"],
        "cost_input_usd": totals["cost_input_usd"],
        "cost_output_usd": totals["cost_output_usd"],
        "cost_output_reason_usd": totals["cost_output_reason_usd"],
        "total_cost_usd": totals["total_cost_usd"],
    }


def _log_llm_cost_totals(flt_name: str, totals: dict[str, int | float | str] | None) -> None:
    if totals is None:
        return

    def _int_value(key: str) -> int:
        value = totals.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(round(float(value)))
        return 0

    def _float_value(key: str) -> float:
        value = totals.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        return 0.0

    def _str_value(key: str) -> str:
        value = totals.get(key)
        return value if isinstance(value, str) else ""

    model_name = _str_value("model_name")
    model_id = _str_value("model_id")
    logger.info("\n" + "=" * 76)
    logger.info(f"{'LLM COST TOTAL':^76}")
    logger.info("=" * 76)
    logger.info(f"{'Technique':38}: {flt_name}")
    if model_name or model_id:
        logger.info(f"{'Model':38}: {model_name} ({model_id})")
    logger.info(
        f"{'Mutants with LLM cost metadata':38}: "
        f"{_int_value('mutants_with_llm_cost')}/{_int_value('mutants_total')}"
    )
    logger.info("-" * 76)
    logger.info(f"{'Total Prompts':38}: {_int_value('total_prompts')}")
    logger.info(f"{'Total Chars Prompted':38}: {_int_value('total_chars_prompted')}")
    logger.info(f"{'Total Chars Response':38}: {_int_value('total_chars_response')}")
    logger.info(f"{'Total Tokens Input':38}: {_float_value('total_tokens_input'):.2f}")
    logger.info(f"{'Total Tokens Output':38}: {_float_value('total_tokens_output'):.2f}")
    logger.info(f"{'Total Tokens Output Reason':38}: {_float_value('total_tokens_output_reason'):.2f}")
    logger.info(f"{'Cost Input ($)':38}: {_float_value('cost_input_usd'):.6f}")
    logger.info(f"{'Cost Output ($)':38}: {_float_value('cost_output_usd'):.6f}")
    logger.info(f"{'Cost Output Reason ($)':38}: {_float_value('cost_output_reason_usd'):.6f}")
    logger.info(f"{'Total Cost ($)':38}: {_float_value('total_cost_usd'):.6f}")
    logger.info("=" * 76)

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
) -> tuple[StatsSummaryEntry, list[ExamOutput], dict[str, int | float | str] | None] | None:
    """
    Receives a technique name and directory, iterates through mutation files, 
    computes EXAM scores, and reports the average.
    
    Args:
        flt_name: Name of the fault localization technique
        base_path: Path to the dataset directory containing 'killed' and 'original' subdirectories
        sequential: If True, run evaluations sequentially; otherwise run in parallel.
                    Note: LLM techniques always force sequential mode.
    """
    # Force sequential mode for LLM techniques for stability
    if _is_llm_technique(flt_name):
        if not sequential:
            logger.info(
                "LLM technique '%s' detected. Forcing sequential mode (LLM techniques require sequential execution).",
                flt_name,
            )
        sequential = True
    
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

    llm_cost_totals = _sum_llm_costs_from_cache(base_path, flt_name, mutant_paths)
    _log_llm_cost_totals(flt_name, llm_cost_totals)

    return summary, all_scores_clean, llm_cost_totals



if __name__ == "__main__":
    # Define a clear usage example for the epilog
    USAGE_EXAMPLE = """"
How to use:
  Run the script from the project root directory.

    Example 1: Evaluate the 'RANDFILE' technique using data in 'datasets/pos_test'
        $ python src/run_1_model.py RANDFILE datasets/pos_test

    Example 2: Evaluate one mutant with a specific LLM model (requires LLM_REAL_MODEL_NAME env var)
        $ LLM_REAL_MODEL_NAME=qwen3-coder-480b python src/run_1_model.py LLM datasets/pos_test/killed/foo__mut1.dfy

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
        help="Fault Localization technique (e.g., 'RANDFILE'). For LLM: use 'LLM' or 'LLM_NO_API'. Set LLM_REAL_MODEL_NAME env var to swap models (e.g., 'qwen3-coder-480b')."
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
        _enable_model_file_logging(args.technique_name)
        compute_metrics_one_dataset(
            args.technique_name,
            args.data_path,
            args.sequential,
            enable_pretty_output=args.pretty_output,
        )
