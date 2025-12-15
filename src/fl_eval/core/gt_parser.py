
from pathlib import Path
from typing import Optional
from fl_eval.util.file_helpers import read_diff_file  # Import helper from the same package

class GroundTruthAndLineLimitFinder:
    """
    Represents the ground truth for a fault localization task where the 
    MUTANT file is the buggy version under test. The ground truth is the 
    line number in the MUTANT file that was changed from the original.
    """
    def __init__(self, originalfile: Path, mutantfile: Path, difffile: Path):
        self.originalfile = originalfile
        self.mutantfile = mutantfile
        self.difffile = difffile
        self.ground_truth: Optional[int] = None
        self._parse_ground_truth()

    def _read_diff_file(self) -> str:
        """Helper to safely read the content of the diff file."""
        try:
            return self.difffile.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise FileNotFoundError(f"Diff file not found at {self.difffile}")
        except Exception as e:
            raise IOError(f"Error reading diff file {self.difffile}: {e}")

    def _parse_ground_truth(self):
        """
        Extracts the ground truth line number from the diff file content.
        
        The ground truth is taken from the right side (Mutant/Buggy file).
        - For XcY, we take Y.
        - For XaY,Z, we take Y (the start of the lines added).
        - For XdY, it represents deleted lines, which means the line *before* Y 
          in the mutant file caused the shift. In this setup, we usually ignore 'd' 
          or focus on lines near the deleted point if the FL is run on the mutant.
          However, for simplicity in mutation testing, we focus on 'c' and 'a'.
        """
        diff_content = self._read_diff_file()
        
        for line in diff_content.splitlines():
            # Check for change, delete, or add operations
            if 'c' in line:
                # Example: '13c16' -> splits into ['13', '16']
                parts = line.split('c')
                if len(parts) == 2:
                    mutant_side = parts[1]
                else:
                    continue
            elif 'a' in line:
                # Example: '13a16,18' -> splits into ['13', '16,18']
                parts = line.split('a')
                if len(parts) == 2:
                    mutant_side = parts[1]
                else:
                    continue
            elif 'd' in line:
                # Example: '13,15d16' -> splits into ['13,15', '16']
                # Deletion means lines 13-15 in original are gone, affecting line 16 onwards in mutant.
                # If the bug is a change (c) or addition (a), these are usually more relevant.
                # For deletion (d), the focus shifts to the resulting lines in the mutant (right side)
                parts = line.split('d')
                if len(parts) == 2:
                    mutant_side = parts[1]
                else:
                    continue
            else:
                continue

            # The line number might be a range (e.g., '16,18'). We take the start line.
            if ',' in mutant_side:
                start_line_str = mutant_side.split(',')[0]
            else:
                start_line_str = mutant_side
                
            try:
                self.ground_truth = int(start_line_str)
                # Found the first change, which represents the ground truth
                return 
            except ValueError:
                # Skip if the right side is not a valid number
                continue

        if self.ground_truth is None:
            raise ValueError(f"Could not extract ground truth line number from diff file: {self.difffile}")
        
