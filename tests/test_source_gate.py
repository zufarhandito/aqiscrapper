import hashlib
import json
from datetime import datetime, UTC
from pathlib import Path

import pytest

from iqair_collector.cli import main
from iqair_collector.extractors.base import ExtractionError, SourceSnapshot, UnverifiedSourceExtractor

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name", ["sleman", "yogyakarta", "computation", "history"])
def test_real_denied_capture_is_not_observation(name):
    folder = ROOT / "samples/discovery"
    metadata = json.loads((folder / f"{name}.json").read_text())
    payload = (folder / f"{name}.html").read_bytes()
    assert hashlib.sha256(payload).hexdigest() == metadata["sha256"]
    snapshot = SourceSnapshot(payload, metadata["final_url"], metadata["status"],
                              datetime.fromisoformat(metadata["fetched_at_utc"]))
    with pytest.raises(ExtractionError) as error:
        UnverifiedSourceExtractor().parse(snapshot, "bmkg_sleman")
    assert error.value.code == "BLOCKED_ACCESS"


@pytest.mark.parametrize("payload", [b"", b"<p>PM2.5 26.6 ug/m3</p>", b'{"aqi":85}', b'{"forecast":[26]}'])
def test_unverified_payload_never_accepted(payload):
    # Synthetic negative inputs, not IQAir fixtures or a claimed source schema.
    snapshot = SourceSnapshot(payload, "https://example.invalid", 200, datetime.now(UTC))
    with pytest.raises(ExtractionError) as error:
        UnverifiedSourceExtractor().parse(snapshot, "amaranta_prambanan")
    assert error.value.code == "BLOCKED_UNVERIFIED_SOURCE"


def test_collection_is_blocked(capsys, monkeypatch):
    monkeypatch.setenv('IQAIR_AUTOMATION_AUTHORIZED', 'false')
    assert main(["collect-once", "--all"]) == 2
    assert json.loads(capsys.readouterr().out)["accepted_count"] == 0
