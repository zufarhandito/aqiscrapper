from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from iqair_collector.models import StationPM25Reading


class ExtractionError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(detail)


@dataclass(frozen=True)
class SourceSnapshot:
    payload: bytes
    source_url: str
    status_code: int
    fetched_at_utc: datetime


class StationExtractor(Protocol):
    def parse(self, snapshot: SourceSnapshot, station_id: str) -> tuple[StationPM25Reading, ...]: ...


class UnverifiedSourceExtractor:
    """Fail closed until an actual source format and semantics are verified.

    This is deliberately not an HTML selector or a claimed IQAir parser.
    """

    def parse(self, snapshot: SourceSnapshot, station_id: str) -> tuple[StationPM25Reading, ...]:
        if snapshot.status_code in (401, 403, 429):
            raise ExtractionError("BLOCKED_ACCESS", f"HTTP {snapshot.status_code}; no observations parsed")
        if snapshot.status_code != 200:
            raise ExtractionError("HTTP_ERROR", f"HTTP {snapshot.status_code}")
        raise ExtractionError("BLOCKED_UNVERIFIED_SOURCE", "No empirically verified IQAir source adapter installed")
