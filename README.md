# Velmora help-center assistant

The assistant takes an English question, searches 30 help-center articles and returns one sentence with its source. When no passage qualifies, it displays “I don't know based on the help center.”

## Run from the project root

Use Python 3.7 or later for the default BM25 assistant and evaluation (tested with 3.10.6). Both run locally with the Python standard library. The optional hybrid experiment has its own environment.

Ask a question:

```sh
python assistant.py "How much does Express delivery cost?"
```

Run the full evaluation:

```sh
python -B evaluate_assistant.py
```

The evaluator passes only the question text to the assistant and uses the labels for scoring. It prints the totals and writes [assistant_results.jsonl](assistant_results.jsonl) in the project root, replacing it on each run. Each row records the question, retrieved IDs and scores, answer, citations, refusal, expected sources, missing phrases and metric outcomes. The only data inputs required are `ai/kb/` and `ai/eval.jsonl`. If `retrieval_results.jsonl` is present, the evaluator also checks each question’s recall against that saved baseline.

Run the seven handmade metric tests:

```sh
python -B -m unittest discover
```

## How a passage qualifies

1. BM25 searches titles and bodies using case-folded alphanumeric tokens, with `k1=1.2` and `b=0.75`. Each title is indexed once. The five highest-scoring matches supply the candidate sentences, with article ID breaking retrieval ties.
2. The assistant removes recognized duration and price request phrases and stopwords to form a set of distinct topic words. For duration requests it also drops “take,” “takes,” “last” and “lasts.” A sentence and its article title must together match at least `floor(number of topic words / 2) + 1` distinct topic words. Matching is literal after tokenization.
3. The sentence itself must match a topic word or supply recognized detail evidence. Every recognized detail request requires its own evidence in the sentence: a euro amount or “free” for price, and a duration expression such as “24 months” or “next working day” for duration. For “How long is a gift card valid?”, the title “Gift cards” supplies “gift” and the sentence supplies “valid” and “24 months.” Two of three topic words qualify the sentence.
4. Among qualifying sentences, the largest number of directly matched topic words wins. Ties go to the newer article by its `updated` date, then the lower article ID, then the earlier sentence in that article. Both old and new articles are searchable. Dates affect only passage ties. The assistant has no conflict detector and presents a single extract even when another article gives a different answer.

## Evaluation on the supplied 40 questions

| Metric | Baseline | Revised |
|---|---:|---:|
| Hydatis recall@1 | 26/35 | 26/35 |
| Hydatis recall@3 | 31/35 | 31/35 |
| Hydatis recall@5 | 32/35 | 32/35 |
| Keyword success | 8/35 | 15/35 |
| Complete citation coverage | 11/35 | 22/35 |
| Both checks | 8/35 | 15/35 |
| Correct refusals on unanswerable questions | 5/5 | 5/5 |
| Mistaken refusals on answerable questions | 22/35 | 11/35 |

- **Hydatis recall@k** is the fraction of answerable questions with at least one expected article among the first *k* retrieved IDs. A question with two expected sources earns a hit if either appears.
- **Keyword success** is a proxy for answer correctness. Every expected phrase must appear as a contiguous substring of the answer, ignoring case. A refusal scores zero. All 35 answerable questions count toward the denominator.
- **Complete citation coverage** is the fraction of answerable questions for which the cited IDs include every expected source. The assistant cites at most one article, so it cannot pass this check on questions with multiple expected sources.
- **Both checks** counts answerable questions passing keyword success and complete citation coverage on the same response.

Inspection of the 40 evaluation questions and the baseline failures informed the change from requiring every topic word to requiring a strict majority. The table measures the change on those same questions. The 5/5 correct refusals are based on only five unanswerable examples. See the [baseline failure analysis](FAILURES.md) and [saved baseline rows](assistant_results_baseline.jsonl).

## Optional offline retrieval comparison

Run from the project root:

```sh
python -B compare_retrieval.py
```

Both methods use the same title and body token counts from the 30 KB articles. TF-IDF weights each term by its count times `1 + ln((1 + article count) / (1 + document frequency))`. It ranks by cosine similarity, breaks ties by ascending article ID and returns an empty list for an all-zero query. The vocabulary and document frequencies come solely from the KB. Both retrievers receive the same 40 question texts. Neither method was tuned on these questions for this comparison. BM25 remains the assistant default.

| Hydatis recall | BM25 | TF-IDF cosine | TF-IDF gained | TF-IDF lost |
|---|---:|---:|---|---|
| @1 | 26/35 (74.29%) | 27/35 (77.14%) | Q01, Q08 | Q23 |
| @3 | 31/35 (88.57%) | 31/35 (88.57%) | None | None |
| @5 | 32/35 (91.43%) | 32/35 (91.43%) | None | None |

TF-IDF put an expected source first for one additional question overall. At ranks three and five, the two methods hit exactly the same questions. For Q05, BM25 returned `KB-19, KB-18, KB-08, KB-01, KB-20` and TF-IDF returned `KB-19, KB-18, KB-08, KB-01, KB-03`. Both missed the expected article, KB-09.

### Optional local sentence embeddings and reciprocal rank fusion

The model is `minishlab/potion-base-2M`, revision `389b9f64be5aa4ae7a6bc6fe95ef20ce485ae5da`, with Model2Vec 0.6.0. This is a pretrained English static sentence encoder. The one-time setup below uses Python 3.10 on Windows and places the runtime and all three model files (8,243,122 bytes total) outside the submission folder. [Pinned model](https://huggingface.co/minishlab/potion-base-2M/tree/389b9f64be5aa4ae7a6bc6fe95ef20ce485ae5da)

```powershell
$experiment = Join-Path $env:LOCALAPPDATA "HydatisExperiments"
$venv = Join-Path $experiment "potion-env"
$model = Join-Path $experiment "potion-base-2M-389b9f6"
$python = Join-Path $venv "Scripts\python.exe"
python -m venv --system-site-packages $venv
& $python -m pip install model2vec==0.6.0
New-Item -ItemType Directory -Force -Path $model | Out-Null
$url = "https://huggingface.co/minishlab/potion-base-2M/resolve/389b9f64be5aa4ae7a6bc6fe95ef20ce485ae5da"
foreach ($file in "config.json", "tokenizer.json", "model.safetensors") {
    Invoke-WebRequest -UseBasicParsing "$url/$file" -OutFile (Join-Path $model $file)
}
```

Run the retrieval comparison offline from the project root:

```powershell
$env:HF_HUB_OFFLINE = "1"
& $python -B compare_retrieval.py --hybrid-model $model
```

Each article gets one normalized embedding of its title and body. The question uses the same encoder. The semantic ranking orders all 30 articles by cosine similarity. The lexical ranking includes every positive TF-IDF match. For each list where an article appears, it earns `1 / (60 + rank)`, starting at rank 1. An article with zero lexical similarity gets zero lexical contribution and remains eligible on its semantic rank. A zero query embedding contributes no semantic ranks. Component and fused ties use ascending article ID. The scores are summed before taking the top five.

**Measured retrieval only**, on the same 35 answerable questions. The model and fusion rule were fixed before scoring; neither was tuned on the evaluation questions.

| Method | Recall@1 | Recall@3 | Recall@5 | Gained at 5 vs BM25 | Lost at 5 vs BM25 | Q05 rank of KB-09 |
|---|---:|---:|---:|---|---|---:|
| BM25 | 26/35 (74.29%) | 31/35 (88.57%) | 32/35 (91.43%) | — | — | 9 |
| TF-IDF | 27/35 (77.14%) | 31/35 (88.57%) | 32/35 (91.43%) | None | None | 6 |
| TF-IDF + embeddings (RRF) | 28/35 (80.00%) | 31/35 (88.57%) | 31/35 (88.57%) | None | Q04 | 6 |

The hybrid gained two first-place hits overall and lost one top-five hit relative to BM25. All three methods missed KB-09 in Q05's top five. The assistant answer metrics above are for BM25. To explicitly select the hybrid for an answer or a separate assistant evaluation, use:

```powershell
& $python -B assistant.py "How much does Express delivery cost?" --hybrid-model $model
& $python -B evaluate_assistant.py --hybrid-model $model
```

The optional evaluation writes `assistant_results_hybrid.jsonl`. The default evaluation writes `assistant_results.jsonl`.

## Two revised answers with the expected citation

- **Q33, shipping an e-bike battery by Express.** The answer cites KB-24 and discusses shipping inside France and using the original box for a return. The relevant sentence in that same article says “Express delivery is not available for batteries.” The selected sentence leaves the Express question open.
- **Q37, customer support opening hours.** The answer cites KB-27 and says “We answer emails within 24 hours on working days.” The question asks when support is available. Another sentence in KB-27 gives the schedule as Monday to Friday, 9:00 to 18:00 CET.
