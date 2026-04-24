import pytest
from unittest.mock import patch, MagicMock
import sys
import os
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from analysis.data_analysis import (
    PairwiseStatResult,
    PairwiseTopKResult,
    build_pairwise_stat_results,
    build_pairwise_topk_results,
    compare_two_methods,
    generate_plots,
    print_ascii_table,
    print_latex_table,
    print_pairwise_topk_latex_table,
    print_pairwise_topk_table,
    print_pairwise_wilcoxon_latex_table,
    print_pairwise_wilcoxon_table,
)
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

    out_file = tmp_path / "benchmark_hybrid_analysis_FILE_success.png"
    assert out_file.exists()
    assert out_file.stat().st_size > 0


    out_file = tmp_path / "benchmark_hybrid_analysis_FILE_distribution.png"
    assert out_file.exists()
    assert out_file.stat().st_size > 0


def test_print_ascii_table_includes_new_non_empty_prediction_columns():
    stats = {
        "RAND": StatsSummaryEntry(
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
    assert any("RAND" in call for call in calls)
    assert any("0.1234" in call for call in calls)
    assert any("0.5678" in call for call in calls)


def test_print_latex_table_includes_new_non_empty_prediction_columns():
    stats = {
        "CNTB": StatsSummaryEntry(
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
    assert any("CNTB" in call for call in calls)
    assert any("0.1250" in call for call in calls)
    assert any("0.8750" in call for call in calls)
    assert any("50.00" in call for call in calls)


def test_print_pairwise_wilcoxon_table_reports_all_pairs():
    raw_results = {
        "CNTM": [
            mk_exam(0.10, True, "f1.dfy"),
            mk_exam(0.20, True, "f2.dfy"),
            mk_exam(0.30, False, "f3.dfy"),
        ],
        "TECH_A": [
            mk_exam(0.40, False, "f1.dfy"),
            mk_exam(0.50, False, "f2.dfy"),
            mk_exam(0.60, True, "f3.dfy"),
        ],
        "TECH_B": [
            mk_exam(0.15, True, "f1.dfy"),
            mk_exam(0.25, True, "f2.dfy"),
            mk_exam(0.35, False, "f3.dfy"),
        ],
    }

    with patch("builtins.print") as mock_print:
        rows = print_pairwise_wilcoxon_table(raw_results)

    assert len(rows) == 3
    assert any(row.technique_1 == "CNTM" and row.technique_2 == "TECH_A" for row in rows)
    assert any(row.technique_1 == "CNTM" and row.technique_2 == "TECH_B" for row in rows)
    assert any(row.technique_1 == "TECH_A" and row.technique_2 == "TECH_B" for row in rows)

    cntm_tech_a = next(row for row in rows if row.technique_1 == "CNTM" and row.technique_2 == "TECH_A")
    assert cntm_tech_a.pair_count == 3
    assert cntm_tech_a.p_value <= 1.0
    assert cntm_tech_a.rank_biserial < 0.0
    assert cntm_tech_a.nonzero_pair_count == 3

    calls = [str(call.args[0]) for call in mock_print.call_args_list if call.args]
    assert any("PAIRWISE WILCOXON SIGNED-RANK TESTS" in call for call in calls)
    assert any("Rank-biserial" in call for call in calls)
    assert any("CNTM" in call for call in calls)
    assert any("TECH_A" in call for call in calls)
    assert any("TECH_B" in call for call in calls)


def test_build_pairwise_stat_results_all_zero_differences():
    raw_results = {
        "A": [
            mk_exam(0.1, True, "f1.dfy"),
            mk_exam(0.2, False, "f2.dfy"),
        ],
        "B": [
            mk_exam(0.1, True, "f1.dfy"),
            mk_exam(0.2, False, "f2.dfy"),
        ],
    }

    rows = build_pairwise_stat_results(raw_results)
    assert len(rows) == 1
    row = rows[0]
    assert row.pair_count == 2
    assert row.nonzero_pair_count == 0
    assert row.statistic == 0.0
    assert row.p_value == 1.0
    assert row.rank_biserial == 0.0


def test_print_pairwise_top1_table_reports_all_pairs():
    raw_results = {
        "A": [
            ExamOutput(
                filename="f1.dfy",
                method_name="m",
                file=ExamScore(score=0.1, found=True, prediction=True, line_ground_truth=10, line_prediction=[10, 11]),
                method=ExamScore(score=0.1, found=True, prediction=True, line_ground_truth=10, line_prediction=[10, 11]),
            ),
            ExamOutput(
                filename="f2.dfy",
                method_name="m",
                file=ExamScore(score=0.4, found=False, prediction=True, line_ground_truth=20, line_prediction=[19, 20]),
                method=ExamScore(score=0.4, found=False, prediction=True, line_ground_truth=20, line_prediction=[19, 20]),
            ),
            ExamOutput(
                filename="f3.dfy",
                method_name="m",
                file=ExamScore(score=0.3, found=False, prediction=True, line_ground_truth=30, line_prediction=[29, 30]),
                method=ExamScore(score=0.3, found=False, prediction=True, line_ground_truth=30, line_prediction=[29, 30]),
            ),
        ],
        "B": [
            ExamOutput(
                filename="f1.dfy",
                method_name="m",
                file=ExamScore(score=0.2, found=True, prediction=True, line_ground_truth=10, line_prediction=[12, 10]),
                method=ExamScore(score=0.2, found=True, prediction=True, line_ground_truth=10, line_prediction=[12, 10]),
            ),
            ExamOutput(
                filename="f2.dfy",
                method_name="m",
                file=ExamScore(score=0.2, found=True, prediction=True, line_ground_truth=20, line_prediction=[20, 21]),
                method=ExamScore(score=0.2, found=True, prediction=True, line_ground_truth=20, line_prediction=[20, 21]),
            ),
            ExamOutput(
                filename="f3.dfy",
                method_name="m",
                file=ExamScore(score=0.2, found=True, prediction=True, line_ground_truth=30, line_prediction=[30, 31]),
                method=ExamScore(score=0.2, found=True, prediction=True, line_ground_truth=30, line_prediction=[30, 31]),
            ),
        ],
    }

    with patch("builtins.print") as mock_print:
        rows = print_pairwise_topk_table(raw_results, k=1)

    assert len(rows) == 1
    row = rows[0]
    assert row.pair_count == 3
    assert row.discordant_pairs == 3
    assert row.a_success_b_fail == 1
    assert row.a_fail_b_success == 2
    assert row.p_value <= 1.0

    calls = [str(call.args[0]) for call in mock_print.call_args_list if call.args]
    assert any("PAIRWISE MCNEMAR TESTS" in call for call in calls)
    assert any("OR(A/B)" in call for call in calls)


def test_print_pairwise_wilcoxon_latex_table_output():
    rows = [
        PairwiseStatResult(
            technique_1="CNTM",
            technique_2="TECH_A",
            pair_count=2,
            nonzero_pair_count=2,
            statistic=51062.0,
            p_value=5.008e-43,
            rank_biserial=0.7944,
            significant=True,
        )
    ]

    with patch("builtins.print") as mock_print:
        print_pairwise_wilcoxon_latex_table(rows, scope="file")

    calls = [str(call.args[0]) for call in mock_print.call_args_list if call.args]
    assert any("LaTeX Table Output (Pairwise Wilcoxon" in call for call in calls)
    assert any("\\begin{table}[h]" in call for call in calls)
    assert any("\\textbf{M.A} & \\textbf{M.B} & \\textbf{NZ} & \\textbf{W} & \\textbf{p} & \\textbf{R-bi} & \\textbf{Sig.}" in call for call in calls)
    assert any("51062 & 5e-43 & 0.794" in call for call in calls)
    assert any("R-bi = rank-biserial effect size" in call for call in calls)
    assert any("\\label{tab:pairwise_wilcoxon_file}" in call for call in calls)


def test_print_pairwise_topk_latex_table_output():
    rows = [
        PairwiseTopKResult(
            technique_1="A",
            technique_2="B",
            pair_count=2,
            discordant_pairs=109,
            a_success_b_fail=16,
            a_fail_b_success=93,
            p_value=2.209e-14,
            paired_odds_ratio=0.1765,
            significant=True,
        )
    ]

    with patch("builtins.print") as mock_print:
        print_pairwise_topk_latex_table(rows, scope="file", k=1)

    calls = [str(call.args[0]) for call in mock_print.call_args_list if call.args]
    assert any("LaTeX Table Output (Pairwise McNemar Top-1" in call for call in calls)
    assert any("\\begin{table}[h]" in call for call in calls)
    assert any("\\textbf{M.A} & \\textbf{M.B} & \\textbf{Disc.} & \\textbf{A-O} & \\textbf{B-O} & \\textbf{p} & \\textbf{OR} & \\textbf{Sig.}" in call for call in calls)
    assert any("16 & 93 & 2e-14 & 0.176" in call for call in calls)
    assert any("OR = paired odds ratio" in call for call in calls)
    assert any("\\label{tab:pairwise_mcnemar_top1_file}" in call for call in calls)

if __name__ == "__main__":
    pytest.main([__file__])