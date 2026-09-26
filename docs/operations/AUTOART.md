# Automatic missing artwork

Optional paid generation runs separately from the display and is disabled by default. Use the current application in `display/`; see [deployment](DEPLOYMENT.md) for installation.

## Opt into automatic missing artwork

Unattended paid requests are **disabled by default**. The Pi requires internet access for a *new* illustration; ordinary observation fetching still uses your local station, and cached/curated art works offline from OpenAI.

From your configured Pi installation:

```bash
cd ~/garden_ink
./autoart.sh enable
./autoart-service.sh install
./autoart.sh scan
```

`enable` shows the model, limits, data being sent and automatic-publication choice. It requires typing `ENABLE`, then prompts for the key without echo. The key is saved on the Pi as `~/garden_ink/.secrets/openai-api-key`, inside a mode-700 directory; the file has mode 600. Do not send it in chat. A dedicated API project/key is preferable to reusing a widely shared credential.

If a valid saved key exists, it is reused. Use `./autoart.sh enable --replace-key` to replace it. This is a separate credential from OpenObservatory's optional token. Do not put either into the other's configuration.

`autoart-service.sh install` enables the separate `garden-ink-art.service` worker at boot. `autoart.sh scan` fetches the station once and queues eligible missing species without refreshing the physical screen. It is optional: the display will also queue eligible gaps after each successful real hourly update. Check/preview/demo commands do not queue paid work.

### How it works

1. Use your already-filtered real-microphone bird identifications, respecting the display's score and human-review handling.
2. Require at least **three qualifying detection records** in today/the hour for unreviewed species; a reviewed latest identification can bypass this extra generation gate. This limits spending on isolated guesses; it does not prove an identification correct.
3. Resolve scientific-name aliases and look for an existing custom, automatically cached or bundled image. Existing artwork is **not regenerated**. This is gap filling, not a replacement for installing the consistent collection you already generated.
4. Prioritise the main illustration and four daily cards, then other qualifying species encountered in the two windows.
5. Queue once per canonical species in SQLite. Fresh observations refresh eligibility but never reset a completed, failed, rejected or uncertain job. Jobs not observed in the preceding 24 hours, or belonging to an old station/filter configuration, do not start automatically.
6. A separate process performs the image edit using the **same original robin PNG** and the same original style brief. Every request also asks for one bird with exactly two legs and at most two visible feet. Completed images never become the next style reference.
7. Keep the raw response and preparation metadata, prepare a white-background PNG, and publish it atomically to the local generated-art cache. A suspect clipped/full-background image is held for inspection instead of being auto-published.
8. A published image is picked up at the **next scheduled hourly display refresh**. Generation never blocks the current refresh and never triggers an additional physical refresh.

### What leaves the Pi

The fixed request goes to `https://api.openai.com/v1/images/edits`. It includes the scientific bird name, standard artistic instructions (and an optional operator correction note), and the reference robin PNG. Known catalogue species may use the catalogue's standard common name and pose instructions.

It does **not** send the audio, your station's URL, coordinates, detection times, counts, screenshots or credentials to the prompt. The API key is sent only as authentication to OpenAI over verified HTTPS; redirects are refused. No other model, image search, or fallback provider is called. Standard system HTTPS proxy configuration may apply if you configured one yourself.

The model stays pinned to `gpt-image-2-2026-04-21`, high quality, 1536 × 1024, one image per call. Input fidelity is not set for this model. We deliberately do not switch an existing consistent collection to a newer model alias.

## Cost and concurrency controls

Default settings in `autoart.json`:

```json
{
  "enabled": false,
  "model": "gpt-image-2-2026-04-21",
  "max_requests_per_24h": 2,
  "max_requests_total": 20,
  "workers": 2,
  "min_detections": 3,
  "timeout_seconds": 1200,
  "auto_publish": true
}
```

Once enabled, two independent requests may be in flight; starts are spaced at least 15 seconds apart. Local PNG preparation is serialised to limit memory use on a Pi Zero. This is not the old serial 53-image production loop.

Limits count **reserved attempt slots**, including failed and uncertain calls, and persist in SQLite across service restarts. A slot is recorded before submitting a paid request. A crash before submission can therefore conservatively consume a slot even though no call was sent. The rolling-24-hour cap avoids doubling at midnight. The total cap prevents an unattended appliance spending forever. These are **request-count caps, not exact currency caps**; billing depends on the model's actual input/output usage.

When a cap is reached, the display continues normally. Pending jobs wait; they are not discarded. Increase a limit deliberately, for example:

```bash
./autoart.sh enable --daily-limit 4 --total-limit 40
```

Previously used attempts remain counted; raising the total to 40 does not reset the counter. Do not delete the database to clear an error or “fix” a cooldown: that would erase both recovery and spending history.

## Anatomy and visual review

Automatic generation is not automatic anatomical or taxonomic validation. The software can verify file type, dimensions, blank output and crude edge clipping, **not whether a drawing has an extra leg or the correct plumage**. A diagram-perfect PNG can still be biologically wrong.

After opting in normally, useful-looking new PNGs are published automatically. They remain AI-generated decorative illustrations, not captured evidence or human-approved field-guide plates. A visible name on the display remains the acoustic classifier/reviewer's claim, not validation supplied by the illustration.

For generation without automatic publication:

```bash
./autoart.sh enable --review-required
```

This still generates and caches the missing image automatically, but you must approve it before it appears on the display. It does not retrospectively remove already published images.

To inspect:

```bash
./autoart.sh status
./autoart.sh review
```

`status` shows settings, counters, per-species state and provider pause state; it never prints the key. `review` writes `state/autoart/review.html` with local candidate images and no remote scripts/resources. Copy that directory to your workstation to browse it (no API key lives in that directory):

```bash
scp -r USER@DISPLAY-PI:~/garden_ink/state/autoart ./garden-ink-art-review
```

For operator edits, stop the artwork worker first; the display service can remain running. Commands deliberately refuse to race an in-flight generation:

```bash
./autoart-service.sh stop
./autoart.sh approve "Certhia familiaris"
./autoart-service.sh start
```

To reject a poor **auto-generated** image and explicitly queue a new paid attempt:

```bash
./autoart-service.sh stop
./autoart.sh reject "Certhia familiaris"
./autoart.sh retry "Certhia familiaris" --note "Exactly two legs; avoid duplicate feet. Preserve the reference drawing style."
./autoart-service.sh start
```

The retry asks for confirmation, preserves old raw/candidate files, and still obeys the request caps. It does not overwrite a separately installed custom or bundled image. For replacing an existing curated/bundled illustration, use the workstation art-studio regeneration workflow and install its approved result as before.

## Failure behaviour

- **Timeout, connection loss, invalid response or interrupted worker:** mark the attempt uncertain; no automatic POST retry. A request may already have been processed/charged.
- **Raw response saved, local preparation interrupted:** keep it. Worker restart can attempt local preparation without another API call. Manual recovery: stop the art worker and run `./autoart.sh recover "Scientific name"`.
- **Authentication, access/model errors, quota/rate response:** pause new requests across the queue. Already in-flight requests may finish. The display still works. Resolve the problem, then run `./autoart.sh resume`. Failed/uncertain species need a separate explicit `retry`; resuming does not resend them.
- **Unexpected drawing:** reject locally. There is no silent paid “try until good” loop.
- **No network/OpenAI issue:** observation display is unaffected. Missing imagery remains a labelled botanical fallback until a usable image is available.
- **Service restart:** previously requesting jobs become uncertain, not queued. Raw files from a completed response can be recovered locally.

To turn off paid requests:

```bash
./autoart.sh disable
```

This prevents new requests; one already in flight may still finish and save its image. Cached/curated images remain available. To stop the worker process as well: `./autoart-service.sh stop` (allows in-flight work to finish).

## File locations and service isolation

- `autoart.json`: opt-in policy, not a secret.
- `.secrets/openai-api-key`: owner-only credential; do not include it in publicly shared backups.
- `state/autoart/jobs.sqlite3`: durable job and attempt ledger, including spending limits' history.
- `state/autoart/raw/`: raw PNG responses and metadata, named by species and attempt ID.
- `state/autoart/candidates/`: prepared images awaiting/recovering from review.
- `state/autoart/images/`: published generated-art cache.
- `assets/custom/`: existing curated artwork. This always takes precedence, including mapped scientific aliases.
- `autoart_reference/`: fixed original robin, common style brief and species guidance.

Both services run under the normal Pi user. The art worker can write only under the application's `state/` directory in its systemd filesystem sandbox, has private devices, and has no panel/GPIO dependency. The application/reference/key directories are read-only to it. These are defence-in-depth settings, not a promise to withstand a compromise of the same Pi user. The worker does not control the physical display.

Services:

```bash
./service.sh status
./service.sh logs
./autoart-service.sh status
./autoart-service.sh logs
./autoart-service.sh diagnose
```

Reinstalling/removing the art service does not erase images, the key or counters. Keep your installation path stable.
