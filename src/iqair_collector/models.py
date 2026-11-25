from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal


@dataclass(frozen=True)
class StationPM25Reading:
    station_id: str
    source_station_name: str
    source_contributor: str
    source_url: str
    source_label_time_raw: str
    source_label_timestamp: datetime
    source_time_semantics: str
    interval_start_utc: datetime
    interval_end_utc: datetime
    pm25_ugm3: Decimal
    observed: bool
    extraction_method: str
    fetched_at_utc: datetime
    quality_flags: tuple[str, ...]
    raw_snapshot_hash: str | None
    pollutant: str = "PM2.5"
    unit: str = "ug/m3"
    measurement_source: str = "iqair_published_station_aggregate"
    source_details: dict = field(default_factory=dict)

    def __post_init__(self):
        for value in (self.source_label_timestamp, self.interval_start_utc,
                      self.interval_end_utc, self.fetched_at_utc):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Timestamp must be timezone-aware")
        for value in (self.interval_start_utc, self.interval_end_utc, self.fetched_at_utc):
            if value.utcoffset() != timedelta(0):
                raise ValueError("Canonical timestamps must be UTC")
        if self.interval_end_utc - self.interval_start_utc != timedelta(hours=1):
            raise ValueError("Hourly interval required")
        if self.source_time_semantics == "interval_end_labeled":
            expected_label = self.interval_end_utc
        elif self.source_time_semantics == "interval_start_labeled":
            expected_label = self.interval_start_utc
        else:
            raise ValueError("Unknown source time semantics")
        if self.source_label_timestamp != expected_label:
            raise ValueError("Label and canonical interval disagree")
        if self.observed is not True or self.pollutant != "PM2.5" or self.unit != "ug/m3":
            raise ValueError("Only observed PM2.5 concentration is accepted")
        if not isinstance(self.pm25_ugm3, Decimal) or not self.pm25_ugm3.is_finite() or self.pm25_ugm3 < 0:
            raise ValueError("PM2.5 must be a finite nonnegative Decimal")
        if self.interval_end_utc > self.fetched_at_utc + timedelta(minutes=2):
            raise ValueError("Future observation")
        if self.extraction_method not in {"structured", "html", "browser"}:
            raise ValueError("Unknown extraction method")
        if not all((self.station_id, self.source_station_name, self.source_contributor,
                    self.source_url, self.source_label_time_raw)):
            raise ValueError("Missing provenance")
