"""Measure the current assistant, optionally checking historical retrieval results."""

import argparse
import json
from pathlib import Path

from assistant import answer_question, get_index
from metrics import CUTOFFS, score_question


ROOT = Path(__file__).resolve().parent


def read_rows(path):
    with path.open(encoding="utf-8-sig") as source:
        return [json.loads(line) for line in source if line.strip()]


def evaluate(reference, index=None):
    if index is None:
        index = get_index()
    question = reference["question"]
    response = answer_question(question, index=index)
    # The assistant returns only its answer and citations. Replay its deterministic
    # top-five search to record the ranking without changing the assistant.
    ranking = index.search(question, k=5)
    ids = [hit["id"] for hit in ranking]
    answer = response["answer"]
    citations = response["citations"]
    score = score_question(reference, retrieved=ids, answer=answer,
                           cited=citations, refused=answer is None)
    folded = (answer or "").casefold()
    missing = None
    if score.answerable:
        missing = [word for word in reference["answer_keywords"] if word.casefold() not in folded]

    return {
        "id": reference["id"],
        "question": question,
        "ranked_article_ids": ids,
        "retrieval_scores": [hit["score"] for hit in ranking],
        "answer": answer,
        "citations": citations,
        "refused": score.refused,
        "answerable": score.answerable,
        "expected_source_ids": reference["source_articles"],
        "missing_keywords": missing,
        "scores": {
            **{f"recall@{k}": score.recall.get(k) for k in CUTOFFS},
            "keyword_success": score.keyword_correct,
            "complete_citations": score.complete_citations,
            "both_checks": score.keyword_correct and score.complete_citations,
        },
    }


def verify(rows, baseline=None):
    ids = {row["id"] for row in rows}
    if len(rows) != 40 or len(ids) != 40:
        raise ValueError("Expected 40 distinct evaluation question IDs")
    if baseline is None:
        return
    saved = {row["id"]: row for row in baseline}
    if len(baseline) != 40 or ids != saved.keys():
        raise ValueError("Expected the same 40 distinct question IDs in both runs")
    for row in rows:
        previous = saved[row["id"]]
        for k in CUTOFFS:
            if row["scores"][f"recall@{k}"] != previous["hits"][f"hit@{k}"]:
                raise ValueError(f"Baseline recall@{k} mismatch for {row['id']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hybrid-model", metavar="DIR", help="local Model2Vec model directory")
    args = parser.parse_args()
    index = get_index(args.hybrid_model)
    rows = [evaluate(ref, index) for ref in read_rows(ROOT / "ai" / "eval.jsonl")]
    baseline_path = ROOT / "retrieval_results.jsonl"
    baseline = read_rows(baseline_path) if not args.hybrid_model and baseline_path.exists() else None
    verify(rows, baseline)
    output = ROOT / ("assistant_results_hybrid.jsonl" if args.hybrid_model else "assistant_results.jsonl")
    with output.open("w", encoding="utf-8", newline="\n") as target:
        for row in rows:
            target.write(json.dumps(row, ensure_ascii=False) + "\n")

    answerable = [row for row in rows if row["answerable"]]
    unanswerable = [row for row in rows if not row["answerable"]]
    checks = [(f"recall@{k}", f"Hydatis recall@{k}") for k in CUTOFFS]
    checks.extend([
        ("keyword_success", "Keyword success (proxy for answer correctness)"),
        ("complete_citations", "Complete citation coverage"),
        ("both_checks", "Both keyword and citation checks"),
    ])
    for key, label in checks:
        print(f"{label}: {sum(row['scores'][key] for row in answerable)}/{len(answerable)}")
    print(f"Correct refusals: {sum(row['refused'] for row in unanswerable)}/{len(unanswerable)}")
    print(f"Mistaken refusals: {sum(row['refused'] for row in answerable)}/{len(answerable)}")
    print("Verified 40 unique question IDs.")
    if baseline is not None:
        print("Per-question recall matches the saved retrieval baseline.")
    print(f"Wrote {len(rows)} rows to {output.name}")


if __name__ == "__main__":
    main()
