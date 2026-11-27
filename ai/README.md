# "Help-center assistant" case study: provided files

Everything here is fictional: *Velmora*, an online shop for bike accessories, does not exist. Nothing needs to be installed, and no API key or account is needed for this case study.

## What is in this folder

| Path | What it is |
|---|---|
| `kb/` | The help center: 30 short articles in Markdown (`01-...md` to `30-...md`). Each file starts with a small header: `id`, `title`, `category`, `updated` (date of the last update). |
| `eval.jsonl` | 40 evaluation questions, one JSON object per line (format below). |

## Format of `eval.jsonl`

```json
{"id": "Q01", "question": "...", "answerable": true, "expected_answer": "...",
 "answer_keywords": ["..."], "source_articles": ["KB-06"]}
```

- `answerable`: `false` when the help center contains no answer to the question. In that case `expected_answer` is `null`, `answer_keywords` is `null` and `source_articles` is empty. The right behaviour for the assistant is to say that it does not know.
- `expected_answer`: the answer a good agent would give, in plain words.
- `answer_keywords`: short phrases (lower case) that should all appear in a correct answer. This is only a cheap, rough automatic judge. It can be wrong in both directions, and you are free to improve it or to check answers by hand. If you do, say so in your note.
- `source_articles`: the article(s) that contain the answer. A question can have more than one.

## Things to know

- Pretend that today is **1 July 2026**.
- The help center was written by several people over several years, like most real ones. Do not assume it is perfectly consistent or perfectly up to date.
- The 40 questions are the only evaluation data we give you. How you use them (and what you avoid doing with them) is part of your design.
- You choose the language, the libraries and the method. A plain lexical search (TF-IDF, BM25) with an extractive answer is a perfectly acceptable assistant. If you use a model API or a local model, use your own key or setup, and tell us; we do not provide any and we do not require any.

The brief itself (what to build, what to hand in) is in the document sent with this folder.
