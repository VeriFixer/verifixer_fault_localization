"""Tests for paper-only technique selection and aliases."""

from __future__ import annotations

from evaluators.eval_model_common import (
    get_technique_display_name,
    get_techniques_for_cntm_ablation,
    get_techniques_for_paper_only,
)



def test_get_techniques_for_paper_only_exact_subset() -> None:
    assert get_techniques_for_paper_only() == [
        "RAND",
        "CNTB",
        "CNTS",
        "CNTM",
        "LLM",
        "SNAP",
    ]



def test_paper_alias_mapping() -> None:
    assert get_technique_display_name("RAND", paper_only=True) == "RAND"
    assert get_technique_display_name("CNTB", paper_only=True) == "CNTB"
    assert get_technique_display_name("CNTS", paper_only=True) == "CNTS"
    assert get_technique_display_name("CNTM", paper_only=True) == "CNTM"
    assert get_technique_display_name("LLM", paper_only=True) == "LLM"
    assert get_technique_display_name("SNAP", paper_only=True) == "SNAP"
    assert get_technique_display_name("CNTS", paper_only=False) == "CNTS"
    assert get_technique_display_name("CNTB", paper_only=False) == "CNTB"



def test_get_techniques_for_cntm_ablation_exact_subset() -> None:
    assert get_techniques_for_cntm_ablation() == [
        "CNTM",
        "CNTM_pure_state",
        "CNTM_no_frequency",
        "CNTM_no_depth",
        "CNTM_no_control",
    ]
