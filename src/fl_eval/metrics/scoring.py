from fl_eval.core.abstract import FLTechnique 
from fl_eval.core.gt_parser import GroundTruthAndLineLimit

def compute_exam_score_one_file(
    predictions: list[int], 
    ground_truth: int, 
    total_line_start: int, 
    total_line_end: int
) -> tuple[bool, float]:
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

    if(total_lines == 1): # If one line it is found and exam is always 0 as no effort is wasted
        return(predictions != [], 0)

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
    return (found_in_predictions, exam_score)



def compute_exam_score(flt : FLTechnique, Gtruth : GroundTruthAndLineLimit) -> tuple[bool, float]:
    predictions = flt.get_fault_localization(Gtruth.mutantfile) 
    
    ground_truth = Gtruth.ground_truth
    total_line_start = Gtruth.startLine
    total_line_end = Gtruth.endLine
    
    return compute_exam_score_one_file(
        predictions, 
        ground_truth, 
        total_line_start, 
        total_line_end
    )