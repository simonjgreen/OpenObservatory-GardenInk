#!/usr/bin/env bash
# Native distro packages work on the ARMv6 Pi Zero; no pip/venv or compilation.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
SKIP=0
if [[ ${1:-} == --skip-apt ]]; then SKIP=1; shift; fi
URL=${1:-}
if [[ $# -gt 1 ]]; then echo 'Usage: ./install.sh [--skip-apt] [http://STATION:8080]' >&2; exit 2; fi
if [[ $EUID -eq 0 ]]; then SUDO=(); else SUDO=(sudo); fi
if [[ $SKIP -eq 0 ]]; then
  echo 'Installing Python, Pillow, SPI/GPIO libraries, system fonts and timezone data...'
  "${SUDO[@]}" apt-get update
  "${SUDO[@]}" apt-get install -y python3 python3-pil python3-spidev python3-gpiozero fonts-dejavu-core fonts-dejavu-extra tzdata
fi
/usr/bin/python3 - <<'PY'
import sys
if sys.version_info < (3,9): raise SystemExit('Python 3.9+ is required (Raspberry Pi OS Bullseye or newer).')
import PIL,spidev,gpiozero
from zoneinfo import ZoneInfo
ZoneInfo('Europe/London')
print('Python packages OK.')
PY
LOGIN_USER=${SUDO_USER:-$(id -un)}
for grp in spi gpio; do
  if getent group "$grp" >/dev/null; then "${SUDO[@]}" usermod -aG "$grp" "$LOGIN_USER"; fi
done
if command -v raspi-config >/dev/null; then
  "${SUDO[@]}" raspi-config nonint do_spi 0
else
  echo 'raspi-config not found: enable SPI0 in your OS before a hardware run.'
fi
chmod +x run.sh service.sh test.sh dashboard.py
if [[ -n $URL ]]; then
  /usr/bin/python3 dashboard.py --configure "$URL"
elif [[ ! -f config.json ]]; then
  if [[ -t 0 ]]; then
    read -r -p 'OpenObservatory station URL (e.g. http://YOUR-STATION:8080): ' URL
    if [[ -n $URL ]]; then /usr/bin/python3 dashboard.py --configure "$URL"; fi
  fi
fi
if [[ $EUID -eq 0 && $LOGIN_USER != root ]]; then
  # Only the app's own config/state, never recursively chown an arbitrary directory.
  [[ ! -f config.json ]] || chown "$LOGIN_USER:$(id -gn "$LOGIN_USER")" config.json
fi
printf '\nInstalled. Reboot once if SPI was disabled; reconnect SSH for new group membership.\n'
printf 'API check:    ./run.sh --check\n'
printf 'First frame:  ./run.sh --once\n'
printf 'Always-on:    ./service.sh install\n'
printf 'Offline demo: ./run.sh --demo --preview\n'
