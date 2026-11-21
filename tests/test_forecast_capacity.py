"""到达预测、容量估计与投影的单元测试。"""

import unittest
from datetime import date

from analysis.arrivals import build_arrival_forecasts, forecast_category
from analysis.config import Config
from analysis.models import ArrivalRow, CapacityRow, Complaint, Dataset
from analysis.periods import future_periods, iso_week_of, next_period
from analysis.loading import DataFormatError
from analysis.throughput import estimate_throughput
from analysis.timeline import build_case_states


def _arrival(category: str, period: str, received: int,
             households: int, corrections: int = 0) -> ArrivalRow:
    return ArrivalRow(period, category, received, households, corrections)


class ArrivalTests(unittest.TestCase):
    def test_trend_forecast_brackets_central(self):
        rows = [
            _arrival("refund", "2026-W05", 10, 8),
            _arrival("refund", "2026-W06", 12, 9),
            _arrival("refund", "2026-W07", 14, 10),
        ]
        forecast = forecast_category(rows, cycles=2)
        self.assertEqual(forecast.basis, "trend")
        self.assertGreater(forecast.trend_slope, 0)
        self.assertLessEqual(forecast.low, forecast.central)
        self.assertGreaterEqual(forecast.high, forecast.central)
        self.assertGreaterEqual(forecast.low, 0)

    def test_flat_series_uses_mean_basis(self):
        rows = [_arrival("advice", f"2026-W0{i}", 9, 8) for i in range(5, 9)]
        forecast = forecast_category(rows, cycles=1)
        self.assertEqual(forecast.basis, "flat_mean")
        self.assertEqual(forecast.central, 9)

    def test_missing_category_falls_back_to_case_log_with_flag(self):
        dataset = Dataset(
            arrivals=[_arrival("refund", "2026-W05", 10, 8)],
            complaints=[
                Complaint("C-1", "H-1", "M-1", "renewal", "high",
                          date(2026, 2, 5), "S-1"),
            ],
        )
        forecasts = build_arrival_forecasts(dataset, cycles=4)
        self.assertIn("renewal", forecasts)
        self.assertEqual(forecasts["renewal"].basis, "no_history")
        self.assertEqual(forecasts["renewal"].fallback_complaint_log_received, 1)


class PeriodTests(unittest.TestCase):
    def test_iso_week_rollover(self):
        self.assertEqual(next_period("2026-W08"), "2026-W09")
        # 2026 是 ISO 长年（53 周），W53 之后才进入 2027-W01
        self.assertEqual(next_period("2026-W53"), "2027-W01")
        self.assertEqual(next_period("2025-W52"), "2026-W01")
        self.assertEqual(len(future_periods("2026-W08", 4)), 4)
        self.assertEqual(iso_week_of(date(2026, 2, 23)), "2026-W09")


class ThroughputTests(unittest.TestCase):
    def test_closed_cases_drive_estimate_and_external_days_excluded(self):
        from analysis.models import Event
        complaint = Complaint("C-5", "H-6", "M-2", "advice", "unknown",
                              date(2026, 2, 6), "S-5")
        events = [
            Event("E1", "C-5", "assigned", date(2026, 2, 6), "T-3", ""),
            Event("E2", "C-5", "waiting_consumer", date(2026, 2, 7), "T-3", ""),
            Event("E3", "C-5", "received_evidence", date(2026, 2, 8), "T-3", ""),
            Event("E4", "C-5", "closed", date(2026, 2, 9), "T-3", ""),
        ]
        dataset = Dataset(
            complaints=[complaint],
            events=events,
            capacity=[CapacityRow("2026-W06", "T-3", 2, "advice", 0)],
        )
        states = build_case_states(dataset, date(2026, 2, 23))
        estimates = estimate_throughput(dataset, states, Config())
        est = estimates["T-3"]
        self.assertEqual(est.basis, "closed_cases")
        # 内部办案 1+1=2 天；外部等待 1 天不计入
        self.assertEqual(est.closed_handling_days, [2.0])
        self.assertGreater(est.per_person_throughput_central, 0)
        self.assertLessEqual(est.per_person_throughput_low,
                             est.per_person_throughput_central)

    def test_team_without_observation_is_marked_not_zero(self):
        dataset = Dataset(
            complaints=[Complaint("C-1", "H-1", "M-1", "refund", "medium",
                                  date(2026, 2, 1), "S-1")],
            capacity=[CapacityRow("2026-W05", "T-9", 3, "refund", 0)],
        )
        states = build_case_states(dataset, date(2026, 2, 23))
        estimates = estimate_throughput(dataset, states, Config())
        self.assertEqual(estimates["T-9"].basis, "no_observation")
        self.assertEqual(estimates["T-9"].per_person_throughput_central, 0.0)


class LoadingGuardTests(unittest.TestCase):
    def test_blank_count_is_an_error_not_zero(self):
        from analysis.loading import _parse_int
        with self.assertRaises(DataFormatError):
            _parse_int("", "unit-test")

    def test_negative_count_is_rejected(self):
        from analysis.loading import _parse_int
        with self.assertRaises(DataFormatError):
            _parse_int("-3", "unit-test")


if __name__ == "__main__":
    unittest.main()
