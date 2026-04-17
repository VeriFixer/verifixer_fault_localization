import pytest

from analysis.query_exam_results import _match_threshold, _parse_techniques


def test_match_threshold_operators() -> None:
    assert _match_threshold(0.5, ">", 0.1)
    assert _match_threshold(0.5, ">=", 0.5)
    assert _match_threshold(0.5, "<", 0.9)
    assert _match_threshold(0.5, "<=", 0.5)
    assert _match_threshold(0.5, "==", 0.5)


def test_parse_techniques_defaults_to_all() -> None:
    techniques = _parse_techniques(None)
    assert "CNTM" in techniques
    assert "RANDFILE" in techniques


def test_parse_techniques_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        _parse_techniques("CNTM,NOPE")
