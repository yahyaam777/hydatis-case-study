import unittest

from metrics import score_question, summarize


ANSWERABLE = {
    "answerable": True,
    "source_articles": ["A", "B"],
    "answer_keywords": ["FREE", "bike lights"],
}
UNANSWERABLE = {"answerable": False, "source_articles": [], "answer_keywords": None}


def score(reference=ANSWERABLE, retrieved=(), answer="", cited=(), refused=False):
    return score_question(reference, retrieved=retrieved, answer=answer, cited=cited, refused=refused)


class MetricsTests(unittest.TestCase):
    def test_one_expected_source_is_a_hit_but_citations_are_incomplete(self):
        result = score(retrieved=["A"], cited=["A"], answer="Free BIKE LIGHTS.")
        self.assertTrue(result.recall[1])
        self.assertFalse(result.complete_citations)
        self.assertTrue(result.keyword_correct)

    def test_all_sources_cited_even_with_extra_citation(self):
        self.assertTrue(score(cited=["B", "C", "A"]).complete_citations)
        self.assertFalse(score(cited=["A", "A"]).complete_citations)

    def test_keywords_require_every_contiguous_phrase_ignoring_case(self):
        self.assertTrue(score(answer="Bike lights ship free.").keyword_correct)
        self.assertFalse(score(answer="Bike lights ship today.").keyword_correct)
        self.assertFalse(score(answer="Free bike helmet lights.").keyword_correct)

    def test_answerable_refusal_fails_keywords_even_if_text_matches(self):
        result = score(answer="I don't know about free bike lights.", refused=True)
        self.assertFalse(result.keyword_correct)

    def test_recall_cutoffs_and_answerable_only_averages(self):
        rankings = ["A", "XXB", "XXXXA", "XXXXXB"]
        scores = [score(retrieved=list(ids)) for ids in rankings]
        scores.append(score(UNANSWERABLE))
        summary = summarize(scores)
        self.assertEqual([summary[f"recall@{k}"] for k in (1, 3, 5)], [0.25, 0.5, 0.75])

    def test_refusal_counts_and_independent_answer_metrics(self):
        summary = summarize([
            score(cited=["A", "B"], answer="Free bike lights."),
            score(cited=["B", "A"]),
            score(refused=True),
            score(UNANSWERABLE, refused=True),
            score(UNANSWERABLE, answer="Yes."),
        ])
        self.assertEqual(summary["correct_refusals"], {"count": 1, "out_of": 2})
        self.assertEqual(summary["mistaken_refusals"], {"count": 1, "out_of": 3})
        self.assertEqual(summary["keyword_correctness"], 1 / 3)
        self.assertEqual(summary["citation_coverage"], 2 / 3)

    def test_empty_evaluation(self):
        summary = summarize([])
        for key in ("recall@1", "recall@3", "recall@5", "keyword_correctness", "citation_coverage"):
            self.assertIsNone(summary[key])
        for key in ("correct_refusals", "mistaken_refusals"):
            self.assertEqual(summary[key], {"count": 0, "out_of": 0})


if __name__ == "__main__":
    unittest.main()
