#!/usr/bin/env bash
# Update an existing Garden Ink directory without replacing secrets or local art.
set -euo pipefail
SOURCE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
TARGET=${1:-"$HOME/garden_ink"}
if [[ $# -gt 1 ]]; then echo 'Usage: bash upgrade.sh [~/garden_ink]' >&2; exit 2; fi
if [[ $EUID -eq 0 ]]; then
  echo 'Run the upgrade as your ordinary Pi login (not sudo). It asks sudo only to stop the service.' >&2
  exit 2
fi
if [[ ! -f "$TARGET/gardenink/hardware.py" || ! -f "$TARGET/config.json" ]]; then
  echo "Not an existing configured Garden Ink installation: $TARGET" >&2
  echo 'For a fresh install, use ./install.sh http://YOUR-STATION:8080 in this package.' >&2
  exit 2
fi
/usr/bin/python3 "$SOURCE/tools/upgrade_installation.py" --validate "$SOURCE" "$TARGET"
if command -v systemctl >/dev/null && systemctl is-active --quiet garden-ink.service; then
  echo 'Stopping garden-ink.service (any in-progress frame is allowed to finish)...'
  sudo systemctl stop garden-ink.service
fi
# The shared display lock also refuses an active foreground run.
/usr/bin/python3 "$SOURCE/tools/upgrade_installation.py" "$SOURCE" "$TARGET"
printf '\nUpgrade installed; the service is intentionally left stopped.\n'
printf 'Next:\n  cd "%s"\n  ./run.sh --check\n  ./run.sh --once\n  ./service.sh install\n' "$TARGET"
