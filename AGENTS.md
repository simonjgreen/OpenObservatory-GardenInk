# Garden Ink / Counterframe: agent instructions

Read `README.md`, `docs/STATUS_AND_BACKLOG.md`, then the relevant document in `docs/INDEX.md`. Garden Ink depends on Open Observatory and maintains an existing appliance and paid artwork collection.

## Source of truth
- Active app: `display/`. Active workstation generator: `art_studio/`.
- Mechanical master: `hardware/counterframe/counterframe.scad`.
- Current visual target = editorial layout in `design/concepts/04-selected-editorial-target.png`, **minus its clock**; actual latest layout in `design/previews/v2.1/no_clock.png`; required art reference is `art_studio/reference/robin.png`.
- `local/` is private and gitignored. Preserve backups and paid-generation state; never publish them.

## Non-negotiables
1. No free-standing clock or implied live time. Use a date and explicitly historical report/observation times.
2. Hourly refresh; local-midnight today and trailing 60 minutes; DST and midnight must remain correct. Do not bypass the persisted hardware cooldown or reset counters to make a test pass.
3. Say heard/acoustic identification, never count detections as birds, visits or songs. Preserve source/review/withdrawal filtering and honest partial totals.
4. One original robin reference for all art. Do not restore procedural/geometric art as the desired style, chain generated references or silently change model/settings. API success is not anatomy validation.
5. No paid calls in tests, previews or during routine code edits. Only explicitly authorised production generation may use a key. No automatic resend of an uncertain paid request.
6. Never print/read/share real tokens unnecessarily, commit `.secrets`, copy a private key to fixtures or delete `state/autoart/jobs.sqlite3`. It contains spending and recovery history.
7. The Pi's curated images and workstation raw/prepared/approved collection must be imported, not regenerated. See `docs/operations/LOCAL_RECOVERY.md`.
8. Keep the working HAT (E) hardware driver unchanged absent a specific reason and hardware verification. Other Waveshare variants are not interchangeable.
9. CAD remains screwless, structural PLA only, portrait, freestanding, one external Pi power lead, safe flex routing, no glass preload. Regenerate all mating parts after dimension changes.
10. Do not claim physical testing, live-station testing or paid API validation from mocked tests or conceptual renders.

## Safe commands
From the project root, with Pillow installed:
```
make test PYTHON=.venv/bin/python
make preview PYTHON=.venv/bin/python
make verify PYTHON=.venv/bin/python
```
`make verify` runs offline tests and a sample preview. Tests contact local mock HTTP servers only. Put a workstation venv at the repo root, not inside `display/`.

## Change discipline
Prefer a small, reviewed fix over replacing the application or adding infrastructure. Record user-facing decisions and update the relevant tests/docs. Validate generated systemd units using `systemd-analyze verify`; do not install or restart live services without approval. For display tests, render actual 480×800 output and inspect it, not an AI concept.

Read the scope of the legacy upgrader and CAD packaging scripts before running them; they can overwrite files.

Workstation studio parallelisation is **not implemented**: it still owns one JSON state file and one lock. The Pi auto-art service has up to two workers; those are different tools. A proposed four-worker studio must keep one state coordinator, preserve fingerprints/approvals and explicitly account for uncertain requests.
