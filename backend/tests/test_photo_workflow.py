from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

_database_file = tempfile.NamedTemporaryFile(prefix="mealmatch-photo-test-", suffix=".db", delete=False)
_database_file.close()
os.environ["MEALMATCH_DATABASE_URL"] = f"sqlite:///{_database_file.name}"

from database import SessionLocal  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402
from models import User  # noqa: E402


class PhotoWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database = SessionLocal()
        database.add(User(id=1, name="Vision test user"))
        database.commit()
        database.close()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        try:
            os.unlink(_database_file.name)
        except OSError:
            pass

    def test_local_frontend_origin_is_allowed(self):
        response = self.client.options(
            "/upload-image",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            "http://localhost:5173",
        )

    def upload(self, passes):
        image = io.BytesIO()
        Image.new("RGB", (32, 32), "white").save(image, "PNG")
        with patch("routers.scanning.scan_pantry_photo", return_value=iter(passes)):
            response = self.client.post(
                "/upload-image",
                data={"user_id": "1"},
                files={"file": ("pantry.png", image.getvalue(), "image/png")},
                headers={"Origin": "http://localhost:5173"},
            )
        self.assertEqual(response.status_code, 200, response.text)
        return response, [json.loads(line) for line in response.text.splitlines()]

    def test_confirmed_edits_are_measured(self):
        whole_photo = {
            "pass": "whole photo",
            "pass_number": 1,
            "passes": 2,
            "detections": [
                {
                    "detection_id": "suggestion-1",
                    "ingredient": "apple",
                    "quantity": "1 piece",
                    "confidence": 0.91,
                    "source": "Qwen2.5-VL 3B",
                    "visible_text": "",
                },
            ],
            "alternatives": [],
            "done_reason": "stop",
        }
        close_up = {
            "pass": "close-up 1",
            "pass_number": 2,
            "passes": 2,
            "detections": [
                {
                    "detection_id": "suggestion-2",
                    "ingredient": "milk",
                    "quantity": "1 carton",
                    "confidence": 0.81,
                    "source": "Qwen2.5-VL 3B",
                    "visible_text": "MILK",
                },
            ],
            "alternatives": [{"detection_id": "suggestion-1", "ingredient": "green apple"}],
            "done_reason": "length",
        }
        upload, events = self.upload([whole_photo, close_up])
        self.assertEqual(
            upload.headers.get("access-control-allow-origin"),
            "http://localhost:5173",
        )
        self.assertEqual([event["type"] for event in events], ["suggestions", "suggestions", "done"])
        self.assertEqual([item["ingredient"] for item in events[1]["detections"]], ["milk"])
        self.assertEqual(events[1]["alternatives"], [{"detection_id": "suggestion-1", "ingredient": "green apple"}])
        scan_id = events[0]["scan_id"]

        confirmed = self.client.post(
            "/verify-ingredients/1",
            json={
                "scan_id": scan_id,
                "user_confidence": 4,
                "items": [
                    {
                        "detection_id": "suggestion-1",
                        "ingredient": "green apple",
                        "quantity": "1 piece",
                        "expiry_date": "2026-09-22",
                    },
                    {
                        "detection_id": "manual-1",
                        "ingredient": "banana",
                        "quantity": "2 pieces",
                        "expiry_date": "2026-09-23",
                    },
                ],
            },
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        metrics = confirmed.json()["study_metrics"]
        self.assertEqual(metrics["renames"], 1)
        self.assertEqual(metrics["deletions"], 1)
        self.assertEqual(metrics["additions"], 1)

        summary = self.client.get("/vision-study/1/summary")
        self.assertEqual(summary.status_code, 200, summary.text)
        self.assertEqual(summary.json()["confirmed_scans"], 1)
        self.assertEqual(summary.json()["average_user_confidence"], 4)
        scan = next(scan for scan in summary.json()["scans"] if scan["scan_id"] == scan_id)
        self.assertEqual(scan["initial_count"], 2)
        self.assertEqual([entry["done_reason"] for entry in scan["passes"]], ["stop", "length"])

    def test_model_failure_is_streamed_as_an_error(self):
        def failing():
            raise RuntimeError("Ollama is not running")
            yield

        _, events = self.upload(failing())
        self.assertEqual(events, [{"type": "error", "detail": "Pantry photo analysis failed: Ollama is not running"}])

    def look_closer(self, scan_id, passes):
        image = io.BytesIO()
        Image.new("RGB", (32, 32), "white").save(image, "PNG")
        with patch("routers.scanning.scan_pantry_photo", return_value=iter(passes)) as scan:
            response = self.client.post(
                f"/upload-image/{scan_id}/close-ups",
                data={"user_id": "1"},
                files={"file": ("pantry.png", image.getvalue(), "image/png")},
            )
        return response, scan

    def test_look_closer_adds_close_ups_to_the_scan(self):
        apple = {"detection_id": "suggestion-1", "ingredient": "apple", "quantity": "1 piece", "confidence": 0.91}
        _, events = self.upload([{"pass": "whole photo", "pass_number": 1, "passes": 1, "detections": [apple], "alternatives": [], "done_reason": "stop"}])
        scan_id = events[0]["scan_id"]

        close_up = {
            "pass": "close-up 1",
            "pass_number": 2,
            "passes": 5,
            "detections": [{"detection_id": "suggestion-2", "ingredient": "milk", "quantity": "1 carton", "confidence": 0.81}],
            "alternatives": [],
            "done_reason": "stop",
        }
        response, scan = self.look_closer(scan_id, [close_up])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(scan.call_args.kwargs["earlier"], [apple])
        events = [json.loads(line) for line in response.text.splitlines()]
        self.assertEqual([event["type"] for event in events], ["suggestions", "done"])
        self.assertEqual(events[-1]["total"], 2)

        again, _ = self.look_closer(scan_id, [])
        self.assertEqual(again.status_code, 409, again.text)
        summary = self.client.get("/vision-study/1/summary").json()
        recorded = next(entry for entry in summary["scans"] if entry["scan_id"] == scan_id)
        self.assertEqual(recorded["initial_count"], 2)
        self.assertTrue(recorded["looked_closer"])
        self.assertEqual([entry["requested_by_user"] for entry in recorded["passes"]], [False, True])

    def test_failed_look_closer_keeps_the_whole_photo_results(self):
        apple = {"detection_id": "suggestion-1", "ingredient": "apple", "quantity": "1 piece", "confidence": 0.91}
        _, events = self.upload([{"pass": "whole photo", "pass_number": 1, "passes": 1, "detections": [apple], "alternatives": [], "done_reason": "stop"}])

        def failing():
            raise RuntimeError("Ollama stopped")
            yield

        response, _ = self.look_closer(events[0]["scan_id"], failing())
        self.assertEqual(json.loads(response.text)["type"], "error")
        summary = self.client.get("/vision-study/1/summary").json()
        recorded = next(entry for entry in summary["scans"] if entry["scan_id"] == events[0]["scan_id"])
        self.assertEqual(recorded["status"], "awaiting_confirmation")
        self.assertEqual(recorded["initial_count"], 1)

    def test_look_closer_needs_an_open_scan(self):
        missing, _ = self.look_closer("no-such-scan", [])
        self.assertEqual(missing.status_code, 404, missing.text)


if __name__ == "__main__":
    unittest.main()
