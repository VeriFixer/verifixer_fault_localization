def compute_exam_score_one_file(
    predictions: list[int], 
    ground_truth: int, 
    total_line_start: int, 
    total_line_end: int
) -> tuple[bool, float]:
    """
    Evaluates the effectiveness of a fault localization technique by calculating the EXAM score.

    The EXAM score represents the percentage of executable statements that must be 
    inspected to find the fault. This function ensures the ranking is complete by 
    appending any unranked lines to the end of the provided prediction list.

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

    prediction_set = set(predictions)
    missing_lines: list[int] = []
    
    for i in range(total_line_start, total_line_end + 1):
        if i not in prediction_set:
            missing_lines.append(i)
            
    full_ranking = predictions + missing_lines

    try:
        rank_index = full_ranking.index(ground_truth)
    except ValueError:
        raise ValueError("Ground truth not found in the constructed line list.")

    found_in_predictions = rank_index < len(predictions)
    exam_score = rank_index / total_lines
    return (found_in_predictions, exam_score)


