# Failure analysis of the baseline run

## Passage filter requires every topic word to match

**Q02 — “Which payment methods can I use?”** The assistant refused even though it ranked KB-02 first. The article lists Visa, Mastercard, PayPal, SEPA bank transfer and a Velmora gift card. The title supplied “payment” and “methods,” but the filter also required “use” in the title or sentence. It skipped the list before ranking it.


**Q10 — “How fast is Express delivery and what is the order cut-off time?”** The assistant refused. KB-06 ranked fourth and gave both details in one sentence, “Express delivery arrives the next working day for orders placed before 14:00 and costs 7.90 EUR whatever the basket size.” The filter matched “Express delivery” but left five terms unmatched (`fast`, `order`, `cut`, `off`, `time`). It rejected the sentence before ranking it.

## Expected source missing from the top five

**Q05 — “My package has been stuck on the same status for a week. What should I do?”** The assistant refused. It searched KB-19, KB-18, KB-08, KB-01 and KB-20 for an answer. The expected source, KB-09, fell outside that list, so the assistant never considered its instruction: “If tracking has not moved for 7 days, or says delivered although you received nothing, contact support.”

## Shipping rule requires a geographic inference

**Q17 — “Can you deliver to Switzerland?”** KB-11 ranked first and says, “We do not ship to countries outside the European Union.” The code kept `deliver` and `switzerland` as required terms. None of the five retrieved articles mentioned Switzerland, so every passage failed the literal filter and the assistant refused.

Under the KB-only design, a direct “no” would require an additional fact: Switzerland is outside the EU. The article supplies only the shipping rule. The supplied label treats Q17 as answerable, so the run counts this as a **mistaken refusal**.

## Single-sentence answer omits an expected detail

**Q29 — “How do I delete my account?”** The assistant answered, “Go to Settings, then Privacy, then Delete my account.” It cited KB-21. The extractor returned that one sentence. The next sentence says, “The deletion is done within 30 days.”

**Manual judgment.** The answer gives the correct deletion steps and source, but omits the 30-day timeline expected by the keyword judge. Citation coverage passed and keyword correctness failed.
