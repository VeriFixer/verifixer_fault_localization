import unittest
from pathlib import Path

# Assume fl_eval is correctly installed or paths are set up for relative import
from fl_eval.core.baselines import RandomRanker

class TestFLCore(unittest.TestCase):
    
    def setUp(self):
        """Create a temporary dummy file for testing."""
        self.temp_file_path = Path("temp_code_file.py")
        self.temp_file_path.write_text(
            "line 1\n"
            "line 2\n"
            "line 3\n"
            "line 4\n"
            "line 5\n"
        )
        self.total_lines = 5
        self.ranker = RandomRanker(name="TestRanker")

    def tearDown(self):
        """Clean up the temporary file."""
        if self.temp_file_path.exists():
            self.temp_file_path.unlink()

    def test_random_ranker_output(self):
        """Check if RandomRanker returns all lines and shuffles them."""
        
        ranking = self.ranker.get_fault_localization(self.temp_file_path)
        
        # 1. Check length
        self.assertEqual(len(ranking), self.total_lines)
        
        # 2. Check content (must contain all lines from 1 to 5)
        expected_set = set(range(1, self.total_lines + 1))
        self.assertEqual(set(ranking), expected_set)
        
        # 3. Check if it's generally shuffled (a weak check, but better than none)
        unshuffled = list(range(1, self.total_lines + 1))
        # Note: This assert can fail very rarely, but it confirms the intent to shuffle.
        self.assertNotEqual(ranking, unshuffled, "The list should be shuffled.")
        
    def test_random_ranker_name(self):
        """Check if the name property is set correctly."""
        self.assertEqual(self.ranker.name, "TestRanker")