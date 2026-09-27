# Architecture and ownership

## The full system

```text
Garden microphone + detector station (OpenObservatory; separate repository)
    GET /api/v1/health and GET /api/v1/detections
             |
             v
Pi Zero: garden-ink.service                  Developer workstation
  bounded newest-first scan                 art_studio/studio.py
  canonical source/review filtering           manual, explicitly paid generation
  independent today/last-hour aggregation     one original robin reference
  no-clock Pillow renderer                    raw/prepared images + JSON state
  palette pack + single SPI owner              human approval + alias-aware ZIP export
             |                                           |
             v                                           v
  800×480 native panel buffer <--- local curated assets/custom/*.png
  hourly refresh, controller sleeps
             |
  metadata-only missing-art queue (real successful frames only)
             v
  state/autoart/jobs.sqlite3
             |
             v
Pi Zero: garden-ink-art.service (separate; optional)
  disabled until explicit paid opt-in
  two request workers, globally spaced starts, durable request-slot reservations
  OpenAI /v1/images/edits with robin reference
  raw response -> local preparation -> candidate/review -> published PNG
             |
             +----> state/autoart/images/ (display watches relevant missing art)
```

No browser, Docker, database server, image model runtime or display server is required on the Zero. The detection station remains the authority for acoustic records and human reviews. Generation is remote; the Zero does not run a generative model.

## Module map (`display/gardenink/`)

| Module | Owns |
|---|---|
| `config.py` | Validated settings, root path, URL normalisation, local token lookup and source/filter identity. |
| `client.py` | Bounded HTTP GETs, health parsing, pagination, tie handling, incremental reduction and completeness proof. |
| `model.py` | UTC/local time boundaries, eligibility, per-window species aggregation, status semantics. |
| `storage.py` | Atomic metadata and cached/empty snapshots; cached data retain their original bounds. |
| `render.py` | 480×800 no-clock composition, scientific/common names, historical times, current gallery compatibility. |
| `palette.py` | Native palette mapping, portrait rotation and packed two-pixels-per-byte transmission buffer. |
| `hardware.py` | The known-working HAT (E) reset/register/refresh/sleep path, GPIO import isolation and BUSY timeout. |
| `app.py` | CLI, global hardware lock, on-the-hour report scheduling, relevant-artwork redraws, persisted panel cooldown, snapshot/image saves and metadata-only post-frame enqueue. |
| `artfiles.py` | Canonical scientific-name handling and custom/generated/bundled asset lookup. |
| `autoart.py` | SQLite job/attempt state, concurrency, spending reservations, publish/recover behaviour. |
| `image_request.py` | Fixed-provider HTTPS request, reference/style fields, decode/preparation safeguards and error classification. |
| `autoart_cli.py` | Explicit enable/disable/key setup, worker, inspection, approval, rejection, retry/recovery/resume. |
| `demo.py` | Explicitly invented examples for offline rendering/tests. |

The workstation studio is intentionally separate and has its own original prompt fingerprint and state format. Sharing the artistic reference does not make the two recovery ledgers interchangeable.

## Time and counting contracts

Daytime page selection defaults to Journal, with Gallery during the local 10:00–10:59 and 14:00–14:59 editions (`gallery_hours: [10, 14]`). Normal hourly updates return to Journal at 11:00 and 15:00. Selection uses the current edition time in the configured timezone, so startup/manual reports during a slot agree with the scheduled report and DST changes preserve the local hours. It adds no refreshes or timers. A qualifying/latched night page takes precedence. Existing explicit alternating rotation takes precedence over the daily slots; `layout: gallery` still keeps Gallery outside the slots. Set `gallery_hours: []` to disable the slots, or supply other distinct integer hours from 0 to 23. `--layout` disables the daily slots for that run, retaining the existing night/rotation priority. Artwork-only redraws retain their original layout. Changing these display-only hours does not invalidate cached observations or the night latch.

On startup/restart, the service requests a fresh frame after a persisted 180-second minimum between attempts. With the default `refresh_seconds: 3600`, subsequent automatic reports start fetching at local `HH:00`, including local midnight and both occurrences of an autumn repeated hour. Long-running cycles skip missed boundaries rather than replaying them; clock corrections re-align the schedule.

Fetching, rendering and physical panel refresh take time: `HH:00` is the start of the update cycle, not a promise that the pigment has settled. Scheduled frames retain the configured interval between attempts. Startup and explicit `--refresh-now` requests use the 180-second minimum, checking the saved attempt time before fetching and again before driving the panel. They persist `attempt_kind: push` before hardware access; the next scheduled frame may resume after that minimum rather than being delayed by another full interval. Failed attempts receive the same protection, counters are never reset, and a backward clock correction restarts the applicable guard. `./service.sh refresh` safely restarts the service to request its startup frame. `--refresh-now` is a one-frame CLI command for use with the service stopped; `--once` retains the ordinary saved interval. Previews and checks remain immediate and do not touch hardware.

The report endpoint is fixed once per edition, preferably anchored to the station health timestamp. Queries cover the union of local today and the last hour, so shortly after midnight yesterday's final minutes may feature above an empty daily list. Event starts at the left edge are included; the report endpoint is exclusive. All arithmetic is timezone-aware.

Between reports the display checks missing image slots every 30 seconds. A newly published image for a pictured species redraws the same snapshot and layout after the persisted 180-second guard; it does not fetch observations, advance the report date, rotate layouts or queue paid work. Text-only mentions and species outside the current page do not trigger redraws. Candidates awaiting review are outside the artwork lookup. The next scheduled report takes priority over pending artwork, including at midnight; custom report intervals also keep their existing deadline. Hardware successes still increment `cycle`, while `edition` tracks report/layout progression independently. Artwork attempts persist `attempt_kind: artwork` before driving the panel, so the next report retains the minimum guard without waiting another full reporting interval.

Counts are records, never population estimates. Unreviewed model results use `min_score` (0.75 default); low-score human confirmations/corrections remain eligible, so the client must not naively filter them out at the server. Synthetic/replay/unknown streams, non-birds, withdrawn/rejected claims and malformed corrections are excluded. No claim of complete historical microphone coverage is made.

Partial data are not silence and do not become exact totals. Each window has its own completeness flag.

## Persistence boundaries

| Path on Pi | Meaning | Preserve during upgrade? |
|---|---|---|
| `config.json` | Site URL, filters, orientation and timezone | Yes |
| `token.txt` or configured token path | OpenObservatory credential | Yes, privately |
| `.secrets/openai-api-key` | OpenAI credential | Yes, privately |
| `autoart.json` | Opt-in and request limits | Yes |
| `assets/custom/` + manifests/catalogue | Reviewed/custom illustration library and aliases | Yes |
| `state/display.json` | Last physical attempt/cooldown | Yes |
| `state/snapshot.json` | Last report for offline rendering | Yes |
| `state/autoart/jobs.sqlite3` (+ WAL/SHM while active) | Durable job and spending history | Yes; coherent backup |
| `state/autoart/raw`, `candidates`, `images` | Paid output/review/publication | Yes |

Deleting the ledger or cooldown is not a supported fix for a failing request or a waiting display. Back up stopped services or use a coherent SQLite backup; do not copy only the main database while discarding an active WAL.

## Hardware/software boundary

The case uses an eight-wire SPI/power connection, not a HAT stacked on the Pi's 40-pin header. Power is one external micro-USB connection to Pi PWR IN. Device bounds and cable geometry in CAD are nominal approximations. The wiring authority for this project is [mechanical guide](design/MECHANICAL.md), the vendor references in the construction guide, not the simplified wire colours in the CAD render.

## After-dark reports

`solar.py` calculates local sunset/sunrise instants. `night_client.py` adds bounded, filtered night scans using the existing read-only transport; `night.py` owns bat policy, recording coverage, reduction and pure edition selection. `night_render.py` renders the three portrait pages, with `night_demo.py` supplying labelled offline fixtures. The day client remains independent for artwork-worker compatibility.

The display stores its night latch/page under `night` in `state/display.json` only after a successful hardware refresh. An attempted frame still saves its physical cooldown first. Artwork-only redraws retain the report and page. Failed night reads can retain the original cached night bounds, explicitly labelled as cached. Missing data cannot create a latch. See [night mode](design/NIGHT_MODE.md).
