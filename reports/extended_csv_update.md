# Extended CSV update — 22 November 2026

Implemented in local workspace. All 57 offline tests passed, including legacy
snapshot recovery, missing-data handling, additional pollutant export and WIB
day rollover. No new live IQAir requests were used for validation.

Deployment to Pi is pending: SSH to 100.98.100.126 timed out; Windows Tailscale
reported Pi offline, last seen approximately 18 hours ago. The running Pi copy
and Drive CSVs have not been updated by this change.

Changed runtime files:

- src/iqair_collector/models.py
- src/iqair_collector/extractors/browser_capture.py
- src/iqair_collector/outputs.py

Deployment procedure when Pi returns online:

1. Confirm SSH host identity and inspect collector status/logs before changing it.
2. Back up these three remote files and SQLite through the SQLite backup API.
3. Stop collector and Drive timer; wait for any active Drive copy to finish.
4. Replace the three runtime files with the tested local versions.
5. Run report from /home/pi/iqair-collector to regenerate CSVs using saved snapshots.
   Compare row counts and original PM2.5 values before/after; inspect added values.
6. Restore collector and timer to their prior enabled/running states, preserving
   the existing fixed 90-day collection window. Trigger one Drive copy and verify.

No dependency change, database schema migration or additional browser navigation
is needed. Data outside the selected public station metadata/current object,
including historical observations and forecasts, is outside this update.
