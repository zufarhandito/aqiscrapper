# Capture provenance

Raw HTML and adjacent JSON were saved by a single urllib HTTP request per URL on
2026-11-18. All four returned HTTP 429. JSON records request time, final URL,
status and SHA-256 of the exact response bytes. These are access-denial fixtures,
not successful station measurements. No request was retried.

Web-reader observations described in the discovery report are a separate evidence
channel. Its rendered/cached text is not the HTML captured here. No positive raw
station fixture has been obtained. Do not construct one from the rendered numbers.

Update: `*_browser_current.json` are actual **selected, decoded public page-state**
captures obtained later via shared-browser inspection, with capture timestamp,
station identity, current measurement and UI fragments. They are derived fixtures,
not raw HTTP responses. `*_browser_history.json` preserve actual history UI text
after selecting PM2.5. Their provenance and extraction steps are described in the
latest discovery report. These current captures now provide positive parser tests.
