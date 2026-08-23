"""Unit tests for the linguistic query complexity scorer."""

import pytest

from app.domain.rag.complexity_scorer import score


def test_empty_query_returns_zero() -> None:
    assert score("") == 0.0
    assert score("   ") == 0.0


def test_simple_query_returns_low_score() -> None:
    result = score("What is the refund policy?")
    assert result < 0.3


def test_conjunction_increases_score() -> None:
    simple = score("What is the refund policy?")
    with_conjunction = score("What is the refund policy and the return process?")
    assert with_conjunction > simple


def test_comparison_pattern_increases_score() -> None:
    result = score("What is the difference between plan A and plan B?")
    assert result >= 0.25


def test_vs_comparison_detected() -> None:
    result = score("Compare policy A vs policy B")
    assert result >= 0.25


def test_causal_pattern_increases_score() -> None:
    result = score("What is the impact of the new policy on productivity?")
    assert result >= 0.2


def test_indonesian_causal_detected() -> None:
    result = score("Apa dampak kebijakan baru terhadap produktivitas?")
    assert result >= 0.2


def test_temporal_pattern_increases_score() -> None:
    result = score("How has the policy changed before and after the merger?")
    assert result >= 0.15


def test_multiple_quoted_terms_increases_score() -> None:
    result = score('Compare "department A" and "department B" leave policies')
    assert result >= 0.1


def test_multiple_question_marks_increases_score() -> None:
    result = score("What is the policy? How does it apply? When was it updated?")
    assert result >= 0.1


def test_long_query_increases_score() -> None:
    long_query = " ".join(["word"] * 25)
    result = score(long_query)
    assert result >= 0.1


def test_complex_query_scores_high() -> None:
    complex_query = (
        "What is the difference between department A and department B leave policies, "
        "and what is the impact on employee productivity and retention?"
    )
    result = score(complex_query)
    assert result >= 0.5


def test_score_capped_at_one() -> None:
    very_complex = (
        'Compare "policy A" vs "policy B" and "policy C", '
        "what is the impact and effect of each? "
        "How did they change before and after 2020? "
        "Also what are the differences and similarities? "
        "Furthermore what are the long term effects?"
    )
    result = score(very_complex)
    assert result <= 1.0


def test_indonesian_conjunction_detected() -> None:
    result = score("Apa perbedaan kebijakan cuti serta tunjangan antara departemen A dan B?")
    assert result >= 0.3
