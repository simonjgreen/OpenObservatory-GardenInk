# Bat display data feasibility

## What does the existing system support?

### Takeaway
The source already supports ultrasonic bat-event records, history, solar moments and microphone coverage. Garden Ink itself is currently bird-only. These are source-code findings and recorded project reports, not a fresh check of the deployed station.

### Cited Findings
- The reference Open Observatory uses an AudioMoth USB microphone captured at 384 kHz, with the 48 kHz audible stream derived from the same frames. USB describes the microphone connection; `alsa` is the software capture source, not a separate audible-only microphone. The source chooses `AlsaSource` and routes native-rate windows to the ultrasonic detector. [README](/home/simon/Documents/OpenObservatory/README.md:3), [source choice](/home/simon/Documents/OpenObservatory/src/open_observatory/station.py:487), [native detector](/home/simon/Documents/OpenObservatory/src/open_observatory/station.py:809).
- `ultrasonic-pass-v1` emits `taxonomic_group="bat"`, label `bat pass`, rank `None`, pulse/frequency statistics and a possible feeding-buzz flag. Its frequency hints explicitly are not species identifications. It refuses a native rate below its minimum, and optional night scheduling can return no detections while capture continues. [detector](/home/simon/Documents/OpenObservatory/src/open_observatory/detectors/ultrasonic.py:299), [event fields](/home/simon/Documents/OpenObservatory/src/open_observatory/detectors/ultrasonic.py:499).
- `GET /api/v1/detections?group=bat` supports UTC since/until, optional detector plugin filtering and up to 500 records/page. Payloads contain start/end, duration, peak frequency, source identity, detector/model version, withdrawal and latest review/effective name. Detailed individual records additionally expose native pulse/buzz statistics. [list endpoint](/home/simon/Documents/OpenObservatory/src/open_observatory/api/app.py:1608), [detail](/home/simon/Documents/OpenObservatory/src/open_observatory/api/app.py:1821), [payload](/home/simon/Documents/OpenObservatory/src/open_observatory/api/app.py:3032).
- The analytics API has night/day series, local-hour matrices, per-day solar moments, captured seconds, missing-day/status reporting and daylight/night spans. It reads roll-ups rebuilt by an hourly worker. ADR-079 records a Pi deployment/backfill, but this inspection did not verify that deployment today. [endpoints](/home/simon/Documents/OpenObservatory/src/open_observatory/api/app.py:2158), [ADR](/home/simon/Documents/OpenObservatory/docs/architecture/adr/ADR-079%20-%20Analytics%20section.md:34).
- Garden Ink requests `group=bird` and its reducer rejects non-birds and non-species ranks, so bat passes need a separate reduction policy, not just new artwork. Its existing today/trailing-hour logic and refresh cooldown must remain intact. [client](/home/simon/Documents/garden-ink/display/gardenink/client.py:100), [reducer](/home/simon/Documents/garden-ink/display/gardenink/model.py:31), [architecture](/home/simon/Documents/garden-ink/docs/ARCHITECTURE.md).

### Inferences
- Lowest-risk content candidates are a chart of qualifying acoustic detection records, first/last detection, peak detection period, and measured call-frequency bands. Any frequency-band panel should avoid converting those bands into asserted species.
- A possible feeding-buzz story is feasible as a later, carefully labelled candidate event with an educational explanation. A buzz flag alone cannot prove a feeding attempt succeeded, prey was caught or even the classifier was correct.
- “Minutes with at least one qualifying bat detection” is derivable from deduplicated raw timestamps, but is a new defined metric, not an existing active-minutes endpoint. Define start-minute versus interval-overlap binning explicitly, and never relabel it as minutes an individual bat spent in the garden.

### Gaps
- No live query was made: current capture rate, active detector, deployment revision, usable prior nights, coordinates and review quality remain unverified.
- No environmental weather input/API was found in the source search; temperature hits were CPU temperature. Weather correlations would need another source and time-aligned history, not the computer's temperature.

## Can tonight be compared honestly with the previous seven nights?

### Takeaway
Yes as a designed extension, preferably one current-night curve against a seven-night median/range, aligned to elapsed time after sunset. Existing aggregates are useful groundwork but do not directly implement Garden Ink's review policy or exact sunset-aligned windows.

### Cited Findings
- Analytics `grain=night` is **noon to noon**, keyed to the evening date; it is not sunset to sunrise. `/history`'s older `last-night` resolves to a fixed 20:00–08:00 window. Neither should be silently presented as astronomical darkness. [series](/home/simon/Documents/OpenObservatory/src/open_observatory/analytics.py:771), [history resolver](/home/simon/Documents/OpenObservatory/src/open_observatory/history.py:234).
- Solar code computes sunrise/sunset and civil dawn/dusk when coordinates are supplied. Analytics returns solar moments with hourly data. [solar calculation](/home/simon/Documents/OpenObservatory/src/open_observatory/schedule.py:80), [hours endpoint](/home/simon/Documents/OpenObservatory/src/open_observatory/api/app.py:2198).
- A critical policy mismatch: group-level analytics and history timelines intentionally retain withdrawn/rejected records as historical detection events. The named analytics table excludes withdrawn/rejected records and applies corrected names, but still does not expose all Garden Ink confidence/review eligibility choices. Bat labels are frequency bands in that table. [module policy](/home/simon/Documents/OpenObservatory/src/open_observatory/analytics.py:13), [builder predicates](/home/simon/Documents/OpenObservatory/src/open_observatory/analytics.py:285), [history endpoint](/home/simon/Documents/OpenObservatory/src/open_observatory/api/app.py:2118).
- Roll-ups carry freshness and missing-day information; days touched by a recent review are scheduled for rebuilding, and older stale days rotate through rebuilds. Withdrawals can therefore lag until rebuilding. [rebuild scheduling](/home/simon/Documents/OpenObservatory/src/open_observatory/analytics.py:538), [stale policy](/home/simon/Documents/OpenObservatory/src/open_observatory/analytics.py:53).
- Existing local-hour roll-ups merge the autumn repeated hour into one two-hour wall-clock cell and make the spring skipped cell empty. They therefore cannot exactly recover all UTC elapsed-since-sunset bins on DST transition nights. [hour windows](/home/simon/Documents/OpenObservatory/src/open_observatory/analytics.py:108).
- Garden Ink already has bounded backward pagination, per-window completeness and explicit lower-bound counts, preserving corrections through re-reads. It does not currently query historical capture coverage. [API contract](/home/simon/Documents/garden-ink/display/docs/API_CONTRACT.md).

### Inferences
- Define each report night by its evening date, extending across local midnight. Compute sunset/sunrise separately for the correct local dates, then use UTC for elapsed durations and comparisons. Preserve bird “today” at local midnight independently.
- Compare tonight only through the report's last completed matching bin with the same elapsed period after sunset on each eligible prior night. Do not compare tonight's partial total with completed-night totals. Use “3 of 7 comparable nights available” when history is insufficient; never manufacture seven nights.
- Good 480×800 concept: one bold current-night line or bar series, a restrained previous-seven-night median/range and one headline comparison. Gaps are absent/hatched, not zeros; the future part of tonight stays blank. The comparison can use detection records per bin, with a capture strip beneath and a clear metric label.
- Raw records (or a new station-side filtered aggregate) are needed to preserve Garden Ink source/review/withdrawal semantics and exact alignment. Query with min_score=0, then apply a bat-specific policy so human confirmation is not discarded by the original score. A bird confidence threshold should not silently become a bat threshold: this detector's score formula is different.
- Baselines should not cross known microphone moves, gain/threshold/schedule/model changes without disclosure. Existing model/plugin IDs help detect some changes, but do not certify stable microphone placement or all detector settings.

### Gaps
- No verified endpoint exposes a ready-made seven-night sunset-aligned, Garden Ink-filtered comparison.
- Read-only source inspection did not establish complete historical detector-settings epochs or a cheap review-compliant aggregate at the desired resolution. A raw seven-night scan must retain bounded pagination and honest partial results rather than assuming it is inexpensive.

## What does coverage really prove, and which concepts need least extra data?

### Takeaway
Microphone capture coverage is implemented, including stream sample rates and gaps. That is not proof all captured ultrasound was analysed, so a zero line should say “no qualifying bat detections” rather than “no bats”.

### Cited Findings
- `/history` coverage includes microphone seconds, stream intervals with sample rates, gaps, suspect-stream counts and pauses. It caps stream duration with recorded frames and merges overlapping intervals. The aggregate live seconds include all ALSA sample rates; consumers can inspect stream sample rates separately. [coverage implementation](/home/simon/Documents/OpenObservatory/src/open_observatory/history.py:695), [stream spans](/home/simon/Documents/OpenObservatory/src/open_observatory/history.py:735), [response](/home/simon/Documents/OpenObservatory/src/open_observatory/history.py:858).
- Detection coverage is a separate SLO based on analysed versus dropped windows. Current station status exposes detector snapshots, but the inspected historical/analytics coverage paths do not persist per-bin ultrasonic analysis effort. [SLO](/home/simon/Documents/OpenObservatory/src/open_observatory/slo.py:239), [status snapshots](/home/simon/Documents/OpenObservatory/src/open_observatory/station.py:2156).
- Ultrasonic health reveals current gating, while the schedule may be always or night and has configurable twilight margins. [health](/home/simon/Documents/OpenObservatory/src/open_observatory/detectors/ultrasonic.py:569), [schedule state](/home/simon/Documents/OpenObservatory/src/open_observatory/schedule.py:234), [defaults](/home/simon/Documents/OpenObservatory/src/open_observatory/config.py:609).
- E-ink is hourly, 480×800 portrait, with no free-standing or implied live clock. Historical intervals, retained report dates and explicit cached/offline status are established conventions. [visual specification](/home/simon/Documents/garden-ink/docs/design/VISUAL_SPEC.md).

### Inferences
- Distinguish three notions: complete API scan, microphone recording coverage at adequate native rate, and ultrasonic detector analysis effort. Neither complete data retrieval nor generic 100% microphone coverage proves bat detector availability throughout the night.
- Derive eligible recording intervals from live ALSA streams at a suitable native rate rather than directly using aggregate microphone seconds when streams vary. Mark uncertain detector effort instead of silently normalising by generic capture hours.
- Data-light alternatives: (1) a “night so far” strip with first/last detection, (2) a seven-night barcode of minutes containing detections, (3) “when the garden usually wakes after sunset” based on qualifying first-detection offsets, or (4) last completed night's summary while a new night has insufficient data. These are design suggestions, not delivered features.
- A small illustrated educational note can keep the screen interesting on quiet/unavailable nights without pretending there is live activity. Use static researched content separate from observation claims.

### Gaps
- Current indoor readability after dark and whether additional ambient lighting is needed were not physically tested. No hardware driver, scheduler, service or station was changed.
