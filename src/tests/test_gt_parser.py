import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
# Assume fl_eval is correctly installed or paths are set up for relative import
from fl_eval.core.gt_parser import GroundTruthAndLineLimit
from tempfile import TemporaryDirectory

class TestGroundTruthAndLineLimitFinder(unittest.TestCase):
    def test_given_file_content_and_line_limits(self):
        """
        Tests the ground truth extraction (8c8) AND the new line limit logic.
        """
        
        # 1. Define the specific diff content
        diff_content = (
            "8c8\n"
            "< \tif x > 0 {\n"
            "---\n"
            "> \tif true {"
        )
        
        # 2. Define content for the mutant file (used to determine line limits)
        mutant_file_content = (
            "line 1\n"
            "line 2\n"
            "line 3\n"
            "line 4\n"
            "line 5\n"
            "line 6\n"
            "line 7\n"
            "line 8 (The bug)\n"
            "line 9\n"
            "line 10\n"
            # This file has exactly 10 lines.
        )
        expected_end_line = 10
        
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create dummy file paths
            original_path = temp_path / "original.txt"
            mutant_path = temp_path / "mutant.txt"
            diff_path = temp_path / "abs__124_BBR_true.txt"
            # Write contents to the necessary files
            diff_path.write_text(diff_content)
            mutant_path.write_text(mutant_file_content) # *** NEW STEP ***
            # 3. Instantiate the Finder class
            finder_instance = GroundTruthAndLineLimit(original_path, mutant_path, diff_path)
            # 4. ASSERTIONS FOR GROUND TRUTH (unchanged)
            expected_ground_truth = 8
            self.assertEqual(finder_instance.ground_truth, expected_ground_truth, 
                             "The ground truth should be 8 for the '8c8' diff.")
            # 5. ASSERTIONS FOR LINE LIMITS (*** NEW ASSERTIONS ***)
            self.assertEqual(finder_instance.startLine, 1,
                             "startLine should be 1 (start of the file).")
            self.assertEqual(finder_instance.endLine, expected_end_line,
                             f"endLine should be {expected_end_line} (last line of mutant file).")

    def test_diff_with_range_and_delete(self):
        """Tests a different diff format: a range and a delete operation."""
        diff_content_range = (
            "15d14\n"
            "<     // Deleted line\n"
            "20,22c19,21\n"
            "< line 20 old\n"
            "< line 21 old\n"
            "< line 22 old\n"
            "---\n"
            "> line 20 new\n"
            "> line 21 new\n"
            "> line 22 new\n"
        )
        # Since we are not explicitly writing content for mutant2.txt, 
        # the line count will be 0, which should trigger a ValueError.
        expected_ground_truth = 14
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            original_path = temp_path / "original2.txt"
            mutant_path = temp_path / "mutant2.txt"
            diff_path = temp_path / "test_diff_2.txt"
            diff_path.write_text(diff_content_range)
            # Create a 5-line dummy mutant file for this test
            mutant_path.write_text("1\n2\n3\n4\n5\n")
            expected_end_line = 5
            finder_instance = GroundTruthAndLineLimit(original_path, mutant_path, diff_path)
            # Assert GT
            self.assertEqual(finder_instance.ground_truth, expected_ground_truth,
                             "The ground truth should be 14 (first change detected).")
            # Assert Limits
            self.assertEqual(finder_instance.startLine, 1)
            self.assertEqual(finder_instance.endLine, expected_end_line)
