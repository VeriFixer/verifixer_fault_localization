"""Tests for paper-only technique selection and aliases."""

from __future__ import annotations

import argparse

from fl_eval.util.run_model_common import (
    get_technique_display_name,
    get_techniques_for_cntm_ablation,
    get_techniques_for_paper_only,
)
from run_common import build_common_runner_parser



def test_get_techniques_for_paper_only_exact_subset() -> None:
    assert get_techniques_for_paper_only() == [
        "randomOnFailingMethod",
        "counterBase",
        "counterExampleIf",
        "counterExampleIfReassume",
        "llm_real",
        "autofixDefault",
    ]



def test_paper_alias_mapping() -> None:
    assert get_technique_display_name("randomOnFailingMethod", paper_only=True) == "RAND"
    assert get_technique_display_name("counterBase", paper_only=True) == "CNTB"
    assert get_technique_display_name("counterExampleIf", paper_only=True) == "CNTS"
    assert get_technique_display_name("counterExampleIfReassume", paper_only=True) == "CNTM"
    assert get_technique_display_name("llm_real", paper_only=True) == "LLM"
    assert get_technique_display_name("autofixDefault", paper_only=True) == "SNAP"
    assert get_technique_display_name("counterExampleIf", paper_only=False) == "counterExampleIf"
    assert get_technique_display_name("counterBase", paper_only=False) == "counterBase"



def test_get_techniques_for_cntm_ablation_exact_subset() -> None:
    assert get_techniques_for_cntm_ablation() == [
        "counterExampleIfReassume",
        "CNTM_pure_state",
        "CNTM_no_frequency",
        "CNTM_no_depth",
        "CNTM_no_control",
    ]


def test_common_runner_parser_includes_use_paper_names_flag() -> None:
    parser = build_common_runner_parser("test parser")

    args = parser.parse_args(["datasets/pos_test", "--use-paper-names"])
    assert isinstance(parser, argparse.ArgumentParser)
    assert args.use_paper_names is True
