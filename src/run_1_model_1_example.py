
import argparse
from pathlib import Path
import shutil

import config as gl
from logging_config import get_logger
from fl_eval.strategies.llm_ranker import LLMRanker
from fl_eval.metrics.scoring import ExamOutput
from fl_eval.util.run_model_common import (
    TECHNIQUE_MAP,
    generate_report,
    process_mutation,
    setup_evaluation,
)

logger = get_logger(__name__)

# --- Orchestrator Function ---
def compute_metrics_1_file(
    flt_name: str,
    dfy_path: Path,
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
    base_path = dfy_path.parent.parent
    setup_result = setup_evaluation(flt_name, base_path, to_validate_dataset=False)
    if setup_result is None:
        return
        
    fl_technique, killed_dir, original_dir = setup_result

    diff_path = killed_dir / Path(dfy_path.name[:-4] + ".txt")

    score = [process_mutation(
        diff_path,
        fl_technique, 
        killed_dir,
        original_dir,
        base_path
    )] 

    scores_clean: list[ExamOutput] = [x for x in score if x is not None]
    generate_report(flt_name, scores_clean)

    score = scores_clean[0]

    logger.info(f"Ground Trhuth: {score.method.line_ground_truth} \n Prediciton: {score.method.line_prediction}")

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
        "dfy_path", 
        type=Path,
        help="The path to the file containing the dfy code (it will extract paths to killed, original folder from there)."
    )

    args = parser.parse_args()
    

    # Check if the path exists before proceeding
    if not args.dfy_path.exists():
        logger.error(f"Data path not found: {args.dfy_path}")
        parser.print_help()
    else:
        # Need cache cleaning per default
        cache = gl.get_file_cache_path(args.dfy_path, args.technique_name)
        if cache.exists():
            try:
                if cache.is_dir():
                    shutil.rmtree(cache)
                else:
                    cache.unlink()
                logger.info(f"Removed cache entry: {cache}")
            except OSError as e:
                logger.error(f"Could not remove cache entry {cache}: {e}")
        compute_metrics_1_file(args.technique_name, args.dfy_path)
