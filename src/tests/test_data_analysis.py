import pytest
from unittest.mock import patch, MagicMock
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from analysis.data_analysis import compare_two_methods
from fl_eval.metrics.scoring import ExamOutput

def test_compare_two_methods_basic():
    """Test basic comparison with normal data"""
    raw_results = {
        'tech1': [
            ExamOutput(0.1, True, False, "file1.dfy"),
            ExamOutput(0.2, True, False, "file2.dfy"),
            ExamOutput(0.3, False, False, "file3.dfy"),
        ],
        'tech2': [
            ExamOutput(0.4, False, False, "file1.dfy"),
            ExamOutput(0.5, False, False, "file2.dfy"),
            ExamOutput(0.6, True, False, "file3.dfy"),
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
            ExamOutput(0.1, True, False, "file1.dfy"),  # found
            ExamOutput(0.2, False, False, "file2.dfy"), # not found
            ExamOutput(0.3, True, False, "file3.dfy"),  # found
        ],
        'tech2': [
            ExamOutput(0.4, False, False, "file1.dfy"), # not found
            ExamOutput(0.5, True, False, "file2.dfy"),  # found
            ExamOutput(0.6, False, False, "file3.dfy"), # not found
        ]
    }
    
    with patch('builtins.print') as mock_print:
        compare_two_methods(raw_results, 'tech1', 'tech2')
        
        calls = [call.args[0] for call in mock_print.call_args_list]
        # Should show 2 cases where tech1 only found, 1 where tech2 only found
        assert any("tech1 found fault but tech2 did not: 2 files" in call for call in calls)
        assert any("tech2 found fault but tech1 did not: 1 files" in call for call in calls)

if __name__ == "__main__":
    pytest.main([__file__])