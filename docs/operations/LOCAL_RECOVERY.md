# Preserve and recover local state

The repository contains application source and bundled artwork. Machine-local configuration, credentials, paid generations and approval/spending state belong to the installation and are excluded from Git.

| Location | Preserve |
|---|---|
| Workstation studio | `output/` including raw/prepared/archive files and `state.json`; exact `species.json`, `STYLE_BRIEF.txt`, `reference/robin.png`; finished art ZIP |
| Pi | Deployed source, configuration, tokens and `.secrets/` privately; custom artwork/manifests; refresh/snapshot state; coherent auto-art ledger and image directories |
| Printing workstation | Revised CAD, slicer project, print settings, cable dimensions and measured fit notes |

## Import an existing studio

Stop all studio generation/review/export processes. From the project root:

```bash
.venv/bin/python tools/import_workstation_art.py /path/to/existing/art_studio
# Inspect the plan, then explicitly apply it:
.venv/bin/python tools/import_workstation_art.py /path/to/existing/art_studio --apply
cd art_studio
PYTHON=../.venv/bin/python bash art.sh list
PYTHON=../.venv/bin/python bash art.sh generate --set all --plan
```

The importer selects output, catalogue, style/reference and finished art ZIP. It excludes credentials, virtual environments and old code. Existing destination material is backed up under gitignored `local/import-backups/`. Both studio locks are checked; nested directories and symlinks are refused. Wait for running work rather than deleting a lock.

Import request fields together with images: species-specific notes, model settings and reference bytes determine fingerprints. Preserve approvals, uncertain states and rejected attempts. List/plan do not make API calls. A timeout may have incurred a charge; inspect saved raw files and use explicit recovery before considering a new paid request.

## Pi recovery

Make a complete private backup with services stopped as described in [deployment](DEPLOYMENT.md). A separate comparison copy can live under gitignored `local/pi-snapshot/`. Exclude `.secrets/`, token files, environment files and any custom credential paths from copies intended for sharing. Review configuration and logs for site details as well.

Gitignore is not encryption. Do not upload private snapshots. Compare source separately and install reviewed artwork through its importer. Keep `state/autoart/jobs.sqlite3` and any required WAL/SHM files coherent; it contains request reservations, spending and recovery history. Keep `state/display.json` so upgrades preserve the physical cooldown.
