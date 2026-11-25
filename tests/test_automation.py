"""Local browser interception only: no IQAir network requests in these tests."""
from datetime import datetime, UTC, timedelta
from pathlib import Path
import json

import pytest
from playwright.sync_api import sync_playwright

from iqair_collector.browser import capture_page
from iqair_collector.extractors.base import ExtractionError
from iqair_collector.extractors.browser_capture import parse_browser_capture
from iqair_collector.scheduler import next_run

ROOT = Path(__file__).resolve().parents[1]


def state_html(capture):
    # Synthetic React Router reference encoding built from an actual decoded
    # capture. Tests decoding mechanics, not original IQAir HTML fidelity.
    table = []
    def encode(v):
        index = len(table)
        table.append(None)
        if isinstance(v, dict):
            table[index] = {'_' + str(encode(k)): encode(n) for k,n in v.items()}
        elif isinstance(v, list):
            table[index] = [encode(n) for n in v]
        else:
            table[index] = v
        return index
    encode({'loaderData': {'root': {'customer': 'DO_NOT_CAPTURE'},
                           'routes/$(locale).air-quality.$': capture}})
    payload = json.dumps(json.dumps(table, separators=(',', ':')))
    return '<h1>Local fixture</h1><h2>Local label</h2><script type="text/plain">window.__reactRouterContext.streamController.enqueue(' + payload + ')</script>'


@pytest.fixture(scope='module')
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chromium')
        yield browser
        browser.close()


@pytest.mark.parametrize('station,file', [('bmkg_sleman','sleman'),('amaranta_prambanan','amaranta'),('dteti_ugm','dteti')])
def test_browser_capture_pipeline_without_network(browser, station, file):
    capture = json.loads((ROOT/f'samples/discovery/{file}_browser_current.json').read_text(encoding='utf-8'))
    with browser.new_context() as ctx:
        ctx.route('**/*', lambda route: route.fulfill(status=200, content_type='text/html', body=state_html(capture)))
        payload = capture_page(ctx.new_page(), station, timeout_ms=3000)
    assert b'DO_NOT_CAPTURE' not in payload
    result = parse_browser_capture(payload, station)
    assert str(result.pm25_ugm3) == str(capture['details']['current']['concentration'])


@pytest.mark.parametrize('status', [401,403,429,500])
def test_browser_denial_has_no_retry(browser, status):
    requests = []
    with browser.new_context() as ctx:
        def intercept(route):
            requests.append(route.request.url)
            route.fulfill(status=status, content_type='text/html', body='Denied')
        ctx.route('**/*', intercept)
        with pytest.raises(ExtractionError) as error:
            capture_page(ctx.new_page(), 'bmkg_sleman', timeout_ms=1000)
        assert error.value.code == ('HTTP_ERROR' if status == 500 else 'BLOCKED_ACCESS')
    assert len(requests) == 1


def test_changed_page_fails_without_values(browser):
    with browser.new_context() as ctx:
        ctx.route('**/*', lambda route: route.fulfill(body='<p>PM2.5 12 ug/m3</p>'))
        from playwright.sync_api import TimeoutError
        with pytest.raises(TimeoutError):
            capture_page(ctx.new_page(), 'bmkg_sleman', timeout_ms=100)


def test_schedule_boundary_and_rollover():
    assert next_run(datetime(2026,1,1,23,16,tzinfo=UTC)) == datetime(2026,1,2,0,15,tzinfo=UTC)
    assert next_run(datetime(2026,1,1,1,15,tzinfo=UTC)).hour == 2
    assert next_run(datetime(2026,1,1,1,14,tzinfo=UTC)).hour == 1
    with pytest.raises(ValueError):
        next_run(datetime(2026,1,1))


def test_expired_collection_does_not_restart_90_days():
    from iqair_collector.scheduler import serve
    calls = []
    serve(lambda: calls.append(True), datetime.now(UTC)-timedelta(days=91))
    assert calls == []


def test_scheduler_stops_on_access_denial(monkeypatch, capsys):
    from iqair_collector.cli import main
    import iqair_collector.collector as collector
    import iqair_collector.scheduler as scheduler
    monkeypatch.setenv('IQAIR_AUTOMATION_AUTHORIZED','true')
    monkeypatch.setenv('SCHEDULED_COLLECTION_ENABLED','true')
    monkeypatch.setenv('DATABASE_URL','postgresql://unused')
    monkeypatch.setenv('COLLECTION_START_UTC',datetime.now(UTC).isoformat())
    monkeypatch.setattr(collector,'collect',lambda *args:[{'status':'failed','error_code':'BLOCKED_ACCESS'}])
    monkeypatch.setattr(scheduler,'serve',lambda job,**kwargs:job())
    assert main(['schedule','--all']) == 2
    assert 'scheduler stopped' in capsys.readouterr().out
