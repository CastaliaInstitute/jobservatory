# Responsible AI and release controls

Jobservatory is a research observatory, not an employment decision system. Candidate matching is disabled, protected-attribute features are prohibited, and no output may be used to screen, rank, or reject people. Any future candidate-facing explanation must cite exact candidate and listing passages and remain subject to human review.

## Fail-closed release policy

The machine-readable release ledger at `/api/ml/release-readiness.json` reports `a_plus_ready` only when every evidence gate passes. Manual assurance claims live in `config/assurance.json` and default to false. Missing evidence is a failure, not an omitted metric.

The gates cover source rights, O*NET mapping review, independent annotation and adjudication, model promotion, protected-attribute counterfactual testing, longitudinal validity, versioned serving, production benchmarking, accessibility, and automatic deployment. The serialized classifier now passes a scoped explicit-phrase counterfactual audit with a positive sensitivity control; the artifact and its limitations are public at `/api/ml/counterfactual-audit.json`.

## Current boundaries

- Source training and redistribution rights are not yet approved for every source.
- Labels used by the classifier are weak labels, not adjudicated gold labels.
- The counterfactual audit does not measure disparate impact or location-proxy effects and is not a fairness certification.
- The retrieval development set has one reviewer and is not promotion evidence.
- Forecasting abstains until sufficient longitudinal history exists.
- Production currently serves static research artifacts; it does not run a low-latency online model service.
- The live delivery benchmark measures one client and uncontrolled CDN cache state, not global model-serving latency.

These boundaries must remain visible in data cards, model cards, UI copy, and downstream Apocalypso integrations.
