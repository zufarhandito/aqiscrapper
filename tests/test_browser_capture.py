"""Positive inputs are derived captures of public page state, not fabricated data."""
from pathlib import Path
from datetime import timedelta
import json

import pytest

from iqair_collector.extractors.base import ExtractionError
from iqair_collector.extractors.browser_capture import parse_browser_capture

ROOT = Path(__file__).resolve().parents[1] / "samples/discovery"


@pytest.mark.parametrize("station,filename,value,hour", [
    ("bmkg_sleman", "sleman_browser_current.json", "38.6", 0),
    ("amaranta_prambanan", "amaranta_browser_current.json", "53", 1),
    ("dteti_ugm", "dteti_browser_current.json", "23", 7),
])
def test_real_browser_current_matches_ui(station, filename, value, hour):
    result = parse_browser_capture((ROOT / filename).read_bytes(), station)
    assert str(result.pm25_ugm3) == value
    assert result.interval_end_utc.hour == hour
    assert result.interval_end_utc - result.interval_start_utc == timedelta(hours=1)
    assert result.observed is True


@pytest.mark.parametrize("mutation", ["city", "wrong_id", "wrong_contributor", "aqi", "forecast_only", "estimated", "naive", "negative", "missing"])
def test_capture_safety(mutation):
    data = json.loads((ROOT / "sleman_browser_current.json").read_text(encoding="utf-8"))
    details = data["details"]
    if mutation == "city":
        data["type"] = "city"
    elif mutation == "wrong_id":
        details["id"] = "other"
    elif mutation == "wrong_contributor":
        details["contributors"] = []
    elif mutation == "aqi":
        details["current"]["pollutants"][0]["unit"] = "AQI"
    elif mutation == "forecast_only":
        details["forecasts"] = {"hourly": [details.pop("current")]}
    elif mutation == "estimated":
        details["current"]["estimated"] = True
    elif mutation == "naive":
        details["current"]["ts"] = "2026-11-18T00:00:00"
    elif mutation == "negative":
        details["current"]["pollutants"][0]["concentration"] = -5
    else:
        del details["current"]["ts"]
    with pytest.raises(ExtractionError):
        parse_browser_capture(json.dumps(data).encode(), "bmkg_sleman")


def test_stations_cannot_be_swapped():
    with pytest.raises(ExtractionError):
        parse_browser_capture((ROOT / "amaranta_browser_current.json").read_bytes(), "bmkg_sleman")
