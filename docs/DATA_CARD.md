# Jobservatory corpus data card

The machine-readable source of truth is published at `/api/data-card.json` and is deterministically rebuilt from `/api/observatory.json`. Its corpus hash ties each card to an exact export.

## Collection and unit of analysis

The unit is a job-listing observation at retrieval time. Jobservatory collects currently published listings from documented public Greenhouse, Lever, and Ashby job-board APIs. It retains metadata, content hashes, derived fields, and short evidence excerpts; it does not republish full descriptions. An append-only ledger records new or revised observations, and daily full-presence snapshots make disappearance measurable.

The registry is curated and globally mixed. Completeness means all eligible listings within every successfully retrieved configured feed—not completeness of the labor market. Employer, ATS, geography, occupation, and sector coverage therefore need to accompany every aggregate claim.

## Rights and provenance

Public unauthenticated API documentation establishes the technical access basis. It does not by itself establish permission to redistribute employer-authored text or train models. Each source remains `pending` until retrieval, retention, excerpt publication, redistribution, and model-training uses are separately reviewed. The public export remains metadata-and-short-evidence only, and source-content training is disabled while review is pending.

Official API documentation:

- [Greenhouse Job Board API](https://developers.greenhouse.io/job-board.html)
- [Lever Postings API](https://github.com/lever/postings-api)
- [Ashby Job Postings API](https://developers.ashbyhq.com/docs/public-job-posting-api)

## Labels and sensitive uses

Rule-derived classifications and O*NET mappings are unreviewed hypotheses unless a record says otherwise. Occupation-inherited O*NET profiles are contextual and are never presented as listing-stated requirements. Jobservatory is not approved for candidate screening, automated employment decisions, or protected-attribute inference.

## Known limitations

The cohort remains curated and concentrated; employer language measures stated intent rather than realized hiring or displacement; compensation disclosure is selective; and missing pay is not random. Repost and location-variant families are stable, unreviewed metadata candidates—not verified shared requisitions. Longitudinal and forecasting outputs must abstain until their stated history and evaluation gates pass.
