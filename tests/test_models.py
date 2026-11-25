"""Synthetic contract tests only; no real successful IQAir reading is claimed."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone, UTC
from decimal import Decimal

import pytest

from iqair_collector.models import StationPM25Reading


@pytest.fixture
def reading():
    end = datetime(2026, 1, 1, 4, tzinfo=UTC)
    return StationPM25Reading(
        station_id="synthetic_station", source_station_name="SYNTHETIC",
        source_contributor="Synthetic test contributor", source_url="https://example.invalid",
        source_label_time_raw="2026-01-01T11:00:00+07:00",
        source_label_timestamp=end.astimezone(timezone(timedelta(hours=7))),
        source_time_semantics="interval_end_labeled", interval_start_utc=end-timedelta(hours=1),
        interval_end_utc=end, pm25_ugm3=Decimal("26.6"), observed=True,
        extraction_method="structured", fetched_at_utc=end+timedelta(minutes=15),
        quality_flags=(), raw_snapshot_hash=None)


def test_verified_end_label_contract(reading):
    assert reading.interval_start_utc.hour == 3
    assert reading.source_label_timestamp.hour == 11


@pytest.mark.parametrize("changes", [
    {"pm25_ugm3": Decimal("NaN")}, {"pm25_ugm3": Decimal("Infinity")},
    {"pm25_ugm3": Decimal("-5")}, {"pm25_ugm3": 26.6},
    {"unit": "AQI"}, {"pollutant": "US AQI"}, {"observed": False},
    {"source_time_semantics": "unknown"}, {"source_contributor": ""},
    {"interval_start_utc": datetime(2026, 1, 1, 3)},
    {"interval_start_utc": datetime(2026, 1, 1, 2, tzinfo=UTC)},
    {"source_label_timestamp": datetime(2026, 1, 1, 5, tzinfo=UTC)},
    {"fetched_at_utc": datetime(2026, 1, 1, 2, tzinfo=UTC)},
])
def test_invalid_contract_rejected(reading, changes):
    with pytest.raises(ValueError):
        replace(reading, **changes)


def test_extreme_value_is_not_silently_deleted(reading):
    assert replace(reading, pm25_ugm3=Decimal("1100"), quality_flags=("extreme_value",)).pm25_ugm3 == 1100
