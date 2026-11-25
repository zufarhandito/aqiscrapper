"""Parse the selected public page-state capture, not arbitrary IQAir JSON.

The capture is a derived fixture from the browser; this module does not fetch
pages, open browsers, or grant authorization for scheduled collection.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256
import json

from iqair_collector.models import StationPM25Reading
from .base import ExtractionError

TARGETS = {
    "bmkg_sleman": (
        "7165697aab08555d97b4", "SLEMAN",
        "Indonesian Meteorology, Climatology, and Geophysics Council",
        "https://www.iqair.com/id/air-quality/indonesia/yogyakarta/sleman/sleman"),
    "amaranta_prambanan": (
        "66d95425fefa97e65599ead8", "Amaranta Prambanan", "Hotel Amaranta Prambanan",
        "https://www.iqair.com/id/air-quality/indonesia/yogyakarta/yogyakarta/amaranta-prambanan"),
    "dteti_ugm": (
        "69cb6499b52a87c536f30bf8", "Smart Censor DTETI Lt. 4", "Sensor IQAir DTETI",
        "https://www.iqair.com/id/air-quality/indonesia/yogyakarta/sleman/smart-censor-dteti-lt-4"),
}


def parse_browser_capture(payload: bytes, station_id: str) -> StationPM25Reading:
    try:
        expected_id, name, contributor, url = TARGETS[station_id]
        data = json.loads(payload, parse_float=Decimal)
        details = data["details"]
        if (data["source_url"] != url or data["type"] != "station" or
                details["type"] != "station" or details["id"] != expected_id or
                details["name"] != name or
                contributor not in [c["name"].strip() for c in details["contributors"]]):
            raise ExtractionError("BLOCKED_STATION_IDENTITY", "Station URL/ID/name/contributor mismatch")
        if details["timezone"] != "Asia/Jakarta":
            raise ExtractionError("BLOCKED_TIMESTAMP_SEMANTICS", "Unexpected source timezone")
        current = details["current"]  # Deliberately never traverse forecasts.
        if current["estimated"] is not False:
            raise ExtractionError("BLOCKED_NOT_OBSERVED", "Estimated measurement rejected")
        pm25 = [p for p in current["pollutants"] if p["pollutantName"] == "pm25"]
        if len(pm25) != 1 or pm25[0]["unit"] != "µg/m³":
            raise ExtractionError("BLOCKED_NO_PM25_CONCENTRATION", "Explicit PM2.5 concentration required")
        label = datetime.fromisoformat(current["ts"].replace("Z", "+00:00"))
        if label.tzinfo is None or label.utcoffset() != timedelta(0) or label.minute or label.second or label.microsecond:
            raise ExtractionError("BLOCKED_TIMESTAMP_SEMANTICS", "Full UTC hourly timestamp required")
        fetched = datetime.fromisoformat(data["captured_at_utc"].replace("Z", "+00:00"))
        # End-label semantics independently matched to UI interval in discovery.
        start = label - timedelta(hours=1)
        flags = []
        value = Decimal(str(pm25[0]["concentration"]))
        if value.is_finite() and value > 1000:
            flags.append("extreme_value")
        if fetched - label > timedelta(hours=2):
            flags.append("stale")
        return StationPM25Reading(
            station_id=station_id, source_station_name=name, source_contributor=contributor,
            source_url=url, source_label_time_raw=current["ts"], source_label_timestamp=label,
            source_time_semantics="interval_end_labeled", interval_start_utc=start,
            interval_end_utc=label, pm25_ugm3=value, observed=True,
            extraction_method="browser", fetched_at_utc=fetched,
            quality_flags=tuple(flags), raw_snapshot_hash=sha256(payload).hexdigest(),
            source_details={key: details[key] for key in
                            ('id', 'name', 'type', 'timezone', 'coordinates', 'contributors', 'current')
                            if key in details})
    except ExtractionError:
        raise
    except (KeyError, TypeError, ValueError, ArithmeticError, AttributeError, IndexError) as exc:
        raise ExtractionError("INVALID_BROWSER_CAPTURE", str(exc)) from exc
