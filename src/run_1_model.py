
import argparse
from dataclasses import dataclass
from pathlib import Path
import shutil

import config as gl
from logging_config import get_logger
from fl_eval.util.dataset_validation import validate_dataset, log_validation_result
# --- Import Core Components from fl_eval package ---
from fl_eval.core.abstract import FLTechnique

# Import rankers
from fl_eval.strategies.random_ranker  import RandomRanker
from fl_eval.strategies.counter_example_base_ranker import CounterExampleBaseRanker
from fl_eval.strategies.empty_ranker import EmptyRanker
from fl_eval.strategies.random_line_of_method_that_fails import RandomLineOfMethodThatFails
from fl_eval.strategies.counter_example_if import CounterExampleIf
from fl_eval.strategies.counter_example_if_reassume import CounterExampleIfReassume
from fl_eval.strategies.autofix_ranker import AutoFixRanker
from fl_eval.strategies.llm_ranker import LLMRanker


from fl_eval.core.gt_parser import GroundTruthAndLineLimit
from fl_eval.metrics.scoring import compute_exam_score
from fl_eval.metrics.scoring import ExamOutput
from fl_eval.metrics.summary_stats import StatsSummaryEntry, build_summary_entry

from fl_eval.util.run_parallel_or_seq import run_parallel_or_seq

from typing import Optional

logger = get_logger(__name__)

@dataclass(frozen=True)
class TechniqueConfig:
    technique_class: type[FLTechnique]
    run_on_all_models: bool = False


# --- Mapping of Technique Names to Config ---
TECHNIQUE_CONFIG: dict[str, TechniqueConfig] = {
    "random": TechniqueConfig(RandomRanker, run_on_all_models=True),
    "counterBase": TechniqueConfig(CounterExampleBaseRanker, run_on_all_models=True),
    "empty": TechniqueConfig(EmptyRanker, run_on_all_models=True),
    "randomOnFailingMethod": TechniqueConfig(RandomLineOfMethodThatFails, run_on_all_models=True),
    "counterExampleIf": TechniqueConfig(CounterExampleIf, run_on_all_models=True),
    "counterExampleIfReassume": TechniqueConfig(CounterExampleIfReassume, run_on_all_models=True),
    "autofix": TechniqueConfig(AutoFixRanker, run_on_all_models=True),
    "llm_stub_all_lines_ranked": TechniqueConfig(LLMRanker, run_on_all_models=True),
    "llm_without_api": TechniqueConfig(LLMRanker, run_on_all_models=False),
    "llm_qwen_480b": TechniqueConfig(LLMRanker, run_on_all_models=True),
}

# Backwards-compatibility map for callers that only need the class.
TECHNIQUE_MAP: dict[str, type[FLTechnique]] = {
    name: cfg.technique_class for name, cfg in TECHNIQUE_CONFIG.items()
}


def get_techniques_for_all_models() -> list[str]:
    """Return techniques explicitly enabled for run_all_models and guard pipelines."""
    return [name for name, cfg in TECHNIQUE_CONFIG.items() if cfg.run_on_all_models]

def _setup_evaluation(flt_name: str, base_path: Path) -> tuple[FLTechnique, Path, Path] | None:
    """
    Handles validation, FL Technique instantiation, and directory setup.
    Returns the FLT instance and paths if successful, otherwise None.
    
    Note: Dataset validation errors are logged but non-blocking. Processing continues
    with individual mutations handling their own robustness. This allows partial
    evaluation of datasets with minor structural issues.
    """
    # 1. Technique Validation
    if flt_name not in TECHNIQUE_MAP:
        logger.error(f"Fault Localization Technique '{flt_name}' not recognized.")
        logger.error(f"Available techniques: {list(TECHNIQUE_MAP.keys())}")
        return None

    FLT_Class = TECHNIQUE_MAP[flt_name]
    fl_technique = FLT_Class(name=flt_name)

    # 2. Dataset Structure and Consistency Validation
    # Note: Validation errors are logged but do not block evaluation.
    # Individual mutations will handle their own validation during processing.
    validation_result = validate_dataset(base_path)
    log_validation_result(validation_result, base_path)

    if not validation_result.is_valid:
        logger.error(
            f"Dataset validation detected issues for {base_path}. "
            f"Continuing with evaluation but some mutations may be skipped. "
            f"Issues: {len([m for m in validation_result.messages if 'validation' not in m.lower()])} errors detected."
        )

    # 3. Directory Setup
    killed_dir = base_path / "killed"
    original_dir = base_path / "original"

    return fl_technique, killed_dir, original_dir

# --- Helper 2: Process a Single Mutation ---
def _process_mutation(
    diff_path: Path, 
    fl_technique: FLTechnique, 
    killed_dir: Path, 
    original_dir: Path,
    dataset_dir: Path
) -> Optional[ExamOutput]:
    """
    Processes a single mutation file pair, computes the EXAM score, and returns it.
    Returns None if any error occurs.
    
    Args:
        diff_path: Path to the diff file (.txt)
        fl_technique: The fault localization technique instance
        killed_dir: Path to the killed (mutant) directory
        original_dir: Path to the original (passing) directory
        dataset_dir: Path to the dataset directory for dataset-specific caching
    """
    mutation_name = diff_path.stem 
    mutant_dfy_path = killed_dir / f"{mutation_name}.dfy"
    
    if not mutant_dfy_path.is_file():
        logger.warning(f"Corresponding mutant file not found for {diff_path}. Skipping.")
        return None

    try:
        # DYNAMIC ORIGINAL FILE IDENTIFICATION
        base_name_raw = "__".join(mutation_name.split('__')[:-1])
        original_file = original_dir / f"{base_name_raw}.dfy"
        
        if not original_file.is_file():
            logger.error(f"Original file '{original_file.name}' not found. Skipping {mutation_name}.")
            return None

        # Create Ground Truth object and compute score
        gtruth_finder = GroundTruthAndLineLimit(
            originalfile=original_file, 
            mutantfile=mutant_dfy_path, 
            difffile=diff_path
        )
        # Note: compute_exam_score handles calling the FL technique with dataset_dir for dataset-specific caching
        exam_output = compute_exam_score(fl_technique, gtruth_finder, dataset_dir)
        return exam_output

    except ValueError as e:
        logger.error(f"Error processing {mutation_name} (Value Error): {e}. Skipping.")
    except IOError as e:
        logger.error(f"File error processing {mutation_name}: {e}. Skipping.")
    except Exception as e:
        logger.error(f"An unexpected error occurred for {mutation_name}: {e}. Skipping.")
        
    return None

# --- Helper 3: Reporting ---

def _generate_report(flt_name: str, all_scores: list[ExamOutput]) -> StatsSummaryEntry:
    """
    Builds summary stats and logs a detailed dual-scope evaluation report.
    """
    summary = build_summary_entry(all_scores)

    if not all_scores:
        logger.info("\nNo mutations were successfully evaluated.")
        return summary

    # Table formatting
    logger.info("\n" + "=" * 76)
    logger.info(f"{'EVALUATION SUMMARY':^76}")
    logger.info("=" * 76)
    logger.info(f"{'Technique':38}: {flt_name.upper()}")
    logger.info(f"{'Evaluated Mutations':38}: {summary.count}")
    logger.info("-" * 76)
    logger.info("FILE-SCOPE METRICS")
    logger.info(f"{'Avg EXAM':38}: {summary.avg_exam_file:.6f}")
    logger.info(f"{'Avg EXAM (Pred != Empty)':38}: {summary.avg_exam_score_pred_not_empty:.6f}")
    logger.info(f"{'Fault Found (%)':38}: {summary.found_rate_file:.6f}")
    logger.info(f"{'Empty Predictions Rate':38}: {summary.exist_rate_file:.6f}")
    logger.info("-" * 76)
    logger.info("METHOD-SCOPE METRICS")
    logger.info(f"{'Evaluated Methods':38}: {summary.count_method}")
    logger.info(f"{'Avg EXAM':38}: {summary.avg_exam_method:.6f}")
    logger.info(f"{'Avg EXAM (Pred != Empty)':38}: {summary.avg_exam_score_pred_not_empty_method:.6f}")
    logger.info(f"{'Fault Found (%)':38}: {summary.found_rate_method:.6f}")
    logger.info(f"{'Empty Predictions Rate':38}: {summary.exist_rate_method:.6f}")
    logger.info("=" * 76 + "\n")
    return summary

# --- Orchestrator Function ---
def compute_metrics(
    flt_name: str,
    base_path: Path,
    sequential: bool = False,
) -> None:
    """
    Receives a technique name and directory, iterates through mutation files, 
    computes EXAM scores, and reports the average.
    
    Args:
        flt_name: Name of the fault localization technique
        base_path: Path to the dataset directory containing 'killed' and 'original' subdirectories
        sequential: If True, run evaluations sequentially; otherwise run in parallel
    """
    setup_result = _setup_evaluation(flt_name, base_path)
    if setup_result is None:
        return
        
    fl_technique, killed_dir, original_dir = setup_result
    all_scores: list[ExamOutput | None] = []

    diff_paths = list(killed_dir.glob("*.txt"))

    all_scores = run_parallel_or_seq(diff_paths, _process_mutation, f"Get metrics for {flt_name}",
                                     fl_technique, killed_dir, original_dir, base_path, parallel=not sequential)
    all_scores_clean: list[ExamOutput] = [x for x in all_scores if x is not None]
    _generate_report(flt_name, all_scores_clean)

    if flt_name == "llm_stub_all_lines_ranked" and isinstance(fl_technique, LLMRanker):
        print("LLM expected cost:")
        fl_technique.get_costs()



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
    

    # Check if the path exists before proceeding
    if not args.data_path.exists():
        logger.error(f"Data path not found: {args.data_path}")
        parser.print_help()
    else:
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
        compute_metrics(args.technique_name, args.data_path, args.sequential)
