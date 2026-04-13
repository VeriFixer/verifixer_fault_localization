import pytest
from unittest.mock import patch, MagicMock
import sys
import os
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from analysis.data_analysis import compare_two_methods, generate_plots, print_ascii_table, print_latex_table
from fl_eval.metrics.scoring import ExamOutput, ExamScore
from fl_eval.metrics.summary_stats import StatsSummaryEntry


def mk_exam(score: float, found: bool, filename: str) -> ExamOutput:
    scoped = ExamScore(score=score, found=found, prediction=True)
    return ExamOutput(
        filename=filename,
        method_name="m",
        file=scoped,
        method=scoped,
    )

def test_compare_two_methods_basic():
    """Test basic comparison with normal data"""
    raw_results = {
        'tech1': [
            mk_exam(0.1, True, "file1.dfy"),
            mk_exam(0.2, True, "file2.dfy"),
            mk_exam(0.3, False, "file3.dfy"),
        ],
        'tech2': [
            mk_exam(0.4, False, "file1.dfy"),
            mk_exam(0.5, False, "file2.dfy"),
            mk_exam(0.6, True, "file3.dfy"),
        ]
    }
    
    # Capture print output (for ASCII/LaTeX table output)
    with patch('builtins.print') as mock_print:
        compare_two_methods(raw_results, 'tech1', 'tech2')
        
        # Check that print was called multiple times
        assert mock_print.call_count > 5  # At least header, stats, overview
        
        # Check some key outputs
        calls = [call.args[0] for call in mock_print.call_args_list]
        assert any("Statistical Comparison" in str(call) for call in calls)
        assert any("Debugging Overview" in str(call) for call in calls)

def test_compare_two_methods_missing_tech():
    """Test with missing technique"""
    raw_results = {'tech1': []}
    
    # Mock the logger to capture error messages
    with patch('analysis.data_analysis.logger') as mock_logger:
        compare_two_methods(raw_results, 'tech1', 'tech2')
        
        # Check that logger.error was called with appropriate message
        mock_logger.error.assert_called()
        error_calls = [call.args[0] if call.args else str(call.kwargs) for call in mock_logger.error.call_args_list]
        assert any("not found in results" in str(call) for call in error_calls)

def test_compare_two_methods_empty_data():
    """Test with empty data"""
    raw_results = {'tech1': [], 'tech2': []}
    
    # Mock the logger to capture error messages
    with patch('analysis.data_analysis.logger') as mock_logger:
        compare_two_methods(raw_results, 'tech1', 'tech2')
        
        # Check that logger.error was called with appropriate message
        mock_logger.error.assert_called()
        error_calls = [call.args[0] if call.args else str(call.kwargs) for call in mock_logger.error.call_args_list]
        assert any("No data" in str(call) for call in error_calls)

def test_compare_two_methods_different_success_rates():
    """Test with different success patterns"""
    raw_results = {
        'tech1': [
            mk_exam(0.1, True, "file1.dfy"),  # found
            mk_exam(0.2, False, "file2.dfy"), # not found
            mk_exam(0.3, True, "file3.dfy"),  # found
        ],
        'tech2': [
            mk_exam(0.4, False, "file1.dfy"), # not found
            mk_exam(0.5, True, "file2.dfy"),  # found
            mk_exam(0.6, False, "file3.dfy"), # not found
        ]
    }
    
    with patch('builtins.print') as mock_print:
        compare_two_methods(raw_results, 'tech1', 'tech2')
        
        calls = [call.args[0] for call in mock_print.call_args_list]
        # Should show 2 cases where tech1 only found, 1 where tech2 only found
        assert any("tech1 found fault but tech2 did not: 2 files" in call for call in calls)
        assert any("tech2 found fault but tech1 did not: 1 files" in call for call in calls)


def test_generate_plots_creates_output_file(tmp_path: Path):
    raw_results = {
        "tech1": [
            mk_exam(0.1, True, "f1.dfy"),
            mk_exam(0.4, False, "f2.dfy"),
            mk_exam(0.2, True, "f3.dfy"),
        ],
        "tech2": [
            mk_exam(0.3, True, "f1.dfy"),
            mk_exam(0.8, False, "f2.dfy"),
            mk_exam(0.5, False, "f3.dfy"),
        ],
    }

    with patch("builtins.print"):
        generate_plots(raw_results, tmp_path)

    out_file = tmp_path / "benchmark_hybrid_analysis_FILE.png"
    assert out_file.exists()
    assert out_file.stat().st_size > 0


def test_print_ascii_table_includes_new_non_empty_prediction_columns():
    stats = {
        "tech1": StatsSummaryEntry(
            count=3,
            avg_exam_file=0.3333,
            avg_exam_not_empty_file=0.1234,
            found_rate_file=66.67,
            exist_rate_file=0.33,
            avg_exam_method=0.2222,
            avg_exam_not_empty_method=0.5678,
            found_rate_method=50.0,
            exist_rate_method=0.0,
            count_method=3,
        )
    }

    with patch("builtins.print") as mock_print:
        print_ascii_table(stats)

    calls = [str(call.args[0]) for call in mock_print.call_args_list if call.args]
    assert any("FILE SCOPE" in call for call in calls)
    assert any("METHOD SCOPE" in call for call in calls)
    assert any("EXAM_3" in call for call in calls)
    assert any("0.1234" in call for call in calls)
    assert any("0.5678" in call for call in calls)


def test_print_latex_table_includes_new_non_empty_prediction_columns():
    stats = {
        "tech1": StatsSummaryEntry(
            count=2,
            avg_exam_file=0.5,
            avg_exam_not_empty_file=0.125,
            found_rate_file=50.0,
            exist_rate_file=0.5,
            avg_exam_method=0.25,
            avg_exam_not_empty_method=0.875,
            found_rate_method=100.0,
            exist_rate_method=0.0,
            count_method=2,
        )
    }

    with patch("builtins.print") as mock_print:
        print_latex_table(stats)

    calls = [str(call.args[0]) for call in mock_print.call_args_list if call.args]
    assert any("\\textbf{Technique} & \\textbf{EXAM$_1$} & \\textbf{EXAM$_2$} & \\textbf{EXAM$_3$} & \\textbf{Found(\\%)} & \\textbf{Empty(\\%)}" in call for call in calls)
    assert any("Evaluated on 2 examples." in call for call in calls)
    assert any("0.1250" in call for call in calls)
    assert any("0.8750" in call for call in calls)
    assert any("50.00" in call for call in calls)

if __name__ == "__main__":
    pytest.main([__file__])