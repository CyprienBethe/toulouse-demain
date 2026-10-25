"""The future feed is required on pull requests: no green tick when it fails.

Run: python -m unittest discover -s scripts/tests -v
"""

from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("write_report", ROOT / "scripts" / "write_report.py")
wr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wr)

STEPS = ["download", "zone", "osm", "sncf", "futur", "build", "serve", "trips"]


def outcomes(**changes):
    return {step: changes.get(step, "success") for step in STEPS}


class ReportStatusTest(unittest.TestCase):
    def test_partial_success_only_where_the_future_feed_is_optional(self):
        success, futur_ok, status = wr.report_status(outcomes(futur="failure"), [], futur_required=False)
        self.assertEqual((success, futur_ok), (True, False))
        self.assertTrue(status.startswith("SUCCÈS PARTIEL"))

    def test_pull_request_fails_without_the_future_feed(self):
        success, futur_ok, status = wr.report_status(outcomes(futur="failure"), [], futur_required=True)
        self.assertEqual((success, futur_ok), (False, False))
        self.assertTrue(status.startswith("ÉCHEC"))

    def test_other_cases(self):
        self.assertEqual(wr.report_status(outcomes(), [], True), (True, True, "SUCCÈS"))
        self.assertEqual(wr.report_status(outcomes(), ["w"], True)[2], "SUCCÈS AVEC AVERTISSEMENTS")
        self.assertEqual(wr.report_status(outcomes(build="failure"), [], False)[:2], (False, True))


class WorkflowTest(unittest.TestCase):
    """.github/workflows/build-graph.yml: the rule is wired in the workflow (text checks, no YAML parser)."""

    workflow = (ROOT / ".github" / "workflows" / "build-graph.yml").read_text(encoding="utf-8")

    def test_future_feed_required_except_on_default_branch_and_schedule(self):
        self.assertRegex(self.workflow, re.escape(
            "FUTUR_REQUIRED: ${{ github.event_name != 'schedule' && "
            "github.ref_name != github.event.repository.default_branch }}"))

    def test_last_step_fails_the_run(self):
        last = self.workflow.rstrip().split("\n      - name: ")[-1]
        self.assertIn("steps.futur.outcome == 'failure' && env.FUTUR_REQUIRED == 'true'", last)
        self.assertIn("always()", last)
        self.assertTrue(last.rstrip().endswith("exit 1"))

    def test_report_knows_the_rule(self):
        self.assertIn('if [[ "$FUTUR_REQUIRED" == "true" ]]; then required=(--futur-required); fi', self.workflow)

    def test_future_step_still_tolerated_so_that_the_report_is_written(self):
        step = self.workflow.split("- name: Construire le GTFS futur")[1].split("\n      - name: ")[0]
        self.assertIn("continue-on-error: true", step)
        self.assertIn("--sncf-gtfs build/otp/gtfs/sncf.gtfs.zip", step)


if __name__ == "__main__":
    unittest.main()
