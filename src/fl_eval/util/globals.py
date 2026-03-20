from pathlib import Path

def find_repo_root(marker : str =".repo_verifixer_fault_localization_marker"):
    """Finds the root of the repository by looking for a marker (default: .git)."""
    print(marker)
    current: Path = Path(__file__).resolve().parent
    while str(current) != current.root:
        if (current / marker).exists():
            return current
        current = current.parent
    raise FileNotFoundError("Could not find repository root. Make sure you're running inside a valid repo.")

BASE_PATH: Path = find_repo_root() 

MAX_RAM_EXTERNAL_PROGRAMS : int = 24  # GBytes
MAX_TIME_EXTERNAL_PROGRAMS : int = 60 # Seconds

print(f"BASE_PATH is: {BASE_PATH}")