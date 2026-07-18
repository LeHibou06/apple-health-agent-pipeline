from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from app.db import connect, init_db
from app.normalizer import process_one
from app.payloads import utc_now


class PipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "health.db")
        init_db(self.db)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def enqueue(self, payload: dict) -> None:
        body = json.dumps(payload, separators=(",", ":"))
        payload_id = hashlib.sha256(body.encode()).hexdigest()
        with connect(self.db) as con:
            con.execute("INSERT INTO raw_payloads(id,received_at,body) VALUES (?,?,?)", (payload_id, utc_now(), body))
            con.commit()

    def test_metrics_sleep_and_workout(self) -> None:
        payload = {"data":{"metrics":[
            {"name":"step_count","units":"count","data":[{"date":"2026-01-01T08:00:00+00:00","qty":1000,"source":"Phone"},{"date":"2026-01-01T18:00:00+00:00","qty":2500,"source":"Watch"}]},
            {"name":"weight_body_mass","units":"kg","data":[{"date":"2026-01-01T07:00:00+00:00","qty":75.5,"source":"Scale"},{"date":"2026-01-01T20:00:00+00:00","qty":75.2,"source":"Scale"}]},
            {"name":"sleep_analysis","data":[{"startDate":"2025-12-31T23:00:00+00:00","endDate":"2026-01-01T02:00:00+00:00","value":"core"},{"startDate":"2026-01-01T02:00:00+00:00","endDate":"2026-01-01T06:00:00+00:00","value":"deep"}]}
        ],"workouts":[{"id":"w1","workoutActivityType":"outdoor_walk","start":"2026-01-01T10:00:00+00:00","end":"2026-01-01T11:00:00+00:00","duration":3600,"distance":{"qty":5.0,"unit":"km"}}]}}
        self.enqueue(payload)
        self.assertTrue(process_one(self.db))
        self.assertFalse(process_one(self.db))
        with connect(self.db) as con:
            steps = con.execute("SELECT total_value FROM daily_metrics WHERE metric='step_count'").fetchone()[0]
            weight = con.execute("SELECT last_value FROM daily_metrics WHERE metric='weight_body_mass'").fetchone()[0]
            sleep = con.execute("SELECT total_sleep_minutes FROM sleep_episodes").fetchone()[0]
            workouts = con.execute("SELECT COUNT(*) FROM workouts").fetchone()[0]
            processed = con.execute("SELECT COUNT(*) FROM processed_payloads WHERE status='ok'").fetchone()[0]
        self.assertEqual(steps, 3500)
        self.assertEqual(weight, 75.2)
        self.assertEqual(sleep, 420)
        self.assertEqual(workouts, 1)
        self.assertEqual(processed, 1)


if __name__ == "__main__":
    unittest.main()
