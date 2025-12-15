
import unittest

from fl_eval.metrics.scoring import compute_exam_score_one_file

class TestExamMetric(unittest.TestCase):
    def test_bug_found_at_start(self):
        """Test when the bug is the very first prediction (best case)."""
        preds = [10, 12, 14]
        truth = 10
        found, score = compute_exam_score_one_file(preds, truth, 10, 14)
        
        self.assertTrue(found)
        self.assertAlmostEqual(score, 0)

    def test_bug_found_later_in_prediction(self):
        """Test when bug is in predictions but not first."""
        preds = [10, 12, 14]
        truth = 12
        found, score = compute_exam_score_one_file(preds, truth, 10, 14)
        
        self.assertTrue(found)
        self.assertAlmostEqual(score, 1/5)

    def test_bug_not_in_prediction(self):
        """Test when bug is missing from predictions (should be appended)."""
        preds = [10, 12] 
        truth = 13
        # Range 10-14. Missing: 11, 13, 14.
        # Full list becomes: [10, 12] + [11, 13, 14]
        # 13 is at index 3 (4th item).
        found, score = compute_exam_score_one_file(preds, truth, 10, 14)
        self.assertFalse(found)
        # Rank 4 out of 5 = 0.8
        self.assertAlmostEqual(score, 3/5)

    def test_empty_predictions(self):
        """Test when the FL tool returns no predictions."""
        preds: list[int] = []
        truth = 2
        # Range 1-3. List becomes [1, 2, 3]. Truth at index 1 (2nd item).
        found, score = compute_exam_score_one_file(preds, truth, 1, 3)
        
        self.assertFalse(found)
        self.assertAlmostEqual(score, 1/3)

    def test_out_of_bounds_error(self):
        """Ensure error is raised if ground truth is outside file lines."""
        with self.assertRaises(ValueError):
            compute_exam_score_one_file([1, 2], 99, 1, 10)
