"""Extract one help-center sentence or refuse when the topic or detail is missing."""

import argparse
import re
from datetime import date
from functools import lru_cache

from retrieval import BM25Index, KB_DIR, tokenize


REFUSAL = "I don't know based on the help center."
STOPWORDS = set("""
    a an the i me my we our you your it its is are am was were be been do does
    did have has had can could will would should what which who where when why
    how if for of on in at by from to with and or as that this about please
""".split())

# Remove the request for a detail from the topic, and require evidence of it
# in the sentence itself. A deadline such as "before 14:00" is not a duration.
DURATION_REQUEST = re.compile(
    r"\b(?:how (?:long|much time|many (?:minutes|hours|days|weeks|months|years))"
    r"|duration)\b"
)
DURATION_EVIDENCE = re.compile(
    r"\b(?:\d+|one|two|a|an|next|same)[ -]+(?:(?:working|business) )?"
    r"(?:minutes?|hours?|days?|weeks?|months?|years?)\b", re.I
)
PRICE_REQUEST = re.compile(r"\b(?:how much|costs?|prices?|fees?|free)\b")
PRICE_EVIDENCE = re.compile(r"\b(?:\d+(?:[.,]\d+)?\s*(?:EUR|euros?)|free)\b", re.I)


@lru_cache(maxsize=1)
def get_index(hybrid_model=None):
    corpus = BM25Index(KB_DIR)
    if hybrid_model is None:
        return corpus
    from compare_retrieval import HybridIndex, TfidfIndex
    return HybridIndex(corpus, TfidfIndex(corpus.term_counts), hybrid_model)


def topic_terms(text):
    return set(tokenize(text)) - STOPWORDS


def answer_question(question, *, index=None):
    if index is None:
        index = get_index()
    hits = index.search(question, k=5)
    topic = question.casefold()
    evidence = []
    for request, marker in ((DURATION_REQUEST, DURATION_EVIDENCE), (PRICE_REQUEST, PRICE_EVIDENCE)):
        if request.search(topic):
            evidence.append(marker)
            topic = request.sub(" ", topic)
    terms = topic_terms(topic)
    if DURATION_EVIDENCE in evidence:
        terms -= {"take", "takes", "last", "lasts"}
    # Require a strict majority of the distinct topic words.
    required_matches = len(terms) // 2 + 1

    candidates = []
    for hit in hits:
        article = index.articles[hit["id"]]
        title = topic_terms(article.title)
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", article.body):
            direct = terms & topic_terms(sentence)
            # Title words provide context, but the sentence must still contribute
            # a topic match or the requested price/duration evidence below.
            if len(terms & (direct | title)) < required_matches or not (direct or evidence):
                continue
            if not all(marker.search(sentence) for marker in evidence):
                continue
            candidates.append((
                -len(direct), -date.fromisoformat(article.updated).toordinal(),
                article.id, sentence,
            ))

    if not candidates:
        return {"answer": None, "citations": []}
    # min is stable, so tied sentences in one article keep their reading order.
    _, _, article_id, sentence = min(candidates, key=lambda item: item[:3])
    return {"answer": sentence, "citations": [article_id]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--hybrid-model", metavar="DIR", help="local Model2Vec model directory")
    args = parser.parse_args()
    result = answer_question(args.question, index=get_index(args.hybrid_model))
    print(result["answer"] or REFUSAL)
    if result["citations"]:
        print("Source:", result["citations"][0])
