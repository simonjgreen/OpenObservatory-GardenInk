# Garden Ink 2: API contract and reduction rules

Reviewed source: `simonjgreen/OpenObservatory`, `src/open_observatory/api/app.py`, Git blob
`df33c9b05a243f0dd02dcf98827669ab4be773d5`, fetched again on 25 September 2026.
The previously inspected repository revision was `d71e77d0339188793df6b4a5305faf6f7c82d2c5`.
This client does not assume its version matches the station's deployed version.

Source references:
- https://github.com/simonjgreen/OpenObservatory/blob/d71e77d0339188793df6b4a5305faf6f7c82d2c5/src/open_observatory/api/app.py
- https://github.com/simonjgreen/OpenObservatory/blob/d71e77d0339188793df6b4a5305faf6f7c82d2c5/src/open_observatory/history.py

## Reads

`GET /api/v1/health`, including valid critical JSON returned with HTTP 503.
`checked_at` anchors the edition's upper bound when available; differences from
the display Pi's clock greater than five minutes are disclosed.

`GET /api/v1/detections` with:
- `since = min(today_local_midnight_utc, snapshot_utc - 3600 seconds)`
- `until = snapshot_utc`, exclusive, then adjusted for backward pagination
- `group=bird`, `identified_only=true`, `include_synthetic=false`
- `min_score=0` (deliberate; original scores cannot express human corrections)
- `limit=500` by default

The payload contains a `detections` array and a boolean `truncated`. A full page
is conservatively reported as truncated by the source API, even if its final row
happens to be the final row in the database. Another page is needed to prove that.
The API is not assumed to implement an undocumented cursor or offset parameter.

## Pagination

Rows must arrive newest first, with timestamps within the requested bounds and
identifiable IDs. A page's oldest timestamp + one microsecond becomes the next
exclusive `until`. This repeats the boundary cohort; duplicate IDs are counted
once. An oversized tie that prevents progress stops the scan and is disclosed.
No attempt is made to silently jump over unseen equal-time records.

Default limits: 64 pages and 180 seconds checked between requests. The client
reduces each page into per-species daily/hourly counters and timestamps, retaining
only seen IDs and summaries. Raw media-heavy payloads are discarded per page.

Each window is complete when either the full union query is exhausted or the
oldest fetched timestamp lies STRICTLY before that window's inclusive beginning.
An incomplete older day can thus coexist with a complete last hour. Counts in an
incomplete window are displayed as lower bounds, never extrapolated.

A first-page failure uses an explicitly cached edition if available. A later-page
failure leaves the current scan partial with the reason in diagnostics. Full
hourly re-reads pick up human reviews of earlier records without a station change.

## Identity/review policy

The current fields are validated rather than synthesised. Group must be `bird`;
`source_kind` must be `alsa`; `is_live_source` must literally be true. Withdrawn,
rejected, unsupported review states, invalid/unreviewed low scores and non-species
ranks are excluded. Human-corrected effective names take precedence. Corrected
names are not replaced with the original species when the correction is malformed.

A confirmed/corrected review bypasses the original score threshold. A held review
does not. Client counts describe qualifying detection records in the returned
bird-group data, not individual animals, visits or independent observations.

## Time and cached editions

All comparisons and the elapsed-hour boundary are in UTC. The local-day boundary
is calculated using `zoneinfo.ZoneInfo` and converted to UTC; it is not UTC
midnight and not `now - 24 hours`. Both halves are independently filtered from the
union query. Across midnight a last-hour bird may be absent from today's list.

Cached data retain their original snapshot timestamp, local date, daily boundary
and hourly boundary. They are visibly marked cached/offline. The client does not
claim coverage throughout a window because no historical capture-coverage query
is made. A time with no qualifying IDs is not inferred to be a silent garden.

## Optional after-dark enrichment

The day scan is unchanged. With `night_mode` enabled, Garden Ink also reads:

- `/api/v1/debug/pipeline`: station coordinates and current BirdNET/ultrasonic worker health. Only those fields are retained.
- `/api/v1/detections`: separately bounded bird and generic-bat scans, preserving review/source/withdrawal filtering. Generic `ultrasonic-pass-v1` bat records do not require a species rank; their score threshold is configured separately.
- `/api/v1/history`: frame-bounded microphone coverage, sample rates and deliberate pauses. Counts/charts are reduced from filtered raw records rather than the endpoint's roll-ups.

Coverage stream `discontinuity_count` is a lifetime counter. The window's `estimated_missing_frames` is converted to a conservative duration loss; unknown-length gaps suppress completeness. Recording and worker health are checked independently before a new night transition. The API does not expose historical detector effort, so unsupported historical zeros remain gaps. Errors in this enrichment leave daytime operation available and cannot trigger a new night latch. See [night mode](../../docs/design/NIGHT_MODE.md).
