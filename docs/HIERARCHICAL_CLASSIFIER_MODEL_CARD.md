# Hierarchical classifier candidate model card

Status: **research candidate; rejected for promotion**

The candidate predicts leaf labels in five families—skills, system layers, AI
relationships, domains, and seniority—and deterministically emits a family
parent when any child is positive. Per-label class-weighted logistic regressions
use title and location TF-IDF features. Employer names and rule-selected evidence
are excluded to reduce source memorization and direct weak-label leakage.

Each leaf model is Platt-calibrated on a separate development partition. A
per-label threshold is selected on that partition, and predictions inside a
0.05 band around the threshold abstain. The compressed JSON artifact contains
the vocabulary, IDF values, coefficients, calibrators, thresholds, hierarchy
rule, and abstention margin. Its manifest records hashes for both the model and
the content-addressed 1,709-observation training snapshot.

## Development results

- Micro precision: 0.6913
- Micro recall: 0.6462
- Micro F1: 0.6680
- Macro F1: 0.3705
- Tail-label macro F1: 0.1833
- Brier score: 0.0637
- Expected calibration error: 0.0111
- Decision coverage: 0.9536
- Parent consistency: 1.0

These metrics measure agreement with versioned rule-generated weak labels. They
do not measure semantic ground truth. The source-time ordering uses timestamps
from a single retrieval snapshot and is not a longitudinal temporal holdout.

## Promotion decision

The candidate is ineligible because:

1. targets are weak labels, not independently annotated and adjudicated labels;
2. no genuine longitudinal temporal test set exists; and
3. source-content model-training rights remain pending.

Calibration against weak labels does not establish calibrated real-world
probabilities. The candidate must not be used for employment or candidate
decisions. It exists to make hierarchy, calibration, abstention, artifact
lineage, and tail-label failure measurable before gold data is available.
