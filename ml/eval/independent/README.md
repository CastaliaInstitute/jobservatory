# Independent temporal evaluation

This directory contains unlabeled, blind annotation packages. It does **not**
contain independent judgments yet. Running `python3 ml/independent_evaluation.py
--write` deterministically rebuilds the packages and the public readiness
manifest from the frozen corpus.

Two people independently complete the reviewer packages without consulting one
another or model output. Each submission must name a distinct reviewer, affirm
independence, preserve every task ID, and use the scales below. A third person
then adjudicates every disagreement. Copy the templates in `templates/` into
`submissions/`; submission files are deliberately absent until real reviewers
provide them.

Reviewers can use the local-first workbench at
`https://jobservatory.castalia.institute/annotation.html`. It loads the exact
hashed packages published with the build, stores drafts only in browser local
storage, and downloads the completed submission JSON. It has no submission API
and does not transmit reviewer judgments to Jobservatory.

After all submissions validate and the agreement thresholds pass, run
`python3 ml/independent_evaluation.py --write --finalize`. Finalization refuses
to write gold labels while any blocker remains; when ready it materializes
content-addressed-lineage retrieval qrels and classification gold records under
`ml/eval/independent/gold/`.

Retrieval labels use `0` (irrelevant), `1` (related), `2` (strongly relevant
with one important miss), or `3` (directly satisfies the intent and material
constraints). Classification labels are selected only when the supplied text
supports them. Use `insufficientEvidence: true` when the evidence-only record
cannot support a defensible judgment.

The holdout uses only `sourcePublishedAt`, never collection time. Records with
unknown publication time are excluded, and every posting family appearing on
both sides of the cutoff is quarantined from the holdout. This is a strict
source-publication split from one corpus snapshot; it is not falsely described
as a longitudinal observation-history test. Classification sampling and each
per-query retrieval pool also permit at most one record per posting family, so
location variants do not inflate effective sample size.

The package omits employer, source, URL, existing rule labels, weak targets,
retrieval scores, and rank provenance. Model-development code must not read
completed submissions. Promotion evaluation is a separate, one-shot process
after the candidate and thresholds are frozen.
