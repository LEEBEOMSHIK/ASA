from datetime import UTC, datetime

from asa.registry.runtime import next_daily


def test_daily_seoul_boundary_and_missed_occurrences():
    assert next_daily("09:00", datetime(2026, 10, 26, 0, 0, tzinfo=UTC)) == datetime(
        2026, 10, 27, 0, 0, tzinfo=UTC)
    assert next_daily("09:00", datetime(2026, 10, 26, 23, 0, tzinfo=UTC)) == datetime(
        2026, 10, 27, 0, 0, tzinfo=UTC)
