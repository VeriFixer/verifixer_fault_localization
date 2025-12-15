import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

# Assume fl_eval is correctly installed or paths are set up for relative import
from fl_eval.core.gt_parser import GroundTruthAndLineLimitFinder

from tempfile import TemporaryDirectory
class TestGroundTruthAndLineLimitFinder(unittest.TestCase):
    
    def test_given_file_content(self):
        """Tests the specific diff content provided by the user (8c8)."""
        
        # 1. Define the specific diff content
        diff_content = (
            "8c8\n"
            "< \tif x > 0 {\n"
            "---\n"
            "> \tif true {"
        )
        
        # 2. Use a temporary directory to create the dummy files safely
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create dummy file paths
            original_path = temp_path / "original.txt"
            mutant_path = temp_path / "mutant.txt"
            diff_path = temp_path / "abs__124_BBR_true.txt"
            
            # Write the diff content to the specified file path
            diff_path.write_text(diff_content)

            # 3. Instantiate the Prevision class
            prevision_instance = GroundTruthAndLineLimitFinder(original_path, mutant_path, diff_path)
            
            # 4. Assert the expected ground truth
            expected_ground_truth = 8
            self.assertEqual(prevision_instance.ground_truth, expected_ground_truth, 
                             "The ground truth should be 8 for the '8c8' diff.")

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
        
        # In this case, the first change is at line 15 ('15d14'), so 15 is the ground truth.
        expected_ground_truth = 14
        
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            original_path = temp_path / "original2.txt"
            mutant_path = temp_path / "mutant2.txt"
            diff_path = temp_path / "test_diff_2.txt"
            diff_path.write_text(diff_content_range)
            
            prevision_instance = GroundTruthAndLineLimitFinder(original_path, mutant_path, diff_path)
            self.assertEqual(prevision_instance.ground_truth, expected_ground_truth,
                             "The ground truth should be 14 (first change detected).")

    def test_no_changes(self):
        """Tests a diff file with no actual changes."""
        
        diff_content_empty = (
            "--- original.txt\n"
            "+++ mutant.txt\n"
        )
        
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            original_path = temp_path / "original3.txt"
            mutant_path = temp_path / "mutant3.txt"
            diff_path = temp_path / "test_diff_3.txt"
            diff_path.write_text(diff_content_empty)
            
            # We expect a ValueError because no ground truth could be extracted
            with self.assertRaises(ValueError):
                GroundTruthAndLineLimitFinder(original_path, mutant_path, diff_path)
