"""EXAM score computation and cache serialization for fault localization metrics.

This module provides functionality to:
1. Compute EXAM scores: percentage of code to inspect to find a fault (0=perfect, 1=worst)
2. Serialize/deserialize predictions and execution metadata to/from JSON cache
3. Support dataset-specific cache directories

Cache Schema (v2):
    {
        "schema_version": 2,
        "predictions": [line_no, ...],
        "execution_metadata": {
            "timestamp_utc": "2025-...",
            "command": [...],
            "status": "OK|TIMEOUT|...",
            "return_code": int or null,
            "stdout": str,
            "stderr": str
        }
    }

Key Implementation Notes:
- Cache writes use json.dump(..., default=str) for Path serialization tolerance
- Cache reads strictly validate schema v2 format (no backward compatibility)
- Metadata capture delegated to run_external_cmd module via get_last_execution_metadata()
- Thread-safe if single-threaded execution (global state in run_external_cmd)
- All cache paths are dataset-specific: run_artifacts/cached_results/<dataset_name>/<technique>/<mutant>.json
"""

from fl_eval.core.abstract import FLTechnique 
import config as gl
from pathlib import Path
import json
import traceback
from dataclasses import dataclass
import sys
from typing import Any, Protocol, cast
import fl_eval.util.run_external_cmd as run_cmd


class GroundTruthLike(Protocol):
    mutantfile: Path
    ground_truth: int
    startLine: int
    endLine: int

@dataclass
class ExamOutput:
    score : float # it is the exam score
    found : bool  # defines if the line of the oracle is inside any line predicted
    empty : bool  # Defines that the predicter did not predict anything
    filename : str  # the filename where the score refers to

def compute_exam_score_one_file(
    predictions: list[int], 
    ground_truth: int, 
    total_line_start: int, 
    total_line_end: int,
    filename: str
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
        filename (str): The filename associated with the score.

    Returns:
        ExamOutput: The computed exam score with metadata.

    Raises:
        ValueError: If the ground_truth is not within the specified line range.
    """
    total_lines = total_line_end - total_line_start + 1
    
    if total_lines <= 0:
        raise ValueError("Invalid line range: total_line_end must be >= total_line_start")

    if not (total_line_start <= ground_truth <= total_line_end):
        raise ValueError(f"Ground truth {ground_truth} is out of bounds ({total_line_start}-{total_line_end})")
    
    pred = list(filter(lambda x: (x < total_line_start) or (x > total_line_end), predictions))
       
    if  len(pred) != 0:
        raise ValueError(f"Some predictions are outside the bounds of the line start {total_line_start} line end {total_line_end} prediction {pred}")

    is_empty = predictions == []
    if(total_lines == 1): # If one line it is found and exam is always 0 as no effort is wasted
        return  ExamOutput(score = 0, found = predictions != [], empty = is_empty, filename=filename) 

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
    return ExamOutput( score = exam_score, found = found_in_predictions, empty = is_empty, filename=filename)

def _results_file_path(flt: FLTechnique, Gtruth: GroundTruthLike, dataset_dir: Path) -> Path:
    """Get the cache file path for a technique's predictions on a specific mutant.
    
    Args:
        flt: The fault localization technique
        Gtruth: Ground truth information for the mutant
        dataset_dir: Path to the dataset directory for dataset-specific caching
    
    Returns:
        Path to the cache file (run_artifacts/cached_results/<dataset_name>/<technique>/<mutant>.json)
    """
    cache_dir = gl.get_dataset_cache_dir(dataset_dir)
    return cache_dir / flt.name / f"{Gtruth.mutantfile.name}.json"


def save_to_file_output(
    flt: FLTechnique,
    Gtruth: GroundTruthLike,
    predictions: list[int],
    dataset_dir: Path,
    execution_metadata: dict[str, Any] | None = None,
) -> None:
    """Save predictions and execution metadata to cache file.
    
    Args:
        flt: The fault localization technique
        Gtruth: Ground truth information for the mutant
        predictions: List of predicted suspicious line numbers
        dataset_dir: Path to the dataset directory for dataset-specific caching
        execution_metadata: Optional metadata about execution (timestamps, return codes, etc.)
    """
    results_file = _results_file_path(flt, Gtruth, dataset_dir)
    results_file.parent.mkdir(parents=True, exist_ok=True)

    payload: dict[str, Any] = {
        "schema_version": 2,
        "predictions": predictions,
        "execution_metadata": execution_metadata,
    }

    with results_file.open("w", encoding="utf-8") as f:
            json.dump(payload, f, default=str)

def load_from_file_output(flt: FLTechnique, Gtruth: GroundTruthLike, dataset_dir: Path) -> list[int]:
    """Load predictions from cache file.
    
    Args:
        flt: The fault localization technique
        Gtruth: Ground truth information for the mutant
        dataset_dir: Path to the dataset directory for dataset-specific caching
    
    Returns:
        List of predicted suspicious line numbers
    
    Raises:
        FileNotFoundError: If cache file does not exist
        ValueError: If cache file format is invalid
        json.JSONDecodeError: If cache file is not valid JSON
    """
    results_file = _results_file_path(flt, Gtruth, dataset_dir)
    if not results_file.exists():
        raise FileNotFoundError(f"Cached results not found: {results_file}")
    with results_file.open("r", encoding="utf-8") as f:
        data: Any = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Invalid cache format in {results_file}. Expected dict, got {type(data).__name__}")

    payload = cast(dict[str, Any], data)
    predictions = payload.get("predictions")
    if not isinstance(predictions, list):
        raise ValueError(f"Invalid predictions payload in {results_file}")
    raw_predictions = cast(list[Any], predictions)
    if not all(isinstance(item, int) for item in raw_predictions):
        raise ValueError(f"Predictions must be a list of integers in {results_file}")

    return [int(item) for item in raw_predictions]


def compute_exam_score(flt : FLTechnique, Gtruth : GroundTruthLike, dataset_dir: Path) -> ExamOutput:
    """Compute EXAM score for a mutation, using cached results if available.
    
    Args:
        flt: The fault localization technique
        Gtruth: Ground truth information for the mutant
        dataset_dir: Path to the dataset directory for dataset-specific caching
    
    Returns:
        ExamOutput with the computed score
    """
    try:
        # Try loading from cached results
        predictions = load_from_file_output(flt, Gtruth, dataset_dir)
    except (FileNotFoundError, PermissionError, OSError, json.JSONDecodeError, ValueError):
        # Compute predictions localization
        execution_metadata: dict[str, Any] | None = None
        try:
            predictions = flt.get_fault_localization(Gtruth.mutantfile) 
            execution_metadata = run_cmd.get_last_execution_metadata()
        except Exception as e:
            predictions = []
            print("Exception occurred while running fault localization:", file=sys.stderr)
            print(str(e), file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            predictions = []
            execution_metadata = run_cmd.get_last_execution_metadata()
        save_to_file_output(flt, Gtruth, predictions, dataset_dir, execution_metadata)
    
    ground_truth = Gtruth.ground_truth
    total_line_start = Gtruth.startLine
    total_line_end = Gtruth.endLine
    
    return compute_exam_score_one_file(
        predictions, 
        ground_truth, 
        total_line_start, 
        total_line_end,
        str(Gtruth.mutantfile)
    )