
import argparse
from pathlib import Path
from typing import Dict, Type, List, Tuple

# --- Import Core Components from fl_eval package ---
from fl_eval.core.abstract import FLTechnique
from fl_eval.core.baselines import RandomRanker, CounterExampleBaseRanker, EmptyRanker

from fl_eval.core.gt_parser import GroundTruthAndLineLimit
from fl_eval.metrics.scoring import compute_exam_score

from fl_eval.util.run_parallel_or_seq import run_parallel_or_seq
from fl_eval.util.globals import *

from typing import Dict, Type, List, Tuple, Optional
# --- Mapping of Technique Names to Classes ---
TECHNIQUE_MAP: Dict[str, Type[FLTechnique]] = {
    "random": RandomRanker,
    "counterBase": CounterExampleBaseRanker,
    "empty": EmptyRanker
    # TODO: Add other FL techniques here as they are implemented
}

def _setup_evaluation(flt_name: str, base_path: Path) -> Optional[Tuple[FLTechnique, Path, Path]]:
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
) -> Optional[tuple[bool,float]]:
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
        base_name_raw = mutation_name.split('__')[0]
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
        (found, exam_score) = compute_exam_score(fl_technique, gtruth_finder)
        
        return (found, exam_score)

    except ValueError as e:
        print(f"Error processing {mutation_name} (Value Error): {e}. Skipping.")
    except IOError as e:
        print(f"File error processing {mutation_name}: {e}. Skipping.")
    except Exception as e:
        print(f"An unexpected error occurred for {mutation_name}: {e}. Skipping.")
        
    return None

# --- Helper 3: Reporting ---

def _generate_report(flt_name: str, all_scores: List[tuple[bool,float]]) -> None:
    """
    Computes the final average and prints the evaluation summary.
    """
    if all_scores:
        found_score = sum([x[0] for x in all_scores])/len(all_scores)
        average_score = sum([x[1] for x in all_scores])/ len(all_scores)
        print("\n" + "="*50)
        print(f"| Evaluation Summary for: {flt_name.upper():<27}")
        print(f"| Total Mutations Evaluated: {len(all_scores):<27}")
        print(f"| Average EXAM Score: {average_score:.6f}{'':<20}")
        print(f"| % where Fault was in the predictions: {found_score:.6f}{'':<20}")
        print("="*50)
    else:
        print("\nNo mutations were successfully evaluated.")

# --- Orchestrator Function ---
def compute_metrics(flt_name: str, base_path: Path) -> None:
    """
    Receives a technique name and directory, iterates through mutation files, 
    computes EXAM scores, and reports the average.
    """
    setup_result = _setup_evaluation(flt_name, base_path)
    if setup_result is None:
        return
        
    fl_technique, killed_dir, original_dir = setup_result
    all_scores: list[tuple[bool,float] | None] = []

    diff_paths = list(killed_dir.glob("*.txt"))

    all_scores = run_parallel_or_seq(RUN_PARALLEL, f"Get metrics for {flt_name}",
                                     diff_paths, _process_mutation, 
                                     fl_technique, killed_dir, original_dir)
    all_scores_clean : list[tuple[bool,float]] = list(filter(lambda x: x is not None, all_scores))
    _generate_report(flt_name, all_scores_clean)



if __name__ == "__main__":
    # Define a clear usage example for the epilog
    USAGE_EXAMPLE = """"
How to use:
  Run the script from the project root directory.

  Example 1: Evaluate the 'random' technique using data in 'src/pos_test'
    $ python src/main.py random src/pos_test

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
        help="The path to the parent directory containing the 'killed' and 'original' folders (e.g., src/pos_test)."
    )
    
    args = parser.parse_args()
    
    # Check if the path exists before proceeding
    if not args.data_path.exists():
        print(f"Error: Data path not found: {args.data_path}")
        parser.print_help()
    else:
        compute_metrics(args.technique_name, args.data_path)
