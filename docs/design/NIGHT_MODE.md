# After-dark carousel

Approved direction, 27 September 2026: keep the bird journal by day and enter the illustrated bat/owl carousel after local sunset when daytime birds quieten and either sustained bat activity or an owl is heard. Keep both bat and owl artwork, use detection counts, and omit repetitive biological caveats. Historical report bounds and actual operational failures remain honest.

## Switching and persistence

At each existing refresh, compare the latest 30 minutes of qualifying daytime bird records (excluding owls) with the rate in the hour before sunset. Quiet means at most 25% of that baseline rate, or at most two records in the recent half hour. Bat activity means at least ten qualifying records across at least three five-minute bins in the recent half hour. An eligible owl record since sunset is an alternative to the bat threshold. These thresholds are configurable starting values.

Use geometric local sunset with refraction convention (solar centre -0.833 degrees), not civil dusk. Source coordinates come from read-only station state or explicit configuration. Use UTC for elapsed windows and local dates for evening identity. No coordinates or trustworthy solar window means no automatic transition.

Require complete trigger scans, recent microphone coverage and healthy available detection pipelines before inferring bird quietness. Do not equate a complete API scan with recording coverage. Persist a latch keyed by evening date and station/filter identity until the following sunrise. Missing data holds a previously selected night edition; it never creates a new latch. Startup/manual refresh continues to follow the existing saved panel guard. Preview/check must not mutate the latch or carousel.

Cycle rhythm, history, journal on successful scheduled editions. Repeated pushes within an edition must not race through pages. Bring the owl journal forward once for a newly heard owl species, then resume. Recheck solar exit at the next normal refresh. Bird local-midnight/trailing-hour aggregation remains unchanged.

## Data and display

Read raw bat and bird detection records with source/review/withdrawal filtering. Generic ultrasonic bat passes need a separate score policy from species-ranked birds. Bounded scans must disclose incomplete totals with a plus suffix and withhold unsupported baselines. Compare only equal completed elapsed periods after each night's own sunset; future intervals and missing nights are gaps. Use recent recording coverage and compatible detector identities when deciding whether historical data can be compared; never silently reuse the station's unfiltered group roll-ups.

Three actual 480×800 pages target design/concepts/after-dark-bats-and-owls-v3. Reuse existing owl artwork through the normal curated-first lookup. Import a bat asset from the approved concept rather than adding paid API calls. Daytime hardware driver and artwork generation services are unchanged.

## Implementation and validation plan

1. Add offline tests for independent bat filtering, UTC solar windows, trigger boundaries, owl exclusion/exception, missing recording data, latch restart/sunrise and carousel stability.
2. Implement a separate night reducer and bounded night client using existing read-only transport. Keep day reduction and cache contracts compatible; add validated night settings and diagnostic output.
3. Implement three deterministic native-palette pages and labelled offline night demo fixtures. Validate dimensions, missing/partial data, long labels and all three rendered images.
4. Integrate selection/persistence around existing refresh flow, preserving cooldown and failed-attempt semantics. Test preview/check no-state writes and cached-night behaviour.
5. Run make verify and generated-unit verification; independently review changes, inspect previews, and correct substantive findings.
6. Deploy only reviewed files to the confirmed Pi with a private backup and state/artwork preservation, then check service logs without claiming unseen physical testing.

## Work log

- Existing uncommitted startup/manual-refresh, colour-wash and related documentation/tests predate this feature. Work in place to retain those approved changes; do not overwrite or revert them.
- Initial sandbox test run: local mock HTTP socket binds denied; rerunning the same offline suite with socket permission. No application failure established by that run.
- User's “ship it” authorizes implementation and delivery of the agreed design. Deployment target confirmed as `192.168.1.89`, installed at `/home/simon/garden_ink`.

## Configuration and previews

Night mode is enabled by default. `night_mode: false` restores day-only selection. Coordinates are read from station pipeline diagnostics unless both `latitude` and `longitude` are supplied explicitly. `night_bird_ratio`, `night_bird_quiet_count`, `night_bat_count` and `night_bat_bins` set the thresholds above; `bat_min_score` defaults to 0.5. `night_coverage_fraction` defaults to 0.9 and `night_max_pages` bounds the additional raw-record scan. These reads do not change station configuration.

From the checkout, use `PYTHONPATH=display .venv/bin/python display/dashboard.py --demo --preview --night-page rhythm --output local/previews/night-rhythm.png`; substitute `history` or `journal` for the other pages. The samples are labelled. `--night-page` is restricted to preview/check, so it cannot force a physical night transition. Live `--check` includes night data and trigger diagnostics. Preview and check never advance the persisted carousel.

Previous nights use equal completed hours after their own sunset. Without historical detector-effort records, an all-zero historical window cannot prove that bat analysis ran; such nights remain gaps. Comparable windows require adequate native-rate microphone coverage and matching observed detector versions. This is a detection-count comparison, not a weather-adjusted measure of the population.

## Verification record

27 September 2026: 324 offline tests passed with `make verify`, including source/review filtering, DST/midnight solar windows, carousel persistence, failed frame attempts, partial comparisons and three native 480×800 renders. An independent review's two findings were corrected: missing current recording coverage suppresses medians, and partial descending scans no longer claim a first detection time. The Pi's installed systemd unit passed validation. Live read-only testing exposed lifetime stream discontinuity counters; coverage now uses window-scoped missing-frame evidence instead. No paid image requests were made.

The first transfer was interrupted before connecting by a Pi reboot at 11:58:38 BST, consistent with the reported shared-USB power interruption. Deployment resumed after recovery with a fresh private backup at `/home/simon/garden_ink-private-night-20260927-1205.tar.gz`. All ten installed release files matched their hashes, and all 70 protected files (configuration, curated art, hardware driver and saved state) were unchanged before restarting services. The installed Pi application passed compilation, service-unit validation, a live daytime check and all three 480×800 sample renders. Both services restarted at 12:08 BST. The driver logged a completed 28-second panel refresh at 12:08:59, then panel sleep and the next scheduled report at 13:00; both services remained active. Release and manifest remain private in `local/`. An isolated read-only replay returned 626 filtered bat detections, owl records and seven usable comparison nights; this was a historical API compatibility check, not an observed dusk transition.
