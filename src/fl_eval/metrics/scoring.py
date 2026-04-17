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
- All cache paths are dataset-specific: tmp/run_artifacts/cached_results/<dataset_name>/<technique>/<mutant>.json
"""

from fl_eval.core.abstract import FLTechnique 
import config as gl
from pathlib import Path
import json
import traceback
from dataclasses import dataclass, field
import sys
from typing import Any, Protocol, cast
import fl_eval.execution.external_cmd as run_cmd
from logging_config import get_logger


logger = get_logger(__name__)


class GroundTruthLike(Protocol):
    mutantfile: Path
    ground_truth: int
    startLine: int
    endLine: int
    method_name: str
    method_start: int
    method_end: int

@dataclass
class ExamScore:
    score: float
    found: bool
    prediction: bool

    line_ground_truth: int = -1
    line_prediction: list[int] = field(default_factory=lambda: cast(list[int], []))

    @property
    def empty(self) -> bool:
        return not self.prediction


@dataclass
class ExamScoreOutput:
    filename: str
    method_name: str

    file: ExamScore
    method: ExamScore

    # Compatibility aliases for existing call sites
    @property
    def score_file(self) -> float:
        return self.file.score

    @property
    def found_file(self) -> bool:
        return self.file.found

    @property
    def empty_file(self) -> bool:
        return self.file.empty

    @property
    def score_method(self) -> float:
        return self.method.score

    @property
    def found_method(self) -> bool:
        return self.method.found

    @property
    def empty_method(self) -> bool:
        return self.method.empty

    # Legacy aliases where "score/found/empty" means file scope
    @property
    def score(self) -> float:
        return self.file.score

    @property
    def found(self) -> bool:
        return self.file.found

    @property
    def empty(self) -> bool:
        return self.file.empty


# Backward-compatible type alias
ExamOutput = ExamScoreOutput


def _compute_exam_score_in_scope(
    predictions: list[int],
    ground_truth: int,
    scope_start: int,
    scope_end: int,
    suppress_warnings: bool = False,
) -> ExamScore:
    """Compute EXAM score for an arbitrary [scope_start, scope_end] range.
    
    Args:
        suppress_warnings: If True, suppress logging of filtered out-of-scope predictions.
                          Used for weak/baseline techniques (e.g., Random, Empty) that cannot
                          reliably predict in-scope lines.
    """
    total_lines = scope_end - scope_start + 1

    if total_lines <= 0:
        raise ValueError("Invalid line range: scope_end must be >= scope_start")

    if not (scope_start <= ground_truth <= scope_end):
        raise ValueError(f"Ground truth {ground_truth} is out of bounds ({scope_start}-{scope_end})")

    # Keep only absolute predictions within the active scope.
    normalized_predictions: list[int] = []
    seen: set[int] = set()
    out_of_scope_count = 0
    for p in predictions:
        if p not in seen:
            seen.add(p)
            normalized_predictions.append(p)
            
            if not(scope_start <= p <= scope_end):
                out_of_scope_count += 1

    if out_of_scope_count > 0 and not suppress_warnings:
        logger.warning(
            "Ignored %d out-of-scope predictions outside [%d, %d].",
            out_of_scope_count,
            scope_start,
            scope_end,
        )

    in_scope_predictions = normalized_predictions
    has_prediction = len(in_scope_predictions) > 0

    if total_lines == 1:
        return ExamScore(score=0.0, 
                         found=ground_truth in in_scope_predictions, 
                         prediction=has_prediction, 
                         line_ground_truth=ground_truth, 
                         line_prediction=in_scope_predictions)

    rank = -1 
    found_in_predictions = False
    for pred in in_scope_predictions:
        rank += 1
        if(pred == ground_truth):
            found_in_predictions = True
            break 

    if(not found_in_predictions):
        lines_inspected_so_far = len(in_scope_predictions)
        remaining_unranked_lines = total_lines - lines_inspected_so_far
        if(remaining_unranked_lines <= 0 ):
            rank = total_lines - 1  # Already inspected more lines that the maximum needed so returning 1
        else:
            # Comput expected rank
            expected_position_in_unranked = (remaining_unranked_lines - 1) / 2
            rank = lines_inspected_so_far + expected_position_in_unranked
    else:
        # if found but basically saw more lines that the method has
        # consider simply worse case
        if(rank >= (total_lines -1)):
            rank = total_lines -1
    exam_score = rank / (total_lines - 1)
    return ExamScore(score=exam_score, 
                     found=found_in_predictions, 
                     prediction=has_prediction, 
                     line_ground_truth=ground_truth, 
                     line_prediction=in_scope_predictions)

def compute_exam_score_one_file(
    predictions: list[int], 
    ground_truth: int, 
    total_line_start: int, 
    total_line_end: int,
    filename: str,
    suppress_warnings: bool = False,
) -> ExamScore:
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
        suppress_warnings (bool): If True, suppress out-of-scope prediction warnings.

    Returns:
        ExamScore for file scope.

    Raises:
        ValueError: If the ground_truth is not within the specified line range.
    """
    _ = filename  # kept for API compatibility with existing callers
    return _compute_exam_score_in_scope(
        predictions=predictions,
        ground_truth=ground_truth,
        scope_start=total_line_start,
        scope_end=total_line_end,
        suppress_warnings=suppress_warnings,
    )


def compute_exam_score_method_scope(
    predictions: list[int],
    ground_truth: int,
    method_start: int,
    method_end: int,
    filename: str,
    suppress_warnings: bool = False,
) -> ExamScore:
    """
    Compute EXAM score within a method scope (not file-wide).
    
    Similar to compute_exam_score_one_file but restricts evaluation to method boundaries.
    
    Args:
        predictions (list[int]): A list of line numbers ranked by suspiciousness (descending).
        ground_truth (int): The actual line number where the fault is located.
        method_start (int): The starting line number of the method scope.
        method_end (int): The ending line number of the method scope.
        filename (str): The filename associated with the score.
        suppress_warnings (bool): If True, suppress out-of-scope prediction warnings.

    Returns:
        ExamScore for method scope.
        
    Raises:
        ValueError: If the ground_truth is not within the method scope
    """
    _ = filename  # kept for API compatibility with existing callers
    return _compute_exam_score_in_scope(
        predictions=predictions,
        ground_truth=ground_truth,
        scope_start=method_start,
        scope_end=method_end,
        suppress_warnings=suppress_warnings,
    )


def _results_file_path(flt: FLTechnique, Gtruth: GroundTruthLike, dataset_dir: Path) -> Path:
    """Get the cache file path for a technique's predictions on a specific mutant.

    Args:
        flt: The fault localization technique
        Gtruth: Ground truth information for the mutant
        dataset_dir: Path to the dataset directory for dataset-specific caching

    Returns:
        Path to the cache file (tmp/run_artifacts/cached_results/<dataset_name>/<technique>/<mutant>.json)
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


def load_execution_metadata_from_cache(
    flt: FLTechnique,
    Gtruth: GroundTruthLike,
    dataset_dir: Path,
) -> dict[str, Any] | None:
    """Load execution metadata from cache payload for display/debugging.

    Returns None when cache is missing or metadata is unavailable/unreadable.
    """
    results_file = _results_file_path(flt, Gtruth, dataset_dir)
    if not results_file.exists():
        return None

    try:
        with results_file.open("r", encoding="utf-8") as f:
            data: Any = json.load(f)
    except (PermissionError, OSError, json.JSONDecodeError) as e:
        logger.warning("Failed to read execution metadata from %s: %s", results_file, e)
        return None

    if not isinstance(data, dict):
        return None

    payload = cast(dict[str, Any], data)
    metadata = payload.get("execution_metadata")
    if not isinstance(metadata, dict):
        return None

    return cast(dict[str, Any], metadata)


def compute_exam_score(flt : FLTechnique, Gtruth : GroundTruthLike, dataset_dir: Path) -> ExamScoreOutput:
    """Compute EXAM score for a mutation in both file-wide and method scopes.
    
    Uses cached results if available. Requires method information (method_name, method_start, method_end)
    to be present in Gtruth. Computes dual-scope metrics:
    - File-wide: entire file from startLine to endLine
    - Method-scoped: only within the method containing the fault
    
    Args:
        flt: The fault localization technique
        Gtruth: Ground truth information for the mutant (must include method fields)
        dataset_dir: Path to the dataset directory for dataset-specific caching
    
    Returns:
        ExamScoreOutput with computed scores for both file and method scopes
        
    Raises:
        AttributeError: If Gtruth lacks required method fields (method_start, method_end, method_name)
    """
    # Load from cache when available; compute only if missing or unreadable.
    results_file = _results_file_path(flt, Gtruth, dataset_dir)
    loaded_from_cache = False
    predictions: list[int] = []

    if results_file.exists():
        try:
            predictions = load_from_file_output(flt, Gtruth, dataset_dir)
            loaded_from_cache = True
        except (PermissionError, OSError, json.JSONDecodeError, ValueError) as e:
            logger.warning(
                "Cache read failed for %s (%s). Recomputing predictions.",
                results_file,
                e,
            )

    if not loaded_from_cache:
        execution_metadata: dict[str, Any] | None = None
        try:
            predictions = flt.get_fault_localization(Gtruth.mutantfile) 
            execution_metadata = run_cmd.get_last_execution_metadata()
        except Exception as e:
            predictions = []
            print("Exception occurred while running fault localization:", file=sys.stderr)
            print(str(e), file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            execution_metadata = run_cmd.get_last_execution_metadata()

        get_cost_snapshot = getattr(flt, "get_cost_snapshot", None)
        if callable(get_cost_snapshot):
            try:
                llm_cost_snapshot = get_cost_snapshot()
                if isinstance(llm_cost_snapshot, dict):
                    if execution_metadata is None:
                        execution_metadata = {}
                    execution_metadata["llm_cost"] = llm_cost_snapshot
            except Exception as e:
                logger.warning("Could not capture LLM cost snapshot for %s: %s", flt.name, e)

        save_to_file_output(flt, Gtruth, predictions, dataset_dir, execution_metadata)
    
    # Compute file-wide EXAM score
    ground_truth = Gtruth.ground_truth
    total_line_start = Gtruth.startLine
    total_line_end = Gtruth.endLine
    
    exam_file = compute_exam_score_one_file(
        predictions, 
        ground_truth, 
        total_line_start, 
        total_line_end,
        str(Gtruth.mutantfile),
        suppress_warnings=flt.suppress_scope_warnings,
    )
    
    # Compute method-scoped EXAM score using mandatory method metadata.
    method_name = Gtruth.method_name
    method_score = exam_file

    if Gtruth.method_start <= ground_truth <= Gtruth.method_end:
        method_score = compute_exam_score_method_scope(
            predictions,
            ground_truth,
            Gtruth.method_start,
            Gtruth.method_end,
            str(Gtruth.mutantfile),
            suppress_warnings=flt.suppress_scope_warnings,
        )
    
    return ExamScoreOutput(
        filename=str(Gtruth.mutantfile),
        method_name=method_name,
        file=exam_file,
        method=method_score,
    )
