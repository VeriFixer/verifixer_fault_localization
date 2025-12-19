
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
    def test_exam_score_lots_of_cases(self):
        # Prediction Inside ranks
        flag, score = compute_exam_score_one_file([1], 1, 1, 1)
        self.assertEqual(flag, True)
        self.assertAlmostEqual(score, 0)

        # Other extreme cases
        flag, score = compute_exam_score_one_file([1, 3, 2], 1, 1, 3)
        self.assertEqual(flag, True)
        self.assertAlmostEqual(score, 0)

        flag, score = compute_exam_score_one_file([1, 3, 2], 2, 1, 3)
        self.assertEqual(flag, True)
        self.assertAlmostEqual(score, 1)

        flag, score = compute_exam_score_one_file([1, 3, 2], 3, 1, 3)
        self.assertEqual(flag, True)
        self.assertAlmostEqual(score, 0.5)

        # Predictions not inside ranks
        flag, score = compute_exam_score_one_file([], 1, 1, 1)
        self.assertEqual(flag, False)
        self.assertAlmostEqual(score, 0)

        # When there are multiple equally-likely ranks the expected average is 0.5
        flag, score = compute_exam_score_one_file([], 1, 1, 2)
        self.assertEqual(flag, False)
        self.assertAlmostEqual(score, 0.5)

        flag, score = compute_exam_score_one_file([], 1, 1, 3)
        self.assertEqual(flag, False)
        self.assertAlmostEqual(score, 0.5)

        flag, score = compute_exam_score_one_file([], 1, 1, 4)
        self.assertEqual(flag, False)
        self.assertAlmostEqual(score, 0.5)

        # Complex scenarios that mix both (here should be 0 or -1 depending on case)
        flag, score = compute_exam_score_one_file([1], 1, 1, 3)
        self.assertEqual(flag, True)
        self.assertAlmostEqual(score, 0)

        flag, score = compute_exam_score_one_file([1, 2], 1, 1, 3)
        self.assertEqual(flag, True)
        self.assertAlmostEqual(score, 0)

        flag, score = compute_exam_score_one_file([1, 2], 3, 1, 3)
        self.assertEqual(flag, False)
        self.assertAlmostEqual(score, 1)

        # Possibilities [1,2,3] gives 0.5 and [1,3,2] gives 1 => mean 0.75
        flag, score = compute_exam_score_one_file([1], 2, 1, 3)
        self.assertEqual(flag, False)
        self.assertAlmostEqual(score, 0.75)

        # Possibilities [1,2,3,4,5] and [1,2,3,5,4] both score 1/(5-1) = 0.25
        flag, score = compute_exam_score_one_file([1, 2, 3], 2, 1, 5)
        self.assertEqual(flag, True)
        self.assertAlmostEqual(score, 0.25) 