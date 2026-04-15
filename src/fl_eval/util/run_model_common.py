import argparse
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import config as gl
from fl_eval.core.abstract import FLTechnique
from fl_eval.core.gt_parser import GroundTruthAndLineLimit
from fl_eval.metrics.scoring import ExamOutput, compute_exam_score
from fl_eval.metrics.summary_stats import StatsSummaryEntry, build_summary_entry
from fl_eval.strategies.autofix_ranker import AutoFixRanker
from fl_eval.strategies.counter_example_base_ranker import CounterExampleBaseRanker
from fl_eval.strategies.counter_example_if import CounterExampleIf
from fl_eval.strategies.counter_example_if_reassume import CounterExampleIfReassume
from fl_eval.strategies.empty_ranker import EmptyRanker
from fl_eval.strategies.llm_ranker import LLMRanker
from fl_eval.strategies.random_line_of_method_that_fails import RandomLineOfMethodThatFails
from fl_eval.strategies.random_ranker import RandomRanker
from fl_eval.util.dataset_validation import log_validation_result, validate_dataset
from logging_config import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class TechniqueConfig:
    technique_class: type[FLTechnique]
    run_on_all_models: bool = False
    autofix_strategy: str = ""


@dataclass(frozen=True)
class MutationContext:
    diff_path: Path
    mutant_dfy_path: Path
    original_file: Path
    gtruth: GroundTruthAndLineLimit


TECHNIQUE_CONFIG: dict[str, TechniqueConfig] = {
    "random": TechniqueConfig(RandomRanker, run_on_all_models=True),
    "counterBase": TechniqueConfig(CounterExampleBaseRanker, run_on_all_models=True),
    "empty": TechniqueConfig(EmptyRanker, run_on_all_models=True),
    "randomOnFailingMethod": TechniqueConfig(RandomLineOfMethodThatFails, run_on_all_models=True),
    "counterExampleIf": TechniqueConfig(CounterExampleIf, run_on_all_models=True),
    "counterExampleIfReassume": TechniqueConfig(CounterExampleIfReassume, run_on_all_models=True),
    "autofixDefault": TechniqueConfig(AutoFixRanker, autofix_strategy="dynamic-and-static-score", run_on_all_models=False),
    #"autofixSimplified": TechniqueConfig(AutoFixRanker, autofix_strategy="dynamic-score-only", run_on_all_models=True),
    "llm_without_api": TechniqueConfig(LLMRanker, run_on_all_models=False),
    "llm_real": TechniqueConfig(LLMRanker, run_on_all_models=True),
}


TECHNIQUE_MAP: dict[str, tuple[type[FLTechnique], str]] = {
    name: (cfg.technique_class, cfg.autofix_strategy) for name, cfg in TECHNIQUE_CONFIG.items()
}

PAPER_ONLY_TECHNIQUES: list[str] = [
    "randomOnFailingMethod",
    "counterBase",
    "counterExampleIfReassume",
    "llm_real",
    "autofixDefault",
]

PAPER_TECHNIQUE_ALIASES: dict[str, str] = {
    "randomOnFailingMethod": "RAND",
    "counterBase": "CNTS",
    "counterExampleIfReassume": "CNTM",
    "llm_real": "LLM",
    "autofixDefault": "SNAP",
}


def get_techniques_for_all_models() -> list[str]:
    """Return techniques explicitly enabled for run_all_models and guard pipelines."""
    return [name for name, cfg in TECHNIQUE_CONFIG.items() if cfg.run_on_all_models]


def get_techniques_for_paper_only() -> list[str]:
    """Return final-paper technique subset.

    Missing techniques are skipped so this remains resilient if a strategy is
    temporarily unavailable in local environments.
    """
    return [name for name in PAPER_ONLY_TECHNIQUES if name in TECHNIQUE_MAP]


def get_technique_display_name(name: str) -> str:
    """Return publication-friendly display name for a technique key."""
    return PAPER_TECHNIQUE_ALIASES.get(name, name)


def get_techniques_for_health_check() -> list[str]:
    """Return fast techniques for lightweight health checks (excludes autofix and LLM).
    
    This subset is fast enough for CI/local pre-commit checks without sacrificing
    core functionality validation.
    """
    # Exclude autofix (slow, long-running) and LLM techniques
    excluded = {"autofixDefault", "autofixSimplified", "llm_stub_all_lines_ranked", "llm_qwen_480b"}
    return [
        name for name, cfg in TECHNIQUE_CONFIG.items() 
        if cfg.run_on_all_models and name not in excluded
    ]


def setup_evaluation(flt_name: str, base_path: Path, to_validate_dataset : bool = True) -> tuple[FLTechnique, Path, Path] | None:
    """Validate technique/dataset and return technique, killed_dir and original_dir."""
    if flt_name not in TECHNIQUE_MAP:
        logger.error(f"Fault Localization Technique '{flt_name}' not recognized.")
        logger.error(f"Available techniques: {list(TECHNIQUE_MAP.keys())}")
        return None

    FLT_Class = TECHNIQUE_MAP[flt_name][0]
    autofix_strategy = TECHNIQUE_MAP[flt_name][1]
    if FLT_Class == AutoFixRanker:
        fl_technique = FLT_Class(name=flt_name, autofix_strategy=autofix_strategy)
    else:
        fl_technique = FLT_Class(name=flt_name)

    if(to_validate_dataset):
        validation_result = validate_dataset(base_path)
        log_validation_result(validation_result, base_path)

        if not validation_result.is_valid:
            logger.error(
            f"Dataset validation detected issues for {base_path}. "
            f"Continuing with evaluation but some mutations may be skipped. "
            f"Issues: {len([m for m in validation_result.messages if 'validation' not in m.lower()])} errors detected."
            )

    return fl_technique, base_path / "killed", base_path / "original"


def process_mutation(
    diff_path: Path,
    fl_technique: FLTechnique,
    killed_dir: Path,
    original_dir: Path,
    dataset_dir: Path,
) -> Optional[ExamOutput]:
    """Process one mutation and return EXAM output, or None if it fails."""
    context = build_mutation_context(diff_path, killed_dir, original_dir)
    if context is None:
        return None

    try:
        return compute_exam_score(fl_technique, context.gtruth, dataset_dir)

    except ValueError as e:
        logger.error(f"Error processing {context.diff_path.stem} (Value Error): {e}. Skipping.")
    except IOError as e:
        logger.error(f"File error processing {context.diff_path.stem}: {e}. Skipping.")
    except Exception as e:
        logger.error(f"An unexpected error occurred for {context.diff_path.stem}: {e}. Skipping.")

    return None


def build_mutation_context(diff_path: Path, killed_dir: Path, original_dir: Path) -> MutationContext | None:
    """Resolve a diff path into all mutation files needed for evaluation."""
    mutation_name = diff_path.stem
    mutant_candidates = [
        killed_dir / f"{mutation_name}.dfy",
        killed_dir / f"{mutation_name}.test.dfy",
    ]
    mutant_dfy_path = next((p for p in mutant_candidates if p.is_file()), None)

    if mutant_dfy_path is None:
        logger.warning(f"Corresponding mutant file not found for {diff_path}. Skipping.")
        return None

    base_name_raw = "__".join(mutation_name.split("__")[:-1])
    original_file = original_dir / f"{base_name_raw}.dfy"

    if not original_file.is_file():
        logger.error(f"Original file '{original_file.name}' not found. Skipping {mutation_name}.")
        return None

    gtruth = GroundTruthAndLineLimit(
        originalfile=original_file,
        mutantfile=mutant_dfy_path,
        difffile=diff_path,
    )
    return MutationContext(
        diff_path=diff_path,
        mutant_dfy_path=mutant_dfy_path,
        original_file=original_file,
        gtruth=gtruth,
    )


def execute_single_mutation(
    flt_name: str,
    mutant_dfy_path: Path,
    to_validate_dataset: bool = False,
) -> tuple[FLTechnique, ExamOutput, MutationContext, Path] | None:
    """Run one technique for one mutant file and return execution output."""
    base_path = mutant_dfy_path.parent.parent
    setup_result = setup_evaluation(flt_name, base_path, to_validate_dataset=to_validate_dataset)
    if setup_result is None:
        return None

    fl_technique, killed_dir, original_dir = setup_result
    mutant_stem = mutant_dfy_path.stem
    diff_candidates: list[Path] = [killed_dir / f"{mutant_stem}.txt"]
    if mutant_stem.endswith(".test"):
        diff_candidates.append(killed_dir / f"{mutant_stem[:-5]}.txt")

    diff_path = next((p for p in diff_candidates if p.exists()), None)
    if diff_path is None:
        logger.error(
            "Diff file not found for mutant %s. Tried: %s",
            mutant_dfy_path.name,
            ", ".join(str(p) for p in diff_candidates),
        )
        return None

    context = build_mutation_context(diff_path, killed_dir, original_dir)
    if context is None:
        return None

    score = process_mutation(diff_path, fl_technique, killed_dir, original_dir, base_path)
    if score is None:
        return None

    return fl_technique, score, context, base_path


def generate_report(flt_name: str, all_scores: list[ExamOutput]) -> StatsSummaryEntry:
    """Build summary stats and log a dual-scope evaluation report."""
    summary = build_summary_entry(all_scores)

    if not all_scores:
        logger.info("\nNo mutations were successfully evaluated.")
        return summary

    logger.info("\n" + "=" * 76)
    logger.info(f"{'EVALUATION SUMMARY':^76}")
    logger.info("=" * 76)
    logger.info(f"{'Technique':38}: {flt_name.upper()}")
    logger.info(f"{'Evaluated Mutations':38}: {summary.count}")
    logger.info("-" * 76)
    logger.info("FILE-SCOPE METRICS")
    logger.info(f"{'Avg EXAM (All)':38}: {summary.avg_exam_file:.6f}")
    logger.info(f"{'Avg EXAM (Found Only)':38}: {summary.avg_exam_found_file:.6f}")
    logger.info(f"{'Avg EXAM (Pred != Empty)':38}: {summary.avg_exam_not_empty_file:.6f}")
    logger.info(f"{'Fault Found (%)':38}: {summary.found_rate_file:.6f}")
    logger.info(f"{'Empty Predictions Rate':38}: {summary.exist_rate_file:.6f}")
    logger.info(f"{'Top-1 Success (%)':38}: {summary.top1_success_file:.6f}")
    logger.info(f"{'Top-3 Success (%)':38}: {summary.top3_success_file:.6f}")
    logger.info(f"{'Top-5 Success (%)':38}: {summary.top5_success_file:.6f}")
    logger.info("-" * 76)
    logger.info("METHOD-SCOPE METRICS")
    logger.info(f"{'Evaluated Methods':38}: {summary.count_method}")
    logger.info(f"{'Avg EXAM (All)':38}: {summary.avg_exam_method:.6f}")
    logger.info(f"{'Avg EXAM (Found Only)':38}: {summary.avg_exam_found_method:.6f}")
    logger.info(f"{'Avg EXAM (Pred != Empty)':38}: {summary.avg_exam_not_empty_method:.6f}")
    logger.info(f"{'Fault Found (%)':38}: {summary.found_rate_method:.6f}")
    logger.info(f"{'Empty Predictions Rate':38}: {summary.exist_rate_method:.6f}")
    logger.info(f"{'Top-1 Success (%)':38}: {summary.top1_success_method:.6f}")
    logger.info(f"{'Top-3 Success (%)':38}: {summary.top3_success_method:.6f}")
    logger.info(f"{'Top-5 Success (%)':38}: {summary.top5_success_method:.6f}")
    logger.info("=" * 76 + "\n")
    return summary


def add_run_control_args(parser: argparse.ArgumentParser) -> None:
    """Add shared run-control flags used by runner CLIs."""
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


def prepare_dataset_cache(data_path: Path, clean_cache: bool) -> bool:
    """Validate dataset path and prepare dataset cache directory state.

    Returns:
        True when the data path is valid and execution can continue.
    """
    if not data_path.exists():
        logger.error(f"Path not found: {data_path}")
        return False

    dataset_cache_dir = gl.get_dataset_cache_dir(data_path)
    if clean_cache:
        logger.info(f"Cleaning: Results Cache for dataset '{data_path.name}'")
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

    return True
