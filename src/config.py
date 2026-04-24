"""Central configuration module for Fault Localization framework.

This module centralizes all runtime configuration, replacing deprecated globals.py.

Responsibilities:
1. Repository root discovery via marker file
2. Paths: cache dirs, output dirs, strategy executables
3. Performance limits: timeouts and memory for external programs
4. Strategy executable paths with environment variable overrides

Usage:
    import config as gl
    print(gl.BASE_PATH)  # Repository root
    print(gl.CACHE_DIR)  # tmp/run_artifacts/cached_results
    print(gl.MAX_TIME_EXTERNAL_PROGRAMS)  # Timeout in seconds
    print(gl.RANDOM_FL_EXECUTABLE)  # Path to random strategy executable

Environment Variables (all optional):
    FL_MAX_RAM_GB: Override MAX_RAM_EXTERNAL_PROGRAMS (default: 24)
    FL_MAX_TIME_SECONDS: Override MAX_TIME_EXTERNAL_PROGRAMS (default: 60)
    FL_VERBOSE: Print full config on import if set to "1"
    FL_<TECHNIQUE>_EXECUTABLE: Override strategy executable path

Thread Safety:
    Module-level constants only. Thread-safe for read access. Do not mutate.

Migration Notes:
    fl_eval.util.globals is deprecated; use this module instead.
"""

from pathlib import Path
import os
from typing import Optional


def find_repo_root(marker: str = ".repo_verifixer_fault_localization_marker") -> Path:
    """Finds the root of the repository by looking for a marker file.
    
    Args:
        marker: Filename to search for (default: .repo_verifixer_fault_localization_marker)
    
    Returns:
        Path to the repository root directory
    
    Raises:
        FileNotFoundError: If marker file is not found when traversing up from current module
    """
    current: Path = Path(__file__).resolve().parent
    while str(current) != current.root:
        if (current / marker).exists():
            return current
        current = current.parent
    raise FileNotFoundError("Could not find repository root. Make sure you're running inside a valid repo.")


# === Repository Structure ===
BASE_PATH: Path = find_repo_root()
DATASET_ROOT: Path = BASE_PATH / "dataset" / "data"
DATASET_SCRIPTS_ROOT: Path = BASE_PATH / "dataset" / "scripts"
TMP_ROOT: Path = BASE_PATH / "tmp"
ARTIFACTS_ROOT: Path = TMP_ROOT / "run_artifacts"

# === Output and Cache Directories ===
CACHE_DIR: Path = ARTIFACTS_ROOT / "cached_results"
AUTOFIX_RUNS_DIR: Path = ARTIFACTS_ROOT / "autofix_fl_runs"
MODELS_LOG_DIR: Path = ARTIFACTS_ROOT / "models_log"
IMAGES_DIR: Path = ARTIFACTS_ROOT / "images"
PRETTY_OUTPUTS_DIR: Path = ARTIFACTS_ROOT / "pretty_outputs"

# === Performance Limrun_external_cmdits for External Programs ===
# Can be overridden via environment variables: FL_MAX_RAM_GB, FL_MAX_TIME_SECONDS
MAX_RAM_EXTERNAL_PROGRAMS: int = 24 # GB
MAX_TIME_EXTERNAL_PROGRAMS: int = 60 # Seconds
# Setting any tinmeout to 0 maked timeout infinite
MAX_TIME_AUTOFIX: int = 6*60*60 # Seconds (6 hours timeout)

# === Strategy Executable Paths ===
# These are discovered via BASE_PATH but can be overridden via environment variables
# for custom build locations or non-standard setups

def get_strategy_executable_path(
    strategy_name: str,
    env_var_name: Optional[str] = None
) -> Optional[Path]:
    """Get the path to a strategy executable with environment variable override support.
    
    Args:
        strategy_name: Name of strategy (e.g., 'CounterExampleIf')
        env_var_name: Optional environment variable name to check for override
    
    Returns:
        Path to executable if found, None otherwise
    """
    # Check environment override first
    if env_var_name and env_var_name in os.environ:
        override_path = Path(os.environ[env_var_name])
        if override_path.is_file():
            return override_path
    
    # Default discovery location
    default_search_dir = BASE_PATH / f"build_output/{strategy_name}"
    if default_search_dir.exists():
        return default_search_dir
    
    return None


# Convenience accessors for known strategies
COUNTER_EXAMPLE_IF_DIR: Optional[Path] = get_strategy_executable_path(
    "CounterExampleIf",
    "FL_COUNTER_EXAMPLE_IF_DIR"
)
COUNTER_EXAMPLE_IF_REASSUME_DIR: Optional[Path] = get_strategy_executable_path(
    "CounterExampleIfReassume",
    "FL_COUNTER_EXAMPLE_IF_REASSUME_DIR"
)
RETURN_AT_RANDOM_ALL_LINES_DIR: Optional[Path] = get_strategy_executable_path(
    "ReturnAtRandomAllLinesOfFailingMethod",
    "FL_RETURN_AT_RANDOM_ALL_LINES_DIR"
)
AUTOFIX_DIR: Path = BASE_PATH / "external" / "tools" / "dafny-autofix"

# Autofix script path
AUTOFIX_SCRIPT: Path = AUTOFIX_DIR / "run.sh"

def get_file_cache_path(file_path : Path, technique_name : str) -> Path:
    # Use the absolute path's name to create a dataset-specific cache dir

    dataset_folder = file_path.parent.parent.name
    file_name = file_path.name + ".json"

    
    return CACHE_DIR / dataset_folder / technique_name / file_name

def get_dataset_cache_dir(dataset_dir: Path) -> Path:
    """Get the cache directory for a specific dataset.
    
    Cache structure: tmp/run_artifacts/cached_results/<dataset_name>/
    
    Args:
        dataset_dir: Path to the dataset directory (e.g., dataset/data/pos_test).
    
    Returns:
        Path to the cache directory for this dataset.
    
    Examples:
        >>> get_dataset_cache_dir(Path("dataset/data/pos_test"))
        Path('tmp/run_artifacts/cached_results/pos_test')
    """
    # Use the absolute path's name to create a dataset-specific cache dir
    dataset_abs = dataset_dir.resolve()
    dataset_key = dataset_abs.name  # Use the directory name (e.g., "pos_test")
    
    return CACHE_DIR / dataset_key


def get_dataset_pretty_output_dir(dataset_dir: Path) -> Path:
    """Get the pretty-output artifact directory for a specific dataset.

    Artifact structure: tmp/run_artifacts/pretty_outputs/<dataset_name>/
    """
    dataset_abs = dataset_dir.resolve()
    dataset_key = dataset_abs.name
    return PRETTY_OUTPUTS_DIR / dataset_key


def get_pretty_output_file_path(mutant_file_path: Path, technique_name: str) -> Path:
    """Get per-mutant pretty-output artifact path for a technique.

    Returns a JSON file path using dataset/technique/mutant partitioning.
    """
    dataset_folder = mutant_file_path.parent.parent.name
    file_name = mutant_file_path.name + ".json"
    return PRETTY_OUTPUTS_DIR / dataset_folder / technique_name / file_name



def print_config(verbose: bool = True) -> None:
    """Print all configuration values to stdout.
    
    Useful for debugging and verifying configuration at runtime.
    
    Args:
        verbose: If True, print all configuration values. If False, print minimal info.
    """
    if verbose:
        print("\n" + "="*70)
        print("FAULT LOCALIZATION CONFIGURATION")
        print("="*70)
        print(f"Repository Root (BASE_PATH)        : {BASE_PATH}")
        print(f"Dataset Root                       : {DATASET_ROOT}")
        print(f"Dataset Scripts Root               : {DATASET_SCRIPTS_ROOT}")
        print(f"Tmp Root                           : {TMP_ROOT}")
        print(f"Artifacts Root                     : {ARTIFACTS_ROOT}")
        print(f"Cache Directory                    : {CACHE_DIR}")
        print(f"AutoFix Runs Directory             : {AUTOFIX_RUNS_DIR}")
        print(f"Model Logs Directory               : {MODELS_LOG_DIR}")
        print(f"Images Directory                   : {IMAGES_DIR}")
        print(f"Max RAM for External Programs      : {MAX_RAM_EXTERNAL_PROGRAMS} GB")
        print(f"Max Time for External Programs     : {MAX_TIME_EXTERNAL_PROGRAMS} seconds")
        print()
        print("Strategy Directories:")
        print(f"  CounterExampleIf                 : {COUNTER_EXAMPLE_IF_DIR if COUNTER_EXAMPLE_IF_DIR else '(not found)'}")
        print(f"  CounterExampleIfReassume         : {COUNTER_EXAMPLE_IF_REASSUME_DIR if COUNTER_EXAMPLE_IF_REASSUME_DIR else '(not found)'}")
        print(f"  ReturnAtRandomAllLines           : {RETURN_AT_RANDOM_ALL_LINES_DIR if RETURN_AT_RANDOM_ALL_LINES_DIR else '(not found)'}")
        print(f"  AutoFix                          : {AUTOFIX_DIR if AUTOFIX_DIR else '(not found)'}")
        print()
    else:
        print(f"Config: BASE_PATH={BASE_PATH}, MAX_RAM={MAX_RAM_EXTERNAL_PROGRAMS}GB, MAX_TIME={MAX_TIME_EXTERNAL_PROGRAMS}s")


# === Initialization ===
# Print configuration at module load time if FL_VERBOSE is set
if __name__ != "__main__" and os.environ.get("FL_VERBOSE"):
    print_config(verbose=True)
