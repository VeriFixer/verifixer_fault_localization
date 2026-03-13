from fl_eval.core.abstract import FLTechnique 
from fl_eval.core.gt_parser import GroundTruthAndLineLimit
from pathlib import Path
import json
import traceback
from dataclasses import dataclass
import sys

@dataclass
class ExamOutput:
    score : float # it is the exam score
    found : bool  # defines if the line of the oracle is inside any line predicted
    empty : bool  # Defines that the predicter did not predict anything

def compute_exam_score_one_file(
    predictions: list[int], 
    ground_truth: int, 
    total_line_start: int, 
    total_line_end: int
) -> ExamOutput:
    """
    Evaluates the effectiveness of a fault localization technique by calculating the EXAM score.

    The EXAM score represents the percentage of executable statements that must be 
    inspected to find the fault. The Exam Score works best by ranking all lines, prior work appended
    missing lines unranked lines to the prediciton list to make it complete.

    However this is statistical unstable, what we will do instead is use the acually ranked lines by the predictor
    And if the line is not there, use the remaining N-len(predictions) to compute the expected number of lines.
    If the ground_truth is not in the predictions, the function calculates the Expected Value 
    of the rank assuming the fault is uniformly distributed among the unranked lines.

    Exam score must be 0 if perfect predicted and 1 if line is the last to be found. it measures the total number of wasted 
    Cecks, at maximum I will waste N-1 lines (as the last one is correct) Therefore the score is computed as 
    Rank[0 index] / (N-1) , and for N=1 returns 0 imediatly

    Args:
        predictions (list[int]): A list of line numbers ranked by suspiciousness (descending).
        ground_truth (int): The actual line number where the fault is located.
        total_line_start (int): The starting line number of the valid code range.
        total_line_end (int): The ending line number of the valid code range.

    Returns:
        tuple[bool, float]: A tuple containing:
            - found_in_predictions (bool): True if the fault was in the original provided list.
            - exam_score (float): The EXAM score (rank / total_lines).

    Raises:
        ValueError: If the ground_truth is not within the specified line range.
    """
    total_lines = total_line_end - total_line_start + 1
    
    if total_lines <= 0:
        raise ValueError("Invalid line range: total_line_end must be >= total_line_start")

    if not (total_line_start <= ground_truth <= total_line_end):
        raise ValueError(f"Ground truth {ground_truth} is out of bounds ({total_line_start}-{total_line_end})")
    
    if  len(list(filter(lambda x: (x < total_line_start) or (x > total_line_end), predictions))) != 0:
        raise ValueError(f"Some predictions are outside the bounds of the line start {total_line_start} line end {total_line_end}")

    is_empty = predictions == []
    if(total_lines == 1): # If one line it is found and exam is always 0 as no effort is wasted
        return  ExamOutput(score = 0, found = predictions != [], empty = is_empty) 

    try:
        rank = predictions.index(ground_truth)
        found_in_predictions = True
        
    except ValueError:
        found_in_predictions = False
        lines_inspected_so_far = len(predictions)
        remaining_unranked_lines = total_lines - lines_inspected_so_far
        
        if remaining_unranked_lines <= 0:
             raise ValueError("Predictions cover all lines but ground truth is missing.")
        # We assume the fault is one of the remaining unranked lines.
        # The expected position of the fault in the unranked set is the average position.
        expected_position_in_unranked = (remaining_unranked_lines-1) / 2
        rank = lines_inspected_so_far + expected_position_in_unranked

    exam_score = rank / (total_lines-1)
    return ExamOutput( score = exam_score, found = found_in_predictions, empty = is_empty)

def _results_file_path(flt: FLTechnique, Gtruth: GroundTruthAndLineLimit) -> Path:
    top_folder = Gtruth.mutantfile.parent.parent.parent
    return  top_folder / "cached_results" / flt.name / f"{Gtruth.mutantfile.name}.json"


def save_to_file_output( flt: FLTechnique, Gtruth: GroundTruthAndLineLimit,  predictions: list[int]):
    # Top-level folder (e.g., project root)
    results_file = _results_file_path(flt, Gtruth)
    results_file.parent.mkdir(parents=True, exist_ok=True)

    with results_file.open("w", encoding="utf-8") as f:
         json.dump(predictions, f)


def load_from_file_output(flt: FLTechnique, Gtruth: GroundTruthAndLineLimit) -> list[int]:
    results_file = _results_file_path(flt, Gtruth)
    if not results_file.exists():
        raise FileNotFoundError(f"Cached results not found: {results_file}")
    with results_file.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def compute_exam_score(flt : FLTechnique, Gtruth : GroundTruthAndLineLimit) -> ExamOutput:
    try : 
        # Try loading from cached results
        predictions = load_from_file_output(flt, Gtruth)
    except FileNotFoundError:
        # Compute predictions localization
        try:
            predictions = flt.get_fault_localization(Gtruth.mutantfile) 
        except Exception as e:
            predictions = []
            print("Exception occurred while running fault localization:", file=sys.stderr)
            print(str(e), file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            predictions = []
        save_to_file_output( flt, Gtruth ,  predictions)
    
    ground_truth = Gtruth.ground_truth
    total_line_start = Gtruth.startLine
    total_line_end = Gtruth.endLine
    
    return compute_exam_score_one_file(
        predictions, 
        ground_truth, 
        total_line_start, 
        total_line_end
    )