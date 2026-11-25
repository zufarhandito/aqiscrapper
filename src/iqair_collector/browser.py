from importlib.resources import files
import json
import os

from .extractors.base import ExtractionError
from .extractors.browser_capture import TARGETS

CAPTURE_JS = files('iqair_collector').joinpath('capture.js').read_text(encoding='utf-8')


def capture_page(page, station_id: str, timeout_ms: int = 30000) -> bytes:
    response = page.goto(TARGETS[station_id][3], wait_until='domcontentloaded', timeout=timeout_ms)
    if response is None or response.status != 200:
        status = response.status if response else None
        code = 'BLOCKED_ACCESS' if status in (401, 403, 429) else 'HTTP_ERROR'
        raise ExtractionError(code, f'Navigation status {status}; no retry or bypass')
    page.wait_for_function("() => [...document.scripts].some(s => s.textContent.startsWith('window.__reactRouterContext.streamController.enqueue(\"[{'))", timeout=timeout_ms)
    result = page.evaluate(CAPTURE_JS)
    return json.dumps(result, ensure_ascii=False, sort_keys=True).encode('utf-8')


def capture_station(station_id: str, headed: bool = False) -> bytes:
    from playwright.sync_api import sync_playwright, Error
    try:
        with sync_playwright() as p:
            executable = os.getenv('BROWSER_EXECUTABLE_PATH') or None
            browser = p.chromium.launch(
                channel=None if executable else 'chromium',
                executable_path=executable, headless=not headed)
            try:
                context = browser.new_context(locale='id-ID', timezone_id='Asia/Jakarta')
                page = context.new_page()
                return capture_page(page, station_id)
            finally:
                browser.close()
    except ExtractionError:
        raise
    except Error as exc:
        # Do not expose response bodies, cookies or browser session details.
        raise ExtractionError('BROWSER_ERROR', type(exc).__name__ + '; browser navigation/capture failed') from exc
