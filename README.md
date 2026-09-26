# Open Observatory · Garden Ink

An illustrated e-ink display for [Open Observatory](https://github.com/simonjgreen/OpenObservatory), powered by a Raspberry Pi Zero in a 3D-printed enclosure.

**Garden Ink expands on and depends on Open Observatory.** It provides an alternative indoor interface to the outdoor station's acoustic detections. Open Observatory handles recording, identification and review; Garden Ink reads its API and turns those records into an hourly garden journal.

<p align="center"><img src="docs/images/garden-ink-device.jpg" width="540" alt="Garden Ink running on a portrait e-ink screen in its white printed Counterframe enclosure"></p>

*The assembled device running the current no-clock layout. Bird illustrations accompany acoustic identifications; they are not photographs of observed birds.*

## What it does

- Shows the latest qualifying identification from the last hour, alongside four other frequent species heard today.
- Refreshes approximately every hour, with a date and clearly historical report/observation times.
- Preserves local-midnight and daylight-saving boundaries, review decisions, source filtering and honest partial totals. Detection counts are records, not numbers of birds or visits.
- Uses a Waveshare 7.3-inch Spectra 6 **HAT (E)** in 480 × 800 portrait orientation.
- Runs locally with cached artwork. Optional paid image generation is separate and disabled by default.

The **Counterframe** enclosure is freestanding, screwless and designed for structural PLA, with one external power lead to the Pi. See the [mechanical guide](docs/design/MECHANICAL.md) before printing or wiring.

## Requirements

A running [Open Observatory station](https://github.com/simonjgreen/OpenObservatory) reachable from the display Pi is required for real observations. Garden Ink reads `/api/v1/health` and `/api/v1/detections`; it does not include or replace the station software. See the [API contract](display/docs/API_CONTRACT.md) for compatibility assumptions.

The display requires a Pi Zero, Raspberry Pi OS, the specific HAT (E) panel and SPI wiring. Other Waveshare variants are not interchangeable. Workstation previews require Python 3.9+, Pillow and DejaVu fonts, with no station or API key.

## Try it on a workstation

```bash
git clone https://github.com/simonjgreen/OpenObservatory-GardenInk.git
cd OpenObservatory-GardenInk
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
make test PYTHON=.venv/bin/python
make preview PYTHON=.venv/bin/python
```

On Debian/Ubuntu, install `python3-venv` and `fonts-dejavu-core` and `fonts-dejavu-extra` if needed. Open `local/previews/no-clock.png` for an actual 480 × 800 render using visibly labelled sample observations. These commands make no paid requests and do not touch GPIO or a live station.

## Install on a Pi

Copy `display/` to `~/garden_ink` on a fresh Pi, then run as the normal Pi user:

```bash
cd ~/garden_ink
./install.sh http://YOUR-STATION:8080
./run.sh --check
./run.sh --once
./service.sh install
```

For an existing device, first follow [deployment and backup](docs/operations/DEPLOYMENT.md). Preserve configuration, curated artwork, credentials, refresh state and the artwork spending ledger.

## Artwork

The original [robin](art_studio/reference/robin.png) defines the ink-and-wash style. The bundled 47 images provide coverage but are not yet a consistent final collection. The workstation studio has a 53-species catalogue and supports generation, visual review, approval and export. Import existing paid outputs before generating replacements.

See the [artwork workflow](docs/artwork/WORKFLOW.md), [local recovery](docs/operations/LOCAL_RECOVERY.md) and [optional automatic artwork](docs/operations/AUTOART.md). Ordinary display operation needs no OpenAI key. Generation is explicitly opt-in and paid; a valid image file does not establish correct anatomy.

## Project layout

| Path | Contents |
|---|---|
| `display/` | Pi application, hardware driver, bundled illustrations and display tests |
| `art_studio/` | Workstation artwork tool and original style reference |
| `hardware/counterframe/` | OpenSCAD master, printable parts and illustrated build guide |
| `design/` | Selected visual reference and current renderer baseline |
| `docs/` | Current architecture, setup, maintenance and design guidance |
| `tests/`, `tools/` | Offline regression suites and development helpers |

Start with the [documentation map](docs/INDEX.md). [Status and roadmap](docs/STATUS_AND_BACKLOG.md) separates implemented behaviour from outstanding verification and future work: content quality, refresh timing, readability, power consumption and art style.

## Contributing and licensing

See [CONTRIBUTING.md](CONTRIBUTING.md) for local checks and [SECURITY.md](SECURITY.md) for private reporting. Software is MIT-licensed; the enclosure is CC0. Artwork, photographs and third-party notices have separate terms described in [LICENSE.md](LICENSE.md).
