from __future__ import annotations

import unittest
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

from cursay.insights import summarize_speed, words_per_minute


class SpeedTests(unittest.TestCase):
    now = datetime(2026, 10, 12, 12, tzinfo=ZoneInfo("America/Toronto"))

    def test_shared_native_speed_contract(self) -> None:
        fixtures = json.loads((Path(__file__).parent / "fixtures/dictation_speed.json").read_text())
        for fixture in fixtures:
            with self.subTest(fixture=fixture["name"]):
                now = datetime.fromisoformat(fixture["now"]).astimezone(ZoneInfo(fixture["timezone"]))
                result = summarize_speed(fixture["rows"], fixture["days"], now)
                for key in ("wpm", "lifetime_wpm", "latest_wpm", "words", "timed_count"):
                    if fixture["expected"][key] is None:
                        self.assertIsNone(result[key])
                    else:
                        self.assertAlmostEqual(result[key], fixture["expected"][key])
                daily = {day["day"]: day["wpm"] for day in result["daily"]}
                for day, expected in fixture["expected"]["daily"].items():
                    self.assertEqual(daily[day], expected)

    @staticmethod
    def row(stamp: str, words: int, seconds: float) -> dict:
        return {"created_at": stamp, "word_count": words, "duration_seconds": seconds}

    def test_recording_speed_and_missing_time(self) -> None:
        self.assertEqual(words_per_minute(100, 30), 200)
        for words, seconds in ((100, 0), (100, -1), (0, 30), (100, float("inf")), (100, float("nan"))):
            with self.subTest(words=words, seconds=seconds):
                self.assertIsNone(words_per_minute(words, seconds))

    def test_daily_and_period_average_are_weighted_by_duration(self) -> None:
        stats = summarize_speed([
            self.row("2026-10-12T10:00:00-04:00", 100, 60),
            self.row("2026-10-12T11:00:00-04:00", 100, 20),
            self.row("2026-10-11T10:00:00-04:00", 100, 120),
        ], 14, self.now)
        self.assertEqual(stats["daily"][-1]["wpm"], 150)
        self.assertEqual(stats["wpm"], 90)
        self.assertEqual(stats["lifetime_wpm"], 90)
        self.assertEqual(stats["latest_wpm"], 300)
        self.assertEqual(stats["timed_count"], 3)
        self.assertEqual(stats["words"], 300)

    def test_missing_duration_counts_words_but_does_not_inflate_speed(self) -> None:
        stats = summarize_speed([
            self.row("2026-10-12T10:00:00-04:00", 100, 60),
            self.row("2026-10-12T11:00:00-04:00", 500, 0),
            self.row("2026-10-12T09:00:00-04:00", 0, 10),
        ], 30, self.now)
        self.assertEqual(stats["wpm"], 100)
        self.assertEqual(stats["lifetime_wpm"], 100)
        self.assertIsNone(stats["latest_wpm"])
        self.assertEqual(stats["words"], 600)
        self.assertEqual(stats["timed_count"], 1)
        self.assertEqual(stats["daily"][-1]["count"], 3)

    def test_calendar_window_includes_first_day_and_fills_gaps(self) -> None:
        rows = [
            self.row("2026-09-28T23:59:59-04:00", 100, 30),
            self.row("2026-09-29T00:00:00-04:00", 100, 60),
            self.row("2026-10-13T00:00:00-04:00", 100, 30),
        ]
        stats = summarize_speed(rows, 14, self.now)
        self.assertEqual(len(stats["daily"]), 14)
        self.assertEqual(stats["daily"][0]["day"], "2026-09-29")
        self.assertEqual(stats["daily"][-1]["day"], "2026-10-12")
        self.assertEqual(stats["wpm"], 100)
        self.assertEqual(stats["words"], 100)
        self.assertIsNone(stats["daily"][-1]["wpm"])
        self.assertAlmostEqual(stats["lifetime_wpm"], 150)
        self.assertEqual(summarize_speed(rows, 30, self.now)["words"], 200)

    def test_utc_timestamps_are_grouped_by_local_day(self) -> None:
        stats = summarize_speed([
            self.row("2026-10-12T02:30:00+00:00", 90, 60),
            self.row("2026-10-12T04:30:00+00:00", 120, 60),
        ], 14, self.now)
        self.assertEqual(stats["daily"][-2]["wpm"], 90)
        self.assertEqual(stats["daily"][-1]["wpm"], 120)

    def test_calendar_days_across_daylight_saving_time(self) -> None:
        now = datetime(2026, 11, 3, 12, tzinfo=ZoneInfo("America/Toronto"))
        stats = summarize_speed([
            self.row("2026-10-31T04:30:00+00:00", 90, 60),
            self.row("2026-11-02T04:30:00+00:00", 120, 60),
        ], 14, now)
        by_day = {row["day"]: row for row in stats["daily"]}
        self.assertEqual(by_day["2026-10-31"]["wpm"], 90)
        self.assertEqual(by_day["2026-11-01"]["wpm"], 120)

    def test_empty_history_has_no_invented_speed(self) -> None:
        stats = summarize_speed([], 90, self.now)
        self.assertIsNone(stats["wpm"])
        self.assertIsNone(stats["lifetime_wpm"])
        self.assertIsNone(stats["latest_wpm"])
        self.assertEqual(stats["words"], 0)
        self.assertEqual(len(stats["daily"]), 90)
        self.assertTrue(all(row["wpm"] is None for row in stats["daily"]))

    def test_invalid_timestamp_does_not_break_insights(self) -> None:
        stats = summarize_speed([self.row("invalid", 100, 60)], 30, self.now)
        self.assertEqual(stats["lifetime_wpm"], 100)
        self.assertIsNone(stats["wpm"])

    def test_naive_legacy_timestamp_is_treated_as_utc(self) -> None:
        now = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)
        stats = summarize_speed([self.row("2026-10-12T10:00:00", 100, 60)], 14, now)
        self.assertEqual(stats["wpm"], 100)


if __name__ == "__main__":
    unittest.main()
