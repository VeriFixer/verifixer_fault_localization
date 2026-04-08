from dataclasses import dataclass
from pathlib import Path
from typing import Optional

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


TECHNIQUE_CONFIG: dict[str, TechniqueConfig] = {
    "random": TechniqueConfig(RandomRanker, run_on_all_models=True),
    "counterBase": TechniqueConfig(CounterExampleBaseRanker, run_on_all_models=True),
    "empty": TechniqueConfig(EmptyRanker, run_on_all_models=True),
    "randomOnFailingMethod": TechniqueConfig(RandomLineOfMethodThatFails, run_on_all_models=True),
    "counterExampleIf": TechniqueConfig(CounterExampleIf, run_on_all_models=True),
    "counterExampleIfReassume": TechniqueConfig(CounterExampleIfReassume, run_on_all_models=True),
    #"autofix": TechniqueConfig(AutoFixRanker, run_on_all_models=True),
    "llm_stub_all_lines_ranked": TechniqueConfig(LLMRanker, run_on_all_models=True),
    "llm_without_api": TechniqueConfig(LLMRanker, run_on_all_models=False),
    "llm_qwen_480b": TechniqueConfig(LLMRanker, run_on_all_models=True),
}


TECHNIQUE_MAP: dict[str, type[FLTechnique]] = {
    name: cfg.technique_class for name, cfg in TECHNIQUE_CONFIG.items()
}


def get_techniques_for_all_models() -> list[str]:
    """Return techniques explicitly enabled for run_all_models and guard pipelines."""
    return [name for name, cfg in TECHNIQUE_CONFIG.items() if cfg.run_on_all_models]


def setup_evaluation(flt_name: str, base_path: Path, to_validate_dataset : bool = True) -> tuple[FLTechnique, Path, Path] | None:
    """Validate technique/dataset and return technique, killed_dir and original_dir."""
    if flt_name not in TECHNIQUE_MAP:
        logger.error(f"Fault Localization Technique '{flt_name}' not recognized.")
        logger.error(f"Available techniques: {list(TECHNIQUE_MAP.keys())}")
        return None

    fl_technique = TECHNIQUE_MAP[flt_name](name=flt_name)

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
    mutation_name = diff_path.stem
    mutant_dfy_path = killed_dir / f"{mutation_name}.dfy"

    if not mutant_dfy_path.is_file():
        logger.warning(f"Corresponding mutant file not found for {diff_path}. Skipping.")
        return None

    try:
        base_name_raw = "__".join(mutation_name.split("__")[:-1])
        original_file = original_dir / f"{base_name_raw}.dfy"

        if not original_file.is_file():
            logger.error(f"Original file '{original_file.name}' not found. Skipping {mutation_name}.")
            return None

        gtruth_finder = GroundTruthAndLineLimit(
            originalfile=original_file,
            mutantfile=mutant_dfy_path,
            difffile=diff_path,
        )
        return compute_exam_score(fl_technique, gtruth_finder, dataset_dir)

    except ValueError as e:
        logger.error(f"Error processing {mutation_name} (Value Error): {e}. Skipping.")
    except IOError as e:
        logger.error(f"File error processing {mutation_name}: {e}. Skipping.")
    except Exception as e:
        logger.error(f"An unexpected error occurred for {mutation_name}: {e}. Skipping.")

    return None


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
