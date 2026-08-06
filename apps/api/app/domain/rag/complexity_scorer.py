"""Linguistic query complexity scorer.

Scores query complexity without any LLM call. Returns a float in [0.0, 1.0].
Used to gate LLM decomposition — only queries above the configured threshold
trigger the decomposer.

Signals detected:
- Conjunction keywords (multi-intent indicators)
- Comparison patterns (X vs Y, difference between)
- Multi-entity detection (quoted terms, capitalized proper nouns)
- Causal/impact chains
- Multiple interrogatives
"""

from __future__ import annotations

import re

# Conjunction keywords that indicate multi-intent queries
_CONJUNCTION_PATTERNS = re.compile(
    r"\b(dan|serta|juga|also|and|as well as|furthermore|moreover|additionally)\b",
    re.IGNORECASE,
)

# Comparison patterns
_COMPARISON_PATTERNS = re.compile(
    r"\b(versus|vs\.?|compared to|comparison|perbedaan|difference between|difference|"
    r"lebih baik dari|better than|worse than|dibanding|dibandingkan)\b",
    re.IGNORECASE,
)

# Causal / impact chain keywords
_CAUSAL_PATTERNS = re.compile(
    r"\b(dampak|impact|effect of|effects of|influence of|pengaruh|karena|"
    r"akibat|result of|resulting in|leads to|cause of|disebabkan)\b",
    re.IGNORECASE,
)

# Temporal multi-hop keywords
_TEMPORAL_PATTERNS = re.compile(
    r"\b(sebelum dan sesudah|before and after|historical(ly)?|over time|"
    r"trend|perubahan dari|change from|evolution of)\b",
    re.IGNORECASE,
)


def score(query: str) -> float:
    """Score query complexity as a float in [0.0, 1.0].

    Higher score = more likely to benefit from decomposition.
    """
    if not query or not query.strip():
        return 0.0

    text = query.strip()
    score_sum = 0.0

    # Signal 1: conjunction keywords (up to 0.25)
    conjunction_hits = len(_CONJUNCTION_PATTERNS.findall(text))
    score_sum += min(conjunction_hits * 0.1, 0.25)

    # Signal 2: comparison patterns (0.25 each, cap at 0.25)
    if _COMPARISON_PATTERNS.search(text):
        score_sum += 0.25

    # Signal 3: causal/impact chains (0.2 each, cap at 0.2)
    if _CAUSAL_PATTERNS.search(text):
        score_sum += 0.2

    # Signal 4: temporal multi-hop (0.15)
    if _TEMPORAL_PATTERNS.search(text):
        score_sum += 0.15

    # Signal 5: multiple quoted terms (0.1 per extra entity, cap at 0.2)
    quoted_terms = re.findall(r'"[^"]+"', text)
    if len(quoted_terms) > 1:
        score_sum += min((len(quoted_terms) - 1) * 0.1, 0.2)

    # Signal 6: multiple question marks or coordinated interrogatives (0.1)
    question_count = text.count("?")
    if question_count > 1:
        score_sum += 0.1

    # Signal 7: long query with many clauses — proxy via word count (0.1)
    word_count = len(text.split())
    if word_count > 20:
        score_sum += 0.1

    return min(score_sum, 1.0)
