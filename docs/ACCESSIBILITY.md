# Accessibility assurance

Jobservatory audits the built Cloudflare Pages artifact with axe-core against WCAG 2.2 Level AA rule tags. The executable audit covers the loaded ledger and open evidence dialog at 1440×1000 and 390×844 viewports. It also verifies initial dialog focus, forward and backward focus wrapping, Escape dismissal, and focus restoration.

`npm run accessibility:audit` publishes `/api/ops/accessibility-audit.json`. The automated gate fails on any violation node, unresolved axe node, serious or critical node, or failed keyboard interaction. The artifact is schema-validated and exercised in CI.

This is not a conformance claim. Automated testing cannot replace evaluation by people who use assistive technologies. The separate assistive-technology release gate remains false until a qualified human review covers screen-reader announcements, reading order, landmarks, forms, tables, dynamic updates, the term map, evidence dialog, zoom/reflow, and keyboard-only operation on production.
