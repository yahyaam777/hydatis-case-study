"""Compare BM25, TF-IDF and optionally full-ranking fusion with local embeddings."""

import argparse
import json
import math
from collections import Counter
from fractions import Fraction
from pathlib import Path

from metrics import CUTOFFS, score_question
from retrieval import BM25Index, KB_DIR, tokenize


class TfidfIndex:
    def __init__(self, article_counts):
        document_frequency = Counter()
        for counts in article_counts.values():
            document_frequency.update(counts.keys())
        n = len(article_counts)
        self.idf = {term: 1 + math.log((1 + n) / (1 + df))
                    for term, df in document_frequency.items()}
        self.documents = {article_id: self.unit_vector(counts)
                          for article_id, counts in article_counts.items()}

    def unit_vector(self, counts):
        weights = {term: count * self.idf[term] for term, count in counts.items()
                   if term in self.idf}
        norm = math.sqrt(math.fsum(w * w for w in weights.values()))
        return {term: weight / norm for term, weight in weights.items()} if norm else {}

    def search(self, question, k=5):
        query = self.unit_vector(Counter(tokenize(question)))
        if not query or k <= 0:
            return []
        matches = []
        for article_id, document in self.documents.items():
            cosine = math.fsum(weight * document.get(term, 0) for term, weight in query.items())
            if cosine > 0:
                matches.append((cosine, article_id))
        matches.sort(key=lambda match: (-match[0], match[1]))
        return [article_id for _, article_id in matches[:k]]


class HybridIndex:
    def __init__(self, corpus, lexical, model_dir):
        path = Path(model_dir).expanduser().resolve()
        for name in ("config.json", "tokenizer.json", "model.safetensors"):
            if not (path / name).is_file():
                raise SystemExit(f"Missing local model file: {path / name}")
        try:
            from model2vec import StaticModel
        except ImportError as exc:
            raise SystemExit("Use the optional Model2Vec environment documented in README.md.") from exc
        self.model = StaticModel.from_pretrained(path, normalize=True)
        self.lexical = lexical
        self.articles = corpus.articles
        self.ids = sorted(self.articles)
        texts = [self.articles[i].title + "\n" + self.articles[i].body for i in self.ids]
        self.vectors = self.model.encode(texts)

    def search(self, question, k=5):
        if not question.strip() or k <= 0:
            return []
        lexical = self.lexical.search(question, k=len(self.ids))
        vector = self.model.encode([question])[0]
        semantic = []
        if vector.any():
            similarities = self.vectors @ vector
            pairs = sorted(zip(self.ids, similarities), key=lambda pair: (-pair[1], pair[0]))
            semantic = [article_id for article_id, _ in pairs]
        scores = Counter()
        for ranking in (lexical, semantic):
            for rank, article_id in enumerate(ranking, start=1):
                scores[article_id] += Fraction(1, 60 + rank)
        ordered = sorted(scores, key=lambda i: (-scores[i], i))
        return [dict(id=i, title=self.articles[i].title, updated=self.articles[i].updated,
                     score=float(scores[i])) for i in ordered[:k]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hybrid-model", metavar="DIR", help="local Model2Vec model directory")
    args = parser.parse_args()
    bm25 = BM25Index(KB_DIR)
    tfidf = TfidfIndex(bm25.term_counts)
    hybrid = HybridIndex(bm25, tfidf, args.hybrid_model) if args.hybrid_model else None
    names = ["BM25", "TF-IDF"]
    if hybrid:
        names.append("Hybrid")
    hits = {name: {k: set() for k in CUTOFFS} for name in names}
    depth = len(bm25.articles)
    total = 0
    with (KB_DIR.parent / "eval.jsonl").open(encoding="utf-8-sig") as source:
        for line in source:
            if not line.strip():
                continue
            ref = json.loads(line)
            question = ref["question"]
            rankings = {
                "BM25": [item["id"] for item in bm25.search(question, k=depth)],
                "TF-IDF": tfidf.search(question, k=depth),
            }
            if hybrid:
                rankings["Hybrid"] = [item["id"] for item in hybrid.search(question, k=depth)]
            total += ref["answerable"]
            for name, ranked in rankings.items():
                if ref["id"] == "Q05":
                    rank = ranked.index("KB-09") + 1 if "KB-09" in ranked else "unranked"
                    print(f"Q05 {name} top five: {', '.join(ranked[:5])} (KB-09 rank: {rank})")
                score = score_question(ref, retrieved=ranked, answer="", cited=[], refused=False)
                for k, found in score.recall.items():
                    if found:
                        hits[name][k].add(ref["id"])

    for k in CUTOFFS:
        original = hits["BM25"][k]
        print(f"Hydatis recall@{k}")
        for name in names:
            found = hits[name][k]
            rate = f"{len(found) / total:.2%}" if total else "N/A"
            print(f"  {name}: {len(found)}/{total} ({rate})")
            if name != "BM25":
                print(f"  {name} gained:", ", ".join(sorted(found - original)) or "none")
                print(f"  {name} lost:", ", ".join(sorted(original - found)) or "none")


if __name__ == "__main__":
    main()
