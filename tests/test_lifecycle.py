# Copyright (c) 2026 Oluwatobiloba Benjamin Ogungbangbe. All rights reserved.
# Owner: Oluwatobiloba Benjamin Ogungbangbe. Not for sale. See LICENSE.
"""Checks for the sample joiner, mover, and leaver files."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import lifecycle  # noqa: E402


class SampleWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name) / "directory.json"
        self.config = lifecycle.load_json(ROOT / "config.example.json")
        self.rules = lifecycle.load_json(ROOT / "rules" / "department-rules.json")

    def tearDown(self):
        self.tmp.cleanup()

    def engine(self):
        return lifecycle.Lifecycle(
            self.config,
            self.rules,
            self.directory,
            Path(self.tmp.name) / "logs",
            Path(self.tmp.name) / "reports",
        )

    def test_joiner_creates_four_and_rejects_unknown_department(self):
        engine = self.engine()
        results = [engine.join(row) for row in lifecycle.read_csv(ROOT / "samples" / "joiners.csv")]
        created = [item for item in results if item["status"] == "created"]
        rejected = [item for item in results if item["status"] == "rejected"]
        self.assertEqual(len(created), 4)
        self.assertEqual(rejected[0]["employee_id"], "E1005")
        self.assertTrue(any("unknown department" in error for error in rejected[0]["errors"]))

    def test_duplicate_email_is_rejected(self):
        engine = self.engine()
        first = engine.join({
            "employee_id": "E1", "first_name": "Ada", "last_name": "Okoye",
            "department": "Finance", "job_title": "Analyst", "location": "Corporate Office",
            "role": "Staff", "manager_email": "m@example.com", "start_date": "2026-10-13",
        })
        second = engine.join({
            "employee_id": "E2", "first_name": "Ada", "last_name": "Okoye",
            "department": "Sales", "job_title": "Analyst", "location": "Corporate Office",
            "role": "Staff", "manager_email": "m@example.com", "start_date": "2026-10-13",
        })
        self.assertEqual(first["status"], "created")
        self.assertEqual(second["status"], "rejected")
        self.assertTrue(any("email already exists" in error for error in second["errors"]))

    def test_mover_swaps_department_groups(self):
        engine = self.engine()
        for row in lifecycle.read_csv(ROOT / "samples" / "joiners.csv"):
            engine.join(row)
        result = engine.move(lifecycle.read_csv(ROOT / "samples" / "movers.csv")[0])
        self.assertEqual(result["status"], "moved")
        self.assertIn("SG-Finance-Users", result["groups_removed"])
        self.assertIn("SG-Infrastructure-Users", result["groups_added"])
        self.assertIn("SG-M365-Standard", engine.find(employee_id="E1001")["groups"])

    def test_leaver_disables_and_missing_person_is_not_created(self):
        engine = self.engine()
        for row in lifecycle.read_csv(ROOT / "samples" / "joiners.csv"):
            engine.join(row)
        results = [engine.leave(row) for row in lifecycle.read_csv(ROOT / "samples" / "leavers.csv")]
        self.assertEqual(results[0]["status"], "disabled")
        self.assertEqual(results[1]["status"], "not_found")
        self.assertFalse(engine.find(employee_id="E1002")["enabled"])
        self.assertEqual(engine.find(employee_id="E1002")["groups"], [])
        self.assertIsNone(engine.find(employee_id="E9999"))

    def test_disabled_account_cannot_be_moved(self):
        engine = self.engine()
        for row in lifecycle.read_csv(ROOT / "samples" / "joiners.csv"):
            engine.join(row)
        engine.leave({"employee_id": "E1001", "email": "ada.okoye@example.com", "reason": "test"})
        result = engine.move(lifecycle.read_csv(ROOT / "samples" / "movers.csv")[0])
        self.assertEqual(result["status"], "rejected")
        self.assertIn("account is disabled", result["errors"])

    def test_report_includes_groups_removed_and_added(self):
        engine = self.engine()
        for row in lifecycle.read_csv(ROOT / "samples" / "joiners.csv"):
            engine.join(row)
        engine.events = []
        engine.move(lifecycle.read_csv(ROOT / "samples" / "movers.csv")[0])
        _, report = engine.write_reports("mover")
        text = report.read_text(encoding="utf-8")
        self.assertIn("removed:", text)
        self.assertIn("added:", text)
        self.assertIn("Demo only", text)


if __name__ == "__main__":
    unittest.main()
