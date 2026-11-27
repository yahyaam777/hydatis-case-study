"""Evaluation metrics for the Hydatis help-center case study."""

from dataclasses import dataclass
from typing import Dict, Iterable, Optional

CUTOFFS = (1, 3, 5)


@dataclass
class QuestionScore:
    answerable: bool
    refused: bool
    recall: Dict[int, bool]
    keyword_correct: Optional[bool]
    complete_citations: Optional[bool]


def score_question(reference, *, retrieved, answer, cited, refused):
    """Score an eval.jsonl record using ranked IDs, answer text and explicit refusal."""
    if not reference["answerable"]:
        return QuestionScore(False, refused, {}, None, None)

    sources = set(reference["source_articles"])
    recall = {k: not sources.isdisjoint(retrieved[:k]) for k in CUTOFFS}
    if refused:
        correct = False
    else:
        folded = answer.casefold()
        correct = all(phrase.casefold() in folded for phrase in reference["answer_keywords"])

    return QuestionScore(True, refused, recall, correct, sources.issubset(cited))


def summarize(scores: Iterable[QuestionScore]):
    """Average over answerable questions. An empty group's mean is undefined (None)."""
    answerable = []
    unanswerable_count = 0
    correct_refusals = 0
    for score in scores:
        if score.answerable:
            answerable.append(score)
        else:
            unanswerable_count += 1
            correct_refusals += score.refused

    count = len(answerable)

    def mean(values):
        return sum(values) / count if count else None

    return {
        **{f"recall@{k}": mean(s.recall[k] for s in answerable) for k in CUTOFFS},
        "keyword_correctness": mean(s.keyword_correct for s in answerable),
        "citation_coverage": mean(s.complete_citations for s in answerable),
        "correct_refusals": {"count": correct_refusals, "out_of": unanswerable_count},
        "mistaken_refusals": {"count": sum(s.refused for s in answerable), "out_of": count},
    }
