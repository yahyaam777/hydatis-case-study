"""Evaluate the unchanged BM25 baseline against ai/eval.jsonl."""

import json
from pathlib import Path

from metrics import CUTOFFS, score_question
from retrieval import search


ROOT = Path(__file__).resolve().parent


def evaluate_question(reference):
    ranked = search(reference["question"], k=5)
    ids = [article["id"] for article in ranked]
    # Only the recall component of the shared scorer is used in this baseline.
    score = score_question(reference, retrieved=ids, answer="", cited=[], refused=False)
    return {
        "id": reference["id"],
        "question": reference["question"],
        "answerable": reference["answerable"],
        "expected_source_ids": reference["source_articles"],
        "ranked_article_ids": ids,
        "scores": [article["score"] for article in ranked],
        "hits": {f"hit@{k}": score.recall.get(k) for k in CUTOFFS},
    }


def main():
    with (ROOT / "ai" / "eval.jsonl").open(encoding="utf-8-sig") as source:
        rows = [evaluate_question(json.loads(line)) for line in source if line.strip()]

    output = ROOT / "retrieval_results.jsonl"
    with output.open("w", encoding="utf-8", newline="\n") as target:
        for row in rows:
            target.write(json.dumps(row, ensure_ascii=False) + "\n")

    answerable = [row for row in rows if row["answerable"]]
    total = len(answerable)
    for k in CUTOFFS:
        hits = sum(row["hits"][f"hit@{k}"] for row in answerable)
        rate = f"{hits / total:.2%}" if total else "N/A"
        print(f"recall@{k}: {hits}/{total} ({rate})")
    print(f"Wrote {len(rows)} rows to {output.name}")


if __name__ == "__main__":
    main()
