# Retrieval relevance annotation

Jobservatory separates model development from model promotion. The committed
queries are a small, single-reviewer development set. They may be used to debug
and compare candidates, but never to authorize production promotion.

## Relevance scale

- `3` — directly satisfies the intent, role family, and important constraints.
- `2` — strongly relevant but misses or ambiguously satisfies one constraint.
- `1` — topically related and plausibly useful, but does not satisfy the intent.
- `0` — not relevant. Zeroes should be retained in raw annotation exports even
  though compact qrels may omit them.

Annotators judge only the frozen observation text and metadata. They must not use
employer prestige, source rank, or facts obtained from the live listing.

## Promotion split contract

A promotion-grade test set must:

1. reference a content-addressed, immutable corpus snapshot;
2. be created after candidate and baseline choices are frozen;
3. contain realistic query strata declared before scoring;
4. have at least two independent judgments per query-document pair;
5. preserve annotator-level raw labels and an adjudicated final label;
6. report agreement and unresolved disagreements;
7. remain unread by model-tuning code until the promotion run; and
8. include time-based separation from the development corpus.

Until every condition is machine-verifiable, reports must set
`eligibleForPromotionDecision` to `false`.

The operational protocol, two shuffled blind packages per task, submission
templates, temporal-family leakage audit, agreement computation, and
adjudication coverage gate live in `ml/eval/independent/`. The public readiness
record is `/api/ml/independent-evaluation-readiness.json`. Package existence is
not evidence of independent review: the gate remains closed until two distinct
reviewers and a distinct adjudicator supply complete, valid submissions.
The accessible `/annotation.html` workbench makes those packages operable while
keeping judgments local until the reviewer explicitly downloads a submission.
