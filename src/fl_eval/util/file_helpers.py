from pathlib import Path
def read_diff_file(path : Path) -> str:
        """Helper to safely read the content of the diff file."""
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise FileNotFoundError(f"Diff file not found at {path}")
        except Exception as e:
            raise IOError(f"Error reading diff file {path}: {e}")
        