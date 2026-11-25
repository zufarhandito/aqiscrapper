from contextlib import closing
import csv
import json
from pathlib import Path
from unittest.mock import patch

from iqair_collector.collector import collect
from iqair_collector.extractors.base import ExtractionError
from iqair_collector.outputs import export_csv, report
from iqair_collector.storage import connect, init_store, station_lock


def fixture(station):
    key={'bmkg_sleman':'sleman','amaranta_prambanan':'amaranta','dteti_ugm':'dteti'}[station]
    return (Path(__file__).resolve().parents[1]/f'samples/discovery/{key}_browser_current.json').read_bytes()


def test_local_ingest_dedup_revision_and_csv(tmp_path):
    stations=['bmkg_sleman','amaranta_prambanan']
    assert all(r['status']=='inserted' for r in collect(tmp_path,stations,fetcher=fixture))
    assert all(r['status']=='unchanged' for r in collect(tmp_path,stations,fetcher=fixture))
    def revised(station):
        data=json.loads(fixture(station))
        data['details']['current']['pollutants'][0]['concentration']=40
        return json.dumps(data).encode()
    assert collect(tmp_path,['bmkg_sleman'],fetcher=revised)[0]['status']=='revised'
    with closing(connect(tmp_path)) as conn:
        assert conn.execute('SELECT count(*) FROM observations').fetchone()[0]==2
        assert conn.execute('SELECT count(*) FROM revisions').fetchone()[0]==1
        assert conn.execute('SELECT count(*) FROM runs').fetchone()[0]==5
    rows=list(csv.DictReader((tmp_path/'bmkg_sleman.csv').open(encoding='utf-8-sig')))
    assert len(rows)==1 and rows[0]['pm25_ugm3']=='40'
    assert rows[0]['interval_start_local'].endswith('+07:00')
    assert export_csv(tmp_path,tmp_path/'combined.csv')==2
    assert len(report(tmp_path))==2


def test_partial_failure_retains_payload_and_other_station(tmp_path):
    def fetch(station):
        return b'{"bad":true}' if station=='bmkg_sleman' else fixture(station)
    result=collect(tmp_path,['bmkg_sleman','amaranta_prambanan'],fetcher=fetch)
    assert [r['status'] for r in result]==['failed','inserted']
    with closing(connect(tmp_path)) as conn:
        assert conn.execute('SELECT count(*) FROM quarantine').fetchone()[0]==1
        assert conn.execute('SELECT count(*) FROM snapshots').fetchone()[0]==2


def test_access_denial_stops_batch(tmp_path):
    calls=[]
    def denied(station):
        calls.append(station)
        raise ExtractionError('BLOCKED_ACCESS','HTTP 429')
    assert collect(tmp_path,['bmkg_sleman','amaranta_prambanan'],fetcher=denied)[0]['status']=='failed'
    assert len(calls)==1


def test_overlapping_writer_is_skipped(tmp_path):
    init_store(tmp_path)
    with closing(connect(tmp_path)) as conn, station_lock(conn,'bmkg_sleman') as acquired:
        assert acquired
        assert collect(tmp_path,['bmkg_sleman'],fetcher=fixture)[0]['status']=='locked'


def test_csv_failure_keeps_old_file_and_recovers_from_state(tmp_path):
    collect(tmp_path,['bmkg_sleman'],fetcher=fixture)
    target=tmp_path/'bmkg_sleman.csv'
    previous=target.read_bytes()
    def revised(station):
        data=json.loads(fixture(station))
        data['details']['current']['pollutants'][0]['concentration']=41
        return json.dumps(data).encode()
    import pytest
    with patch('iqair_collector.outputs.os.replace',side_effect=PermissionError('Excel file locked')):
        with pytest.raises(PermissionError):
            collect(tmp_path,['bmkg_sleman'],fetcher=revised)
    assert target.read_bytes()==previous
    assert not list(tmp_path.glob('.collector-*.tmp'))
    report(tmp_path)
    rows=list(csv.DictReader(target.open(encoding='utf-8-sig')))
    assert rows[0]['pm25_ugm3']=='41'


def test_report_initializes_empty_local_folder(tmp_path):
    assert report(tmp_path)==[]


def test_extended_csv_and_legacy_snapshot_recovery(tmp_path):
    collect(tmp_path, ['dteti_ugm'], fetcher=fixture)
    target = tmp_path / 'dteti_ugm.csv'
    def row():
        with target.open(encoding='utf-8-sig') as stream:
            return next(csv.DictReader(stream))
    fresh = row()
    assert fresh['ditangkap_pada_wib'] == 'Kamis, 19 November 2026 (15:40) WIB'
    assert fresh['source_label_local'] == '2026-11-19T14:00:00+07:00'
    assert fresh['aqi'] == '77' and fresh['humidity_source'] == '89'
    assert fresh['wind_speed_source'] == '5'
    assert fresh['pm10_concentration'] == ''  # Never manufacture absent pollutants.
    assert json.loads(fresh['current_json'])['estimated'] is False
    assert json.loads(fresh['source_details_json'])['coordinates']['latitude'] == '-7.766'
    # Simulate an observation created by the previous deployed version.
    with closing(connect(tmp_path)) as conn:
        doc = json.loads(conn.execute('SELECT reading FROM observations').fetchone()[0])
        doc.pop('source_details')
        conn.execute('UPDATE observations SET reading=?', (json.dumps(doc),))
    report(tmp_path)
    recovered = row()
    assert recovered['aqi'] == fresh['aqi']
    assert recovered['latitude'] == fresh['latitude']
    assert recovered['ditangkap_pada_wib'] == fresh['ditangkap_pada_wib']
    # Without a saved snapshot, retain old readings and leave extra data empty.
    with closing(connect(tmp_path)) as conn:
        conn.execute('DELETE FROM snapshots')
    report(tmp_path)
    assert row()['pm25_ugm3'] == '23' and row()['aqi'] == ''


def test_capture_date_uses_wib_across_day_boundary(tmp_path):
    def late(station):
        data = json.loads(fixture(station))
        data['captured_at_utc'] = '2026-11-22T18:15:00Z'
        data['details']['current']['pollutants'].append(
            {'pollutantName': 'pm10', 'concentration': 12, 'unit': 'ug/m3', 'aqi': 10})
        return json.dumps(data).encode()
    collect(tmp_path, ['dteti_ugm'], fetcher=late)
    with (tmp_path/'dteti_ugm.csv').open(encoding='utf-8-sig') as stream:
        row = next(csv.DictReader(stream))
    assert row['ditangkap_pada_wib'] == 'Senin, 23 November 2026 (01:15) WIB'
    assert row['pm10_concentration'] == '12' and row['pm10_unit'] == 'ug/m3'


def test_three_station_collection_and_dteti_identity(tmp_path):
    from iqair_collector.extractors.browser_capture import TARGETS, parse_browser_capture
    import pytest
    result=collect(tmp_path,list(TARGETS),fetcher=fixture)
    assert len(result)==3 and all(r['status']=='inserted' for r in result)
    assert all((tmp_path/f'{station}.csv').is_file() for station in TARGETS)
    rows=list(csv.DictReader((tmp_path/'dteti_ugm.csv').open(encoding='utf-8-sig')))
    assert len(rows)==1 and rows[0]['pm25_ugm3']=='23'
    assert rows[0]['source_contributor']=='Sensor IQAir DTETI'
    with pytest.raises(ExtractionError):
        parse_browser_capture(fixture('bmkg_sleman'),'dteti_ugm')
    with pytest.raises(ExtractionError):
        parse_browser_capture(fixture('dteti_ugm'),'bmkg_sleman')
