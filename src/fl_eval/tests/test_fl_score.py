import unittest
from pathlib import Path

# Assume fl_eval is correctly installed or paths are set up for relative import
from fl_eval.strategies.random_ranker import RandomRanker
from pathlib import Path

# Assume fl_eval is correctly installed or paths are set up for relative import
from fl_eval.metrics.scoring import compute_exam_score # Assuming this is the renamed compute_exam_score_one_file

# --- MOCK CLASSES (needed for the test environment) ---
# We need a mock class that holds the attributes required by compute_exam_score
class MockGroundTruth:
    """Mock object to simulate the GroundTruthAndLineLimitFinder instance."""
    def __init__(self, mutantfile: Path, gt: int, start: int, end: int):
        self.mutantfile = mutantfile
        self.ground_truth = gt
        self.startLine = start
        self.endLine = end

class TestFLCore(unittest.TestCase):
    
    def setUp(self):
        """Create a temporary dummy file for testing."""
        self.temp_file_path = Path("temp_code_file.py")
        self.code_content = (
            "line 1\n"
            "line 2\n"
            "line 3\n"
            "line 4\n"
            "line 5\n"
        )
        self.temp_file_path.write_text(self.code_content)
        self.total_lines = 5
        self.ranker = RandomRanker(name="TestRanker")

    def tearDown(self):
        """Clean up the temporary file."""
        if self.temp_file_path.exists():
            self.temp_file_path.unlink()

    # --- Original Tests ---
    
    def test_random_ranker_output(self):
        """Check if RandomRanker returns all lines and shuffles them."""
        # ... (Body unchanged)
        ranking = self.ranker.get_fault_localization(self.temp_file_path)
        
        self.assertEqual(len(ranking), self.total_lines)
        expected_set = set(range(1, self.total_lines + 1))
        self.assertEqual(set(ranking), expected_set)
        
        unshuffled = list(range(1, self.total_lines + 1))
        self.assertNotEqual(ranking, unshuffled, "The list should be shuffled.")
        
    def test_random_ranker_name(self):
        """Check if the name property is set correctly."""
        self.assertEqual(self.ranker.name, "TestRanker")

    # --- New Test for compute_exam_score ---

    def test_compute_exam_score_integration(self):
        """
        Tests the compute_exam_score function by using RandomRanker 
        and checking the resulting score based on the ground truth.
        """
        # Set ground truth to an arbitrary line within the 5 lines.
        # We set it to 3 (the middle line).
        ground_truth = 3
        
        # 1. Create the Mock Ground Truth instance
        mock_gtruth = MockGroundTruth(
            mutantfile=self.temp_file_path, 
            gt=ground_truth, 
            start=1, 
            end=self.total_lines  # 5
        )
        
        # 2. Run the function multiple times due to the random nature of RandomRanker
        # We need to assert that the score is always a valid value (0.0, 0.2, 0.4, 0.6, or 0.8)
        
        num_runs = 100
        valid_scores = {0.0, 0.2, 0.4, 0.6, 0.8} # Ranks 0-4 out of 5 total lines

        for _ in range(num_runs):
            examp_out = compute_exam_score(self.ranker, mock_gtruth)
            found, score, empty = examp_out.found, examp_out.score, examp_out.empty 
            
            # Since RandomRanker covers all lines, the bug should always be found 
            # within the completed ranking list, and thus, within the full set of lines (1-5).
            self.assertIn(score, valid_scores, 
                          f"Score {score} is outside the expected range of {{0.0, 0.2, 0.4, 0.6, 0.8}}.")
            
            # The 'found' status depends on whether the random ranking put the GT in the 
            # *original* prediction list (if the FLT had filtering). Since RandomRanker 
            # returns ALL lines, the bug is always found in the list it returns.
            # However, for robustness, we just ensure the score is valid.