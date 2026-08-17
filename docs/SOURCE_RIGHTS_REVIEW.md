# Source rights review protocol

The machine-readable register at `/api/governance/source-rights-register.json` is the authoritative public audit of source-use decisions. Public technical access is evidence of reachability, not a license or legal conclusion.

## Review inputs

An accountable reviewer records source-specific evidence in `config/source-rights-decisions.json`, keyed by the register `sourceId`. Each review must include:

- the employer-specific terms or licensing URL;
- reviewer identity and review date;
- separate decisions for retrieval, metadata retention, short-excerpt publication, redistribution, model training, and raw-response retention;
- concise notes explaining scope, restrictions, attribution, and any expiration or re-review condition.

The corresponding source entry in `config/sources.json` must carry matching retrieval, redistribution, and model-training states. The build reports `registryAlignment` as false and blocks release when an evidence input and source registry disagree.

Example `reviews` entry:

```json
{
  "greenhouse:example": {
    "decisions": {
      "retrieval": "approved",
      "metadataRetention": "approved",
      "shortExcerptPublication": "approved",
      "redistribution": "rejected",
      "modelTraining": "rejected",
      "rawResponseRetention": "not_requested"
    },
    "decisionEvidence": {
      "employerTermsUrl": "https://example.com/terms",
      "reviewer": "Accountable reviewer name or role",
      "reviewedAt": "2026-08-17",
      "notes": "Decision scope and restrictions."
    }
  }
}
```

`approved` is never inferred from a successful HTTP response. Full source descriptions and raw responses remain unretained, and source-content model training remains disabled, while the register is pending.
