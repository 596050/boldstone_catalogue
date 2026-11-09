import csv
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from utils.ibkr.download_historical import _configure_ib_request_timeout, _ensure_event_loop_for_ib_insync_import, existing_csv_freshness


class DownloadHistoricalTests(unittest.TestCase):
    def test_ensure_event_loop_for_ib_insync_import_is_idempotent(self) -> None:
        _ensure_event_loop_for_ib_insync_import()
        _ensure_event_loop_for_ib_insync_import()

    def _write_csv(self, path: Path, dates: list[str]) -> None:
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "symbol",
                    "con_id",
                    "exchange",
                    "primary_exchange",
                    "currency",
                    "date",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "average",
                    "bar_count",
                ],
            )
            writer.writeheader()
            for date in dates:
                writer.writerow(
                    {
                        "symbol": "AAPL",
                        "con_id": "",
                        "exchange": "SMART",
                        "primary_exchange": "NASDAQ",
                        "currency": "USD",
                        "date": date,
                        "open": 100,
                        "high": 101,
                        "low": 99,
                        "close": 100,
                        "volume": 1_000,
                        "average": 100,
                        "bar_count": 10,
                    }
                )

    def test_existing_csv_older_than_one_day_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "AAPL.csv"
            self._write_csv(path, ["2026-06-18T12:03:00-04:00"])

            freshness = existing_csv_freshness(
                path,
                stale_after_hours=24.0,
                now=datetime(2026, 6, 20, 16, 4, tzinfo=timezone.utc),
            )

        self.assertTrue(freshness["stale"])
        self.assertEqual(freshness["basis"], "latest_bar")
        self.assertGreater(freshness["age_hours"], 24.0)

    def test_existing_csv_older_than_one_day_is_stale_even_with_larger_requested_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "AAPL.csv"
            self._write_csv(path, ["2026-06-19T12:03:00-04:00"])

            freshness = existing_csv_freshness(
                path,
                stale_after_hours=72.0,
                now=datetime(2026, 6, 20, 16, 4, tzinfo=timezone.utc),
            )

        self.assertTrue(freshness["stale"])
        self.assertEqual(freshness["stale_after_hours"], 24.0)
        self.assertGreater(freshness["age_hours"], 24.0)

    def test_existing_csv_within_one_day_is_fresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "AAPL.csv"
            self._write_csv(path, ["2026-06-20T12:03:00-04:00"])

            freshness = existing_csv_freshness(
                path,
                stale_after_hours=24.0,
                now=datetime(2026, 6, 20, 16, 4, tzinfo=timezone.utc),
            )

        self.assertFalse(freshness["stale"])
        self.assertLess(freshness["age_hours"], 24.0)

    def test_date_only_daily_bar_is_fresh_until_next_day_ages_out(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "AAPL.csv"
            self._write_csv(path, ["2026-06-25"])

            freshness = existing_csv_freshness(
                path,
                stale_after_hours=24.0,
                now=datetime(2026, 6, 26, 16, 4, tzinfo=timezone.utc),
            )

        self.assertFalse(freshness["stale"])
        self.assertLess(freshness["age_hours"], 24.0)

    def test_existing_csv_uses_downloaded_at_when_no_bar_date_column(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "earnings.csv"
            with path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["symbol", "downloaded_at_utc"])
                writer.writeheader()
                writer.writerow(
                    {
                        "symbol": "AAPL",
                        "downloaded_at_utc": "2026-06-20T15:30:00+00:00",
                    }
                )

            freshness = existing_csv_freshness(
                path,
                stale_after_hours=24.0,
                now=datetime(2026, 6, 20, 16, 4, tzinfo=timezone.utc),
            )

        self.assertFalse(freshness["stale"])
        self.assertEqual(freshness["basis"], "latest_bar")

    def test_existing_csv_can_prefer_cache_mtime_for_command_caches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fred.csv"
            self._write_csv(path, ["2026-01-01"])
            mtime = datetime(2026, 6, 20, 15, 30, tzinfo=timezone.utc).timestamp()
            os.utime(path, (mtime, mtime))

            freshness = existing_csv_freshness(
                path,
                stale_after_hours=24.0,
                now=datetime(2026, 6, 20, 16, 4, tzinfo=timezone.utc),
                prefer_cache_time=True,
            )

        self.assertFalse(freshness["stale"])
        self.assertEqual(freshness["basis"], "file_mtime")

    def test_existing_csv_prefers_explicit_cache_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshot.csv"
            with path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["date", "downloaded_at_utc"])
                writer.writeheader()
                writer.writerow(
                    {
                        "date": "2026-01-01",
                        "downloaded_at_utc": "2026-06-20T15:30:00+00:00",
                    }
                )

            freshness = existing_csv_freshness(
                path,
                stale_after_hours=24.0,
                now=datetime(2026, 6, 20, 16, 4, tzinfo=timezone.utc),
                prefer_cache_time=True,
            )

        self.assertFalse(freshness["stale"])
        self.assertEqual(freshness["basis"], "cache_time")

    def test_command_cache_binary_file_uses_mtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cache.npz"
            path.write_bytes(b"\xff\x00not a csv")
            mtime = datetime(2026, 6, 20, 15, 30, tzinfo=timezone.utc).timestamp()
            os.utime(path, (mtime, mtime))

            freshness = existing_csv_freshness(
                path,
                stale_after_hours=24.0,
                now=datetime(2026, 6, 20, 16, 4, tzinfo=timezone.utc),
                prefer_cache_time=True,
            )

        self.assertFalse(freshness["stale"])
        self.assertEqual(freshness["basis"], "file_mtime")

    def test_ib_request_timeout_is_bounded_for_contract_qualification(self) -> None:
        class FakeIB:
            RequestTimeout = 0.0

        fake = FakeIB()

        _configure_ib_request_timeout(fake, 0.25)

        self.assertEqual(fake.RequestTimeout, 1.0)


if __name__ == "__main__":
    unittest.main()
