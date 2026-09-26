# Development

Use a root workstation virtual environment, Python 3.9+ and Pillow. DejaVu fonts, including the italic faces in `fonts-dejavu-extra`, must be installed separately. Pi GPIO dependencies are installed by `display/install.sh`, not the workstation requirements.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
make test PYTHON=.venv/bin/python
make preview PYTHON=.venv/bin/python
make verify PYTHON=.venv/bin/python
```

`tools/test_all.py` runs display, auto-art, studio and project suites in separate processes. Tests use local mock HTTP servers and mocked paid responses. Credential environment variables are removed before subprocesses start. Logs go under ignored `local/test-results/`.

`make preview` renders labelled sample data at 480 × 800 into `local/previews/no-clock.png`, without GPIO, station access or paid requests. Review at actual size. For layout changes include empty/quiet, long names, unknown art, midnight, DST, offline/paused and partial-window cases. `make verify` runs the same offline tests and preview; it is not a live-device certification.

## Services

Use the scripts' `print-unit` and `verify` commands on a configured temporary installation to validate generated units with `systemd-analyze verify`. Do not install or restart live services as a workstation check. Stop timeouts allow in-flight scans, refreshes and paid requests to finish.

## Artwork and persistence

Use the exact original robin reference. Preserve existing paid output and fingerprints through [local recovery](../operations/LOCAL_RECOVERY.md). No paid requests belong in tests or routine previews. Do not reset cooldowns, spending counters or uncertain attempts to make checks pass.

## CAD

`make cad-check` checks the nine printable meshes using the optional `requirements-cad.txt` dependencies. Regeneration and collision checks are described in the [mechanical guide](../design/MECHANICAL.md). CAD passes do not establish physical fit or safety.

## Publishing

Keep secrets, site configuration, observation logs, artwork ledgers, private backups and generated local output out of commits. Review staged files and image metadata before pushing. Use a GitHub no-reply commit email. CI runs the offline tests and preview only.
