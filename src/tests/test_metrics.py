
import unittest

from fl_eval.metrics.scoring import compute_exam_score_one_file

class TestExamMetric(unittest.TestCase):
    def test_bug_found_at_start(self):
        """Test when the bug is the very first prediction (best case)."""
        preds = [10, 12, 14]
        truth = 10
        exam_out = compute_exam_score_one_file(preds, truth, 10, 14)
        found, score = exam_out.found, exam_out.score
        
        self.assertTrue(found)
        self.assertAlmostEqual(score, 0)

    def test_bug_found_later_in_prediction(self):
        """Test when bug is in predictions but not first."""
        preds = [10, 12, 11, 13, 14]
        truth = 12
        # Examp score gives  score from 0 to 1 to the predictions. in this case if ground truth is 10 score is 0, and 
        # 14 is 1. So fot the other values they must give a distributed sore betwen 0 and 1
        # 0 , 0.25, 0.5, 0.75, 1 for the ranks 10, 12, 11, 13, 14 
        # So the score is n_tested_lines_before_gt/ total_lines -1 
        # If reuslt truth was ten exam would
        exam_out = compute_exam_score_one_file(preds, truth, 10, 14)
        found, score = exam_out.found, exam_out.score

        self.assertTrue(found)
        self.assertAlmostEqual(score, 1/4)

    def test_bug_found_later_in_prediction_not_complete(self):
        """Test when bug is in predictions but not first."""
        preds = [10, 12]
        truth = 12
        # Must give exactly same score as previout test 
        exam_out = compute_exam_score_one_file(preds, truth, 10, 14)
        found, score = exam_out.found, exam_out.score

        self.assertTrue(found)
        self.assertAlmostEqual(score, 1/4)

    def test_bug_not_in_prediction(self):
        """Test when bug is missing from predictions (should be appended)."""
        preds = [10, 12] 
        truth = 13
        # Range 10-14. Missing: 11, 13, 14.
        # Here basically the numver of not used lines is 2 + (3-1)/2 
        # being (3-1)/2 the number of expected lines that I need to check untill dind the line 13 
        # for intances if 13 is right at beggining 0, after 1, after 2 mean 1. 

        # 2 + (3-1)/2 /4 = 3/4 = 0.75


        # Also this must be equivalent to the expected value of all combination so the average of them
        # Full list becomes: [10, 12] + [a, 13, b], score 3/4 = 0.75
        # Full list becomes: [10, 12] + [13, d, f] score 2/4 = 0.5
        # Full list becomes: [10, 12] + [i, g, 13] score 4/4 = 1 
        # Average score = 0.75 + 0.5 + 1 / 3 = 0.75
        # 13 is at index 3 (4th item).
        exam_out = compute_exam_score_one_file(preds, truth, 10, 14)
        found, score = exam_out.found, exam_out.score
        self.assertFalse(found)
        self.assertAlmostEqual(score, 3/4)

    def test_bug_not_in_prediction_bigger(self):
        """Test when bug is missing from predictions (should be appended)."""
        preds = [10] 
        truth = 13

        # Explication follows formula derived before
        # Range 10-14. Missing: 11, 13, 14.
        # Here basically the numver of not used lines is 2 + (3-1)/2 
        # being (3-1)/2 the number of expected lines that I need to check untill dind the line 13 
        # for intances if 13 is right at beggining 0, after 1, after 2 mean 1. 

        # (1 + (4-1)/2) /4 = (1 + 1.5) /4 = 2.5/4 = 0.625

        exam_out = compute_exam_score_one_file(preds, truth, 10, 14)
        found, score = exam_out.found, exam_out.score
        self.assertFalse(found)
        self.assertAlmostEqual(score, 0.625)
    def test_empty_predictions(self):
        """Test when the FL tool returns no predictions."""
        preds: list[int] = []
        truth = 2
        # Range 1-3. List becomes [1, 2, 3]. Truth at index 1 (2nd item).
        exam_out = compute_exam_score_one_file(preds, truth, 1, 3)
        found, score = exam_out.found, exam_out.score
        
        self.assertFalse(found)
        self.assertAlmostEqual(score, 1/2)

    def test_out_of_bounds_error(self):
        """Ensure error is raised if ground truth is outside file lines."""
        with self.assertRaises(ValueError):
            compute_exam_score_one_file([1, 2], 99, 1, 10)
    def test_exam_score_lots_of_cases(self):
        # Prediction Inside ranks
        exam_out = compute_exam_score_one_file([1], 1, 1, 1)
        self.assertEqual(exam_out.found, True)
        self.assertAlmostEqual(exam_out.score, 0)

        # Other extreme cases
        exam_out = compute_exam_score_one_file([1, 3, 2], 1, 1, 3)
        self.assertEqual(exam_out.found, True)
        self.assertAlmostEqual(exam_out.score, 0)

        exam_out = compute_exam_score_one_file([1, 3, 2], 2, 1, 3)
        self.assertEqual(exam_out.found, True)
        self.assertAlmostEqual(exam_out.score, 1)

        exam_out = compute_exam_score_one_file([1, 3, 2], 3, 1, 3)
        self.assertEqual(exam_out.found, True)
        self.assertAlmostEqual(exam_out.score, 0.5)

        # Predictions not inside ranks
        exam_out = compute_exam_score_one_file([], 1, 1, 1)
        self.assertEqual(exam_out.found, False)
        self.assertAlmostEqual(exam_out.score, 0)

        # When there are multiple equally-likely ranks the expected average is 0.5
        exam_out = compute_exam_score_one_file([], 1, 1, 2)
        self.assertEqual(exam_out.found, False)
        self.assertAlmostEqual(exam_out.score, 0.5)

        exam_out = compute_exam_score_one_file([], 1, 1, 3)
        self.assertEqual(exam_out.found, False)
        self.assertAlmostEqual(exam_out.score, 0.5)

        exam_out = compute_exam_score_one_file([], 1, 1, 4)
        self.assertEqual(exam_out.found, False)
        self.assertAlmostEqual(exam_out.score, 0.5)

        # Complex scenarios that mix both (here should be 0 or -1 depending on case)
        exam_out = compute_exam_score_one_file([1], 1, 1, 3)
        self.assertEqual(exam_out.found, True)
        self.assertAlmostEqual(exam_out.score, 0)

        exam_out = compute_exam_score_one_file([1, 2], 1, 1, 3)
        self.assertEqual(exam_out.found, True)
        self.assertAlmostEqual(exam_out.score, 0)

        exam_out = compute_exam_score_one_file([1, 2], 3, 1, 3)
        self.assertEqual(exam_out.found, False)
        self.assertAlmostEqual(exam_out.score, 1)

        # Possibilities [1,2,3] gives 0.5 and [1,3,2] gives 1 => mean 0.75
        exam_out = compute_exam_score_one_file([1], 2, 1, 3)
        self.assertEqual(exam_out.found, False)
        self.assertAlmostEqual(exam_out.score, 0.75)

        # Possibilities [1,2,3,4,5] and [1,2,3,5,4] both score 1/(5-1) = 0.25
        exam_out = compute_exam_score_one_file([1, 2, 3], 2, 1, 5)
        self.assertEqual(exam_out.found, True)
        self.assertAlmostEqual(exam_out.score, 0.25) 