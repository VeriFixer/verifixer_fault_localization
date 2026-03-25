"""Dataset structure and consistency validation for fault localization.

Provides comprehensive checks to validate dataset integrity before processing:
1. Directory structure validation (original/, killed/, .dfy, .txt files)
2. File consistency (diff files have corresponding mutants)
3. Mutant/original pairing validation
4. Diff file format checks
5. Detailed error diagnostics with actionable messages

This module is designed to detect and report issues early, but validation failures
are non-blocking. The pipeline will log issues as errors but continue processing,
allowing individual mutations to handle their own robustness. This design choice:
- Enables partial evaluation of datasets with minor structural issues
- Lets mutations fail gracefully rather than rejecting entire datasets
- Provides clear diagnostics for debugging data quality issues
- Maintains operational resilience for imperfect datasets

Validation is called once per technique (in _setup_evaluation) before any
mutations are processed, providing early diagnostics without blocking work.
"""

from pathlib import Path
from logging_config import get_logger
from dataclasses import dataclass

logger = get_logger(__name__)


@dataclass
class DatasetValidationResult:
    """Result of dataset validation with summary metrics."""
    is_valid: bool
    error_count: int
    warning_count: int
    messages: list[str]  # List of error/warning messages
    stats: dict[str, int]  # Stats: original_files, mutant_files, diff_files, etc.


def _check_directory_structure(dataset_path: Path) -> tuple[bool, list[str]]:
    """
    Validates that required directories exist and are readable.
    
    Returns:
        (is_valid, error_messages)
    """
    errors = []
    
    if not dataset_path.is_dir():
        errors.append(f"Dataset path is not a directory: {dataset_path}")
        return False, errors
    
    original_dir = dataset_path / "original"
    killed_dir = dataset_path / "killed"
    
    for name, dir_path in [("original", original_dir), ("killed", killed_dir)]:
        if not dir_path.is_dir():
            errors.append(f"Missing required '{name}' subdirectory at {dir_path}")
        elif not any(dir_path.glob("*.dfy")):
            errors.append(f"No .dfy files found in '{name}' directory: {dir_path}")
    
    if killed_dir.is_dir() and not any(killed_dir.glob("*.txt")):
        errors.append(f"No diff (.txt) files found in 'killed' directory: {killed_dir}")
    
    return len(errors) == 0, errors


def _check_file_pairing(dataset_path: Path) -> tuple[bool, list[str], dict[str, int]]:
    """
    Validates that each diff file has a corresponding mutant .dfy file.
    Also checks that diff files are readable and have expected format.
    
    Returns:
        (is_valid, error_messages, stats_dict)
    """
    errors = []
    stats = {
        "original_files": 0,
        "mutant_files": 0,
        "diff_files": 0,
        "orphan_diffs": 0,
        "missing_mutants": 0,
    }
    
    killed_dir = dataset_path / "killed"
    original_dir = dataset_path / "original"
    
    # Count files
    stats["original_files"] = len(list(original_dir.glob("*.dfy")))
    stats["mutant_files"] = len(list(killed_dir.glob("*.dfy")))
    stats["diff_files"] = len(list(killed_dir.glob("*.txt")))
    
    # Check each diff file
    for diff_file in sorted(killed_dir.glob("*.txt")):
        mutation_name = diff_file.stem
        mutant_dfy = killed_dir / f"{mutation_name}.dfy"
        
        if not mutant_dfy.is_file():
            stats["missing_mutants"] += 1
            errors.append(
                f"Diff file {diff_file.name} has no corresponding mutant: "
                f"expected {mutant_dfy.name}"
            )
        
        # Try to read diff file to check format
        try:
            diff_content = diff_file.read_text(encoding="utf-8").strip()
            if not diff_content:
                errors.append(f"Diff file is empty: {diff_file}")
            elif not any(op in diff_content for op in ['c', 'a', 'd']):
                errors.append(
                    f"Diff file has invalid format (no c/a/d operations): {diff_file}"
                )
        except (IOError, UnicodeDecodeError) as e:
            errors.append(f"Failed to read diff file {diff_file}: {e}")
    
    # Check for orphan .dfy files (mutants without diffs)
    for mutant_file in killed_dir.glob("*.dfy"):
        diff_file = killed_dir / f"{mutant_file.stem}.txt"
        if not diff_file.is_file():
            stats["orphan_diffs"] += 1
            logger.debug(f"Mutant without diff file: {mutant_file.name}")
    
    return len(errors) == 0, errors, stats


def _check_original_pairing(dataset_path: Path) -> tuple[bool, list[str]]:
    """
    Validates that mutant files can be paired with original files.
    Checks the naming convention: mutant names should derive from original names.
    
    Returns:
        (is_valid, error_messages)
    """
    errors = []
    killed_dir = dataset_path / "killed"
    original_dir = dataset_path / "original"
    
    original_files = {f.name for f in original_dir.glob("*.dfy")}
    
    for mutant_file in killed_dir.glob("*.dfy"):
        mutation_name = mutant_file.stem
        
        # Extract base name by removing mutation suffix (last __ segment)
        parts = mutation_name.split("__")
        if len(parts) < 2:
            errors.append(
                f"Mutant naming doesn't follow convention (expected base__suffix): {mutation_name}"
            )
            continue
        
        base_name = "__".join(parts[:-1])
        expected_original = f"{base_name}.dfy"
        
        if expected_original not in original_files:
            # This might be OK if the mutant is from a different base,
            # but log it as a warning if no original can be found
            found = False
            for orig in original_files:
                if orig.startswith(base_name):
                    found = True
                    break
            if not found:
                logger.debug(
                    f"Could not find original for mutant {mutation_name}. "
                    f"Expected {expected_original} or similar."
                )
    
    return len(errors) == 0, errors


def validate_dataset(dataset_path: Path) -> DatasetValidationResult:
    """
    Comprehensive dataset validation.
    
    Args:
        dataset_path: Path to dataset directory (contains 'original' and 'killed' subdirs)
    
    Returns:
        DatasetValidationResult with validation status, error count, and diagnostics
    """
    all_errors = []
    all_warnings = []
    all_stats = {}
    
    # Check 1: Directory structure
    valid_dirs, dir_errors = _check_directory_structure(dataset_path)
    if not valid_dirs:
        all_errors.extend(dir_errors)
        return DatasetValidationResult(
            is_valid=False,
            error_count=len(all_errors),
            warning_count=0,
            messages=all_errors,
            stats={},
        )
    
    # Check 2: File pairing (diffs ↔ mutants)
    valid_pairing, pairing_errors, stats = _check_file_pairing(dataset_path)
    all_errors.extend(pairing_errors)
    all_stats.update(stats)
    
    # Check 3: Original file pairing
    valid_originals, original_errors = _check_original_pairing(dataset_path)
    all_errors.extend(original_errors)
    
    # Determine overall validity
    is_valid = valid_dirs and valid_pairing and valid_originals
    
    # Add summary stats as info messages
    summary = (
        f"Dataset validation: {all_stats.get('original_files', 0)} originals, "
        f"{all_stats.get('mutant_files', 0)} mutants, "
        f"{all_stats.get('diff_files', 0)} diffs"
    )
    all_errors.insert(0, summary)
    
    return DatasetValidationResult(
        is_valid=is_valid,
        error_count=len(all_errors),
        warning_count=len(all_warnings),
        messages=all_errors + all_warnings,
        stats=all_stats,
    )


def log_validation_result(result: DatasetValidationResult, dataset_path: Path) -> None:
    """
    Log validation results with appropriate log levels.
    
    Args:
        result: DatasetValidationResult from validate_dataset()
        dataset_path: Path to dataset for context
    """
    for msg in result.messages:
        if "validation:" in msg.lower():
            logger.info(f"Dataset {dataset_path.name}: {msg}")
        elif result.is_valid or "could not find" in msg.lower():
            logger.debug(f"Dataset validation: {msg}")
        else:
            logger.error(f"Dataset validation: {msg}")
