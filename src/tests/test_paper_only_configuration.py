"""Tests for paper-only technique selection and aliases."""

from __future__ import annotations

import argparse
import unittest

from fl_eval.util.run_model_common import get_technique_display_name, get_techniques_for_paper_only
from run_all_models import validate_run_mode_flags



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



def test_run_all_models_rejects_health_check_with_paper_only() -> None:
    parser = argparse.ArgumentParser()

    with unittest.TestCase().assertRaises(SystemExit):
        validate_run_mode_flags(
            parser,
            paper_only=True,
            health_check=True,
        )


def test_run_all_models_accepts_paper_only_without_health_check() -> None:
    parser = argparse.ArgumentParser()

    validate_run_mode_flags(
        parser,
        paper_only=True,
        health_check=False,
    )
