import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from fl_eval.core.abstract import FLTechnique
from autofix_ranker import AutoFixRanker
from fl_eval.strategies.counter_example_base_ranker import CounterExampleBaseRanker
from fl_eval.strategies.counter_example_if import CounterExampleIf
from fl_eval.strategies.counter_example_if_reassume import CounterExampleIfReassume
from fl_eval.strategies.empty_ranker import EmptyRanker
from fl_eval.strategies.llm_err_msg import LLMErrMsgRanker
from fl_eval.strategies.llm_err_msg_cntm import LLMErrMsgCNTMRanker
from fl_eval.strategies.llm_ranker import LLMRanker
from fl_eval.strategies.random_line_of_method_that_fails import RandomLineOfMethodThatFails
from fl_eval.strategies.random_ranker import RandomRanker
from fl_eval.util.ranking_strategy import (
    CNTM_ABLATION_NO_CONTROL,
    CNTM_ABLATION_NO_DEPTH,
    CNTM_ABLATION_NO_FREQUENCY,
    CNTM_ABLATION_PURE_STATE,
    CounterExampleRankingControls,
)
from logging_config import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class TechniqueConfig:
    technique_class: type[FLTechnique]
    run_on_all_models: bool = False
    autofix_strategy: str = ""
    ranking_controls: CounterExampleRankingControls | None = None


TECHNIQUE_CONFIG: dict[str, TechniqueConfig] = {
    "RANDFILE": TechniqueConfig(RandomRanker, run_on_all_models=True),
    "CNTB": TechniqueConfig(CounterExampleBaseRanker, run_on_all_models=True),
    "EMPTY": TechniqueConfig(EmptyRanker, run_on_all_models=True),
    "RAND": TechniqueConfig(RandomLineOfMethodThatFails, run_on_all_models=True),
    "CNTS": TechniqueConfig(CounterExampleIf, run_on_all_models=True),
    "CNTM": TechniqueConfig(CounterExampleIfReassume, run_on_all_models=True),
    "CNTM_pure_state": TechniqueConfig(
        CounterExampleIfReassume,
        run_on_all_models=False,
        ranking_controls=CNTM_ABLATION_PURE_STATE,
    ),
    "CNTM_no_frequency": TechniqueConfig(
        CounterExampleIfReassume,
        run_on_all_models=False,
        ranking_controls=CNTM_ABLATION_NO_FREQUENCY,
    ),
    "CNTM_no_depth": TechniqueConfig(
        CounterExampleIfReassume,
        run_on_all_models=False,
        ranking_controls=CNTM_ABLATION_NO_DEPTH,
    ),
    "CNTM_no_control": TechniqueConfig(
        CounterExampleIfReassume,
        run_on_all_models=False,
        ranking_controls=CNTM_ABLATION_NO_CONTROL,
    ),
    "SNAP": TechniqueConfig(AutoFixRanker, autofix_strategy="dynamic-and-static-score", run_on_all_models=False),
    "SNAP_SIMPLIFIED": TechniqueConfig(AutoFixRanker, autofix_strategy="dynamic-score-only", run_on_all_models=False),
    "LLM_NO_API": TechniqueConfig(LLMRanker, run_on_all_models=False),
    "LLM": TechniqueConfig(LLMRanker, run_on_all_models=True),
    "LLM_ERR_MSG": TechniqueConfig(LLMErrMsgRanker, run_on_all_models=False),
    "LLM_ERR_MSG_CNTM": TechniqueConfig(LLMErrMsgCNTMRanker, run_on_all_models=False),
}


TECHNIQUE_MAP: dict[str, tuple[type[FLTechnique], str]] = {
    name: (cfg.technique_class, cfg.autofix_strategy) for name, cfg in TECHNIQUE_CONFIG.items()
}


def setup(flt_name: str) -> FLTechnique | None:
    """Validate technique."""
    if flt_name not in TECHNIQUE_MAP:
        logger.error(f"Fault Localization Technique '{flt_name}' not recognized.")
        logger.error(f"Available techniques: {list(TECHNIQUE_MAP.keys())}")
        return None

    tech_config = TECHNIQUE_CONFIG[flt_name]
    FLT_Class = tech_config.technique_class
    autofix_strategy = tech_config.autofix_strategy
    if FLT_Class == AutoFixRanker:
        fl_technique = FLT_Class(name=flt_name, autofix_strategy=autofix_strategy)
    elif tech_config.ranking_controls is not None:
        fl_technique = FLT_Class(name=flt_name, ranking_controls=tech_config.ranking_controls)
    else:
        fl_technique = FLT_Class(name=flt_name)

    return fl_technique


def process_faulty_program(
    fl_technique: FLTechnique,
    dfy_path: Path,
) -> Optional[list[int]]: # TODO
    """Process one faulty program and return ranking, or None if it fails."""

    try:
        return compute_ranking(fl_technique, dfy_path)
    except IOError as e:
        logger.error(f"File error processing {dfy_path.stem}: {e}. Skipping.")
    except Exception as e:
        logger.error(f"An unexpected error occurred for {dfy_path.stem}: {e}. Skipping.")

    return None


def compute_ranking(flt : FLTechnique, dfy_path: Path) -> list[int]:
    """Compute suspiciousness location ranking for a faulty program."""
    # Load from cache when available; compute only if missing or unreadable.
    predictions: list[int] = []

    try:
        predictions = flt.get_fault_localization(dfy_path) 
    except Exception as e:
        predictions = []
        print("Exception occurred while running fault localization:", file=sys.stderr)
        print(str(e), file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
    
    return predictions


def execute_single_mutation(
    flt_name: str,
    dfy_path: Path,
) -> tuple[FLTechnique, list[int]] | None:
    """Run one technique for one mutant file and return execution output."""
    fl_technique = setup(flt_name)
    if fl_technique is None:
        return None

    ranking = process_faulty_program(fl_technique, dfy_path)
    if ranking is None:
        return None

    return fl_technique, ranking
