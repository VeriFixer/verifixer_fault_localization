"""Method span extraction for Dafny files using ReturnAtRandomAllLinesOfFailingMethod binary.

This module provides functionality to extract method boundaries from Dafny files,
enabling method-scoped fault localization metrics.

Key Features:
1. Extract method spans (start_line, end_line) by running the ReturnAtRandomAllLinesOfFailingMethod binary
2. Find the method containing a specific fault line
3. Cache method definitions per file to amortize CLI cost
4. Handle edge cases (no methods, fault outside all methods)

Usage:
    from fl_eval.core.method_extractor import extract_method_containing_line
    
    result = extract_method_containing_line(
        mutant_file=Path("example.dfy"),
        fault_line=42
    )
    if result:
        method_name, start_line, end_line = result
    else:
        # Fault line not in any method (e.g., top-level declarations)
        pass
"""

from pathlib import Path
from typing import Optional
from logging_config import get_logger
import config as gl
import re
import fl_eval.util.run_external_cmd as run_cmd

logger = get_logger(__name__)

# Module-level cache: filename -> list of (method_name, start_line, end_line)
_METHOD_CACHE: dict[str, list[tuple[str, int, int]]] = {}


def _find_executable(base_dir: Path, pattern: str) -> Path:
    """Find the ReturnAtRandomAllLinesOfFailingMethod executable."""
    for path in base_dir.rglob(pattern):
        if path.is_file() and "ref" not in path.parts:
            return path
    raise FileNotFoundError(f"Could not find {pattern} executable in {base_dir}")


def extract_method_containing_line(
    file_path: Path,
    fault_line: int
) -> Optional[tuple[str, int, int]]:
    """
    Find the method containing a specific line using ReturnAtRandomAllLinesOfFailingMethod binary.
    
    Args:
        file_path: Path to the .dfy file
        fault_line: Line number to search for (1-indexed)
        
    Returns:
        Tuple of (method_name, start_line, end_line) if fault_line is within a method,
        None otherwise
        
    Raises:
        ValueError: If fault_line is invalid
        FileNotFoundError: If binary cannot be found
    """
    if fault_line < 1:
        raise ValueError(f"Invalid line number: {fault_line}")
    
    file_key = str(file_path.resolve())
    
    # Check cache first
    if file_key in _METHOD_CACHE:
        logger.debug(f"Using cached method span for {file_path.name}")
        spans = _METHOD_CACHE[file_key]
        # Find method containing fault_line
        for method_name, start_line, end_line in spans:
            if start_line <= fault_line <= end_line:
                logger.debug(
                    f"Fault at line {fault_line} is in method '{method_name}' "
                    f"(lines {start_line}-{end_line})"
                )
                return (method_name, start_line, end_line)
        
        logger.debug(f"Fault at line {fault_line} is not within any cached method span")
        return None
    
    # Not in cache, run binary
    logger.debug(f"Extracting method span from {file_path.name} via ReturnAtRandomAllLinesOfFailingMethod")
    
    try:
        # Find the binary (same approach as random_line_of_method_that_fails.py)
        base_dir = gl.BASE_PATH / "build_output/ReturnAtRandomAllLinesOfFailingMethod"
        pattern = "**/ReturnAtRandomAllLinesOfFailingMethod"
        exec_path = _find_executable(base_dir, pattern)
        
        # Run binary with time/memory limits
        command = [
            str(exec_path),
            str(file_path),
            "--max-time", str(gl.MAX_TIME_EXTERNAL_PROGRAMS),
            "--max-ram", str(gl.MAX_RAM_EXTERNAL_PROGRAMS)
        ]
        
        status, stdout, stderr = run_cmd.run_external_cmd(command)
        
        if status != run_cmd.Status.OK:
            logger.warning(
                f"Method extraction binary failed with status {status} on {file_path.name}. "
                f"Falling back to no method scope."
            )
            return None
        
        # Parse output to extract method spans
        # Expected format: "Method 'MethodName': spans lines X to Y"
        spans: list[tuple[str, int, int]] = []
        for match in re.finditer(r"Method\s+'([^']+)':\s+spans\s+lines\s+(\d+)\s+to\s+(\d+)", stdout):
            method_name = match.group(1)
            start_line = int(match.group(2))
            end_line = int(match.group(3))
            spans.append((method_name, start_line, end_line))
        
        if not spans:
            logger.debug(f"No method spans found in output from {file_path.name}")
            # Empty list indicates no methods were found
            _METHOD_CACHE[file_key] = []
            return None
        
        # Cache the spans
        _METHOD_CACHE[file_key] = spans
        
        # Find method containing fault_line
        for method_name, start_line, end_line in spans:
            if start_line <= fault_line <= end_line:
                logger.debug(
                    f"Fault at line {fault_line} is in method '{method_name}' "
                    f"(lines {start_line}-{end_line})"
                )
                return (method_name, start_line, end_line)
        
        logger.debug(f"Fault at line {fault_line} is not within any extracted method span")
        return None
        
    except FileNotFoundError as e:
        logger.warning(f"ReturnAtRandomAllLinesOfFailingMethod binary not found: {e}")
        return None
    except Exception as e:
        logger.warning(f"Failed to extract method span from {file_path.name}: {e}")
        return None


def clear_cache():
    """Clear the method cache. Useful for testing or forcing re-extraction."""
    _METHOD_CACHE.clear()
