
import argparse
from pathlib import Path
from typing import Type
import shutil

import config as gl
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


from fl_eval.core.gt_parser import GroundTruthAndLineLimit
from fl_eval.metrics.scoring import compute_exam_score
from fl_eval.metrics.scoring import ExamOutput

from fl_eval.util.run_parallel_or_seq import run_parallel_or_seq

from typing import Type, Optional
# --- Mapping of Technique Names to Classes ---
TECHNIQUE_MAP: dict[str, type[FLTechnique]] = {
    "random": RandomRanker,
    "counterBase": CounterExampleBaseRanker,
    "empty": EmptyRanker,
    "randomOnFailingMethod" : RandomLineOfMethodThatFails,
    "counterExampleIf": CounterExampleIf,
    "counterExampleIfReassume" : CounterExampleIfReassume,
    "autofix": AutoFixRanker
}

def _setup_evaluation(flt_name: str, base_path: Path) -> tuple[FLTechnique, Path, Path] | None:
    """
    Handles validation, FL Technique instantiation, and directory setup.
    Returns the FLT instance and paths if successful, otherwise None.
    """
    # 1. Technique Validation
    if flt_name not in TECHNIQUE_MAP:
        print(f"Error: Fault Localization Technique '{flt_name}' not recognized.")
        print(f"Available techniques: {list(TECHNIQUE_MAP.keys())}")
        return None

    FLT_Class = TECHNIQUE_MAP[flt_name]
    fl_technique = FLT_Class(name=flt_name)
    
    # 2. Directory Validation
    killed_dir = base_path / "killed"
    original_dir = base_path / "original"
    
    if not killed_dir.is_dir() or not original_dir.is_dir():
        print(f"Error: Required 'killed' or 'original' directories not found in {base_path}")
        return None
        
    return fl_technique, killed_dir, original_dir

# --- Helper 2: Process a Single Mutation ---
def _process_mutation(
    diff_path: Path, 
    fl_technique: FLTechnique, 
    killed_dir: Path, 
    original_dir: Path
) -> Optional[ExamOutput]:
    """
    Processes a single mutation file pair, computes the EXAM score, and returns it.
    Returns None if any error occurs.
    """
    mutation_name = diff_path.stem 
    mutant_dfy_path = killed_dir / f"{mutation_name}.dfy"
    
    if not mutant_dfy_path.is_file():
        print(f"Warning: Corresponding mutant file not found for {diff_path}. Skipping.")
        return None

    try:
        # DYNAMIC ORIGINAL FILE IDENTIFICATION
        base_name_raw = "__".join(mutation_name.split('__')[:-1])
        original_file = original_dir / f"{base_name_raw}.dfy"
        
        if not original_file.is_file():
            print(f"Error: Original file '{original_file.name}' not found. Skipping {mutation_name}.")
            return None

        # Create Ground Truth object and compute score
        gtruth_finder = GroundTruthAndLineLimit(
            originalfile=original_file, 
            mutantfile=mutant_dfy_path, 
            difffile=diff_path
        )
        # Note: compute_exam_score handles calling the FL technique
        exam_output = compute_exam_score(fl_technique, gtruth_finder)
        return exam_output

    except ValueError as e:
        print(f"Error processing {mutation_name} (Value Error): {e}. Skipping.")
    except IOError as e:
        print(f"File error processing {mutation_name}: {e}. Skipping.")
    except Exception as e:
        print(f"An unexpected error occurred for {mutation_name}: {e}. Skipping.")
        
    return None

# --- Helper 3: Reporting ---

def _generate_report(flt_name: str, all_scores: list[ExamOutput]) -> None:
    """
    Computes the final average and prints the evaluation summary in a neat table.
    """
    if not all_scores:
        print("\nNo mutations were successfully evaluated.")
        return

    # Compute metrics
    total = len(all_scores)
    average_score = sum(x.score for x in all_scores) / total
    found_score = sum(x.found for x in all_scores) / total
    empty_score = sum(x.empty for x in all_scores) / total

    # Table formatting
    print("\n" + "="*60)
    print(f"{'EVALUATION SUMMARY':^60}")
    print("="*60)
    print(f"{'Filter Name':30}: {flt_name.upper():<27}")
    print(f"{'Total Mutations':30}: {total:<27}")
    print(f"{'Average EXAM Score':30}: {average_score:.6f}")
    print(f"{'Fault Found (%)':30}: {found_score:.6f}")
    print(f"{'Empty Predictions (%)':30}: {empty_score:.6f}")
    print("="*60 + "\n")

# --- Orchestrator Function ---
def compute_metrics(flt_name: str, base_path: Path, sequential: bool = False) -> None:
    """
    Receives a technique name and directory, iterates through mutation files, 
    computes EXAM scores, and reports the average.
    """
    setup_result = _setup_evaluation(flt_name, base_path)
    if setup_result is None:
        return
        
    fl_technique, killed_dir, original_dir = setup_result
    all_scores: list[ExamOutput | None] = []

    diff_paths = list(killed_dir.glob("*.txt"))

    all_scores = run_parallel_or_seq(diff_paths, _process_mutation, f"Get metrics for {flt_name}",
                                     fl_technique, killed_dir, original_dir, parallel=not sequential)
    all_scores_clean: list[ExamOutput] = [x for x in all_scores if x is not None]
    _generate_report(flt_name, all_scores_clean)



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
        print(f"Error: Data path not found: {args.data_path}")
        parser.print_help()
    else:
        cache_dir = gl.CACHE_DIR
        if args.clean_cache:
            print("Cleaning: Results Cache")
            if cache_dir.exists():
                try:
                    shutil.rmtree(cache_dir)
                    print(f"Removed cache directory: {cache_dir}")
                except OSError as e:
                    print(f"Could not remove cache directory {cache_dir}: {e}")
            else:
                print(f"No cache directory found at: {cache_dir}")
        else:
            print(f"Using cached Results if any at {cache_dir}")
        compute_metrics(args.technique_name, args.data_path, args.sequential)
