"""BM25 retrieval over the Velmora help center, using only titles and bodies."""

import argparse
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


KB_DIR = Path(__file__).resolve().parent / "ai" / "kb"
K1 = 1.2  # Controls how quickly repeated occurrences of a term saturate.
B = 0.75  # Length normalization strength (0 disables it, 1 applies it fully).


def tokenize(text):
    """Case-fold and extract Unicode alphanumeric runs, keeping stopwords as-is."""
    return re.findall(r"[^\W_]+", text.casefold())


@dataclass(frozen=True)
class Article:
    id: str
    title: str
    updated: str
    body: str


def read_article(path):
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        raise ValueError(f"Missing front matter in {path}")
    end = lines.index("---", 1)
    metadata = {}
    for line in lines[1:end]:
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()

    title = metadata["title"]
    body = "\n".join(lines[end + 1:]).strip()
    first_line, _, remainder = body.partition("\n")
    if first_line.strip() == f"# {title}":
        body = remainder.strip()
    return Article(metadata["id"], title, metadata["updated"], body)


class BM25Index:
    def __init__(self, kb_dir):
        self.articles = {}
        self.term_counts = {}
        self.lengths = {}
        document_frequency = Counter()
        for path in sorted(Path(kb_dir).glob("*.md")):
            article = read_article(path)
            if article.id in self.articles:
                raise ValueError(f"Duplicate article ID {article.id} in {path}")
            tokens = tokenize(article.title + "\n" + article.body)
            counts = Counter(tokens)
            self.articles[article.id] = article
            self.term_counts[article.id] = counts
            self.lengths[article.id] = len(tokens)
            document_frequency.update(counts.keys())

        size = len(self.articles)
        self.average_length = sum(self.lengths.values()) / size if size else 0
        self.idf = {
            term: math.log1p((size - df + 0.5) / (df + 0.5))
            for term, df in document_frequency.items()
        }

    def search(self, question, k=5):
        """Sum BM25 contributions once per distinct matching query term."""
        terms = [term for term in dict.fromkeys(tokenize(question)) if term in self.idf]
        if not terms or k <= 0:
            return []

        results = []
        for article_id, counts in self.term_counts.items():
            norm = K1 * (1 - B + B * self.lengths[article_id] / self.average_length)
            score = 0.0
            for term in terms:
                frequency = counts[term]
                score += self.idf[term] * frequency * (K1 + 1) / (frequency + norm)
            if score > 0:
                article = self.articles[article_id]
                results.append(dict(id=article_id, title=article.title,
                                    updated=article.updated, score=score))
        results.sort(key=lambda hit: (-hit["score"], hit["id"]))
        return results[:k]


@lru_cache(maxsize=1)
def _default_index():
    return BM25Index(KB_DIR)


def search(question, k=5):
    """Return up to k matching articles in descending score order, ties by ID."""
    return _default_index().search(question, k)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    args = parser.parse_args()
    print(f"Loaded {len(_default_index().articles)} unique articles.")
    for hit in search(args.question):
        print(f"{hit['id']}  {hit['updated']}  {hit['score']:.4f}  {hit['title']}")
