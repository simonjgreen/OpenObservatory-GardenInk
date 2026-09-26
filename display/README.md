# Garden Ink display

The Pi application for the [Open Observatory](https://github.com/simonjgreen/OpenObservatory) e-ink companion. A reachable Open Observatory station supplies observations; this application provides the alternative hourly display interface.

See the [project README](../README.md), [deployment guide](../docs/operations/DEPLOYMENT.md) and [API contract](docs/API_CONTRACT.md).

```bash
./run.sh --demo --preview     # invented sample data; no network or GPIO
./run.sh --preview            # station data to PNG; no GPIO
./run.sh --check              # station diagnostics; no GPIO
./run.sh --once               # physical edition, respecting saved cooldown
./service.sh status
./service.sh diagnose
```

The layout is 480 × 800 portrait for the Waveshare HAT (E), with a date and historical report times. The refresh interval is approximately 3,600 seconds. Today starts at local midnight; the last hour is 60 elapsed minutes.

Missing-art generation is disabled by default. Read [automatic artwork](../docs/operations/AUTOART.md) before enabling paid requests. Custom artwork takes precedence over generated cache and bundled images.

`test.sh` runs the display suite. Use `make test` at the repository root for all current suites. `upgrade.sh` is a legacy v1-to-v2 migration helper, not a general deployment command.
