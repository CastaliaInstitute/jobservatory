#!/usr/bin/env python3
"""Offline contract tests for ATS normalization."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collect_listings import normalize_job, structured_compensation  # noqa: E402


class SourceAdapterTests(unittest.TestCase):
    def test_greenhouse_preserves_update_semantics(self):
        result = normalize_job("greenhouse", {
            "id": 42,
            "title": "ML Engineer",
            "content": "<p>Build models.</p>",
            "location": {"name": "Remote"},
            "absolute_url": "https://example.test/jobs/42",
            "updated_at": "2026-08-17T00:00:00Z",
        })
        self.assertEqual(result["id"], "42")
        self.assertEqual(result["sourceUpdatedAt"], "2026-08-17T00:00:00Z")
        self.assertIsNone(result["sourcePublishedAt"])

    def test_lever_keeps_created_time_out_of_updated_field(self):
        result = normalize_job("lever", {
            "id": "abc",
            "text": "Research Scientist",
            "descriptionPlain": "Research models.",
            "additionalPlain": "",
            "lists": [{"text": "What you'll do", "content": "<li>Evaluate systems</li>"}],
            "categories": {"location": "London"},
            "hostedUrl": "https://example.test/jobs/abc",
            "createdAt": 1786924800000,
        })
        self.assertIsNone(result["sourceUpdatedAt"])
        self.assertEqual(result["sourcePublishedAt"], "2026-08-17T00:00:00+00:00")
        self.assertIn("Evaluate systems", result["content"])

    def test_ashby_preserves_publication_and_structured_salary(self):
        result = normalize_job("ashby", {
            "id": "ashby-1", "title": "ML Scientist", "descriptionPlain": "Train and evaluate models.",
            "location": "New York", "secondaryLocations": [{"location": "Remote — US"}],
            "jobUrl": "https://jobs.ashbyhq.com/example/ashby-1", "publishedAt": "2026-08-16T12:00:00+00:00",
            "compensation": {"summaryComponents": [{"compensationType": "Salary", "interval": "1 YEAR", "currencyCode": "USD", "minValue": 180000, "maxValue": 220000}]},
        })
        self.assertEqual(result["sourcePublishedAt"], "2026-08-16T12:00:00+00:00")
        self.assertEqual(result["location"], "New York · Remote — US")
        self.assertEqual(result["structuredCompensation"]["minimum"], 180000)
        self.assertEqual(result["structuredCompensation"]["source"], "structured-ats-field")

    def test_nonannual_structured_pay_is_not_annualized(self):
        self.assertIsNone(structured_compensation("lever", {"salaryRange": {"currency": "USD", "interval": "hour", "min": 50, "max": 75}}))


if __name__ == "__main__":
    unittest.main()
