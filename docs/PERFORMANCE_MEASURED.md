# Measured performance soak (auto-generated 2026-10-24 08:18 UTC)

Methodology: the app boots against a throwaway SQLite under /tmp/opencode with
the normal seed, the clock jumps into the departure band, then it runs at the
requested speed for 6.31 wall seconds while sampling the control
snapshot. The two-second probe then injects a 40-minute delay on the seeded
Gate-42 flight and measures: (a) zone presence rise (crowd +257→
+405 passengers documented dwell model), (b) screen re-plan,
both relative to the injection.

| Metric | Value |
|---|---|
| Requested speed | 60x |
| Simulated seconds processed | 346.0 |
| Wall seconds | 6.31 |
| Sim progress rate | 54.8x (threshold ≥ 54x) |
| Decision rows persisted this run | 500 |
| Decision rows / wall-s during soak | 0.0 (planning upper bound 720/s, §21) |
| Presence raise latency | 0.473 s (limit 2.0) |
| Screen slot re-plan latency | 0.915 s (limit 2.0) |
| Thresholds met | True |

Interpretation: the engine is on one worker thread; latency figures include
HTTP round trips from the test client, i.e. an upper bound on what a browser
would observe through the same engine. Presence/sample resolution is the poll
interval (~20 ms); the documented allocation follows AGENTS §21 planning notes.
Re-execute this script to refresh the numbers: `.venv/bin/python scripts/soak.py --seconds 6 --speed 60` (or with docker: `docker compose exec airp uv run --no-dev python scripts/soak.py --seconds 6 --speed 60`).
