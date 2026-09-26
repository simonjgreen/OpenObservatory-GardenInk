#!/usr/bin/env bash
# Garden Ink service installer, fixed 2026-09-25.
# WorkingDirectory is a path setting, not an ExecStart shell-style argument.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
cd -- "$ROOT"
NAME=garden-ink.service
ACTION=${1:-status}
if [[ $EUID -eq 0 ]]; then SUDO=(); else SUDO=(sudo); fi
TMP=''
cleanup() { [[ -z "$TMP" ]] || rm -rf -- "$TMP"; }
trap cleanup EXIT

prepare_unit() {
    [[ "$ROOT" =~ ^[a-zA-Z0-9_./@+-]+$ ]] || {
        echo 'Use a simple absolute installation path, such as /home/pi/garden_ink.' >&2
        echo 'Whitespace, quotes, percent signs and backslashes are not supported by this installer.' >&2
        exit 1
    }
    [[ -f "$ROOT/dashboard.py" && -f "$ROOT/config.json" ]] || {
        echo 'Run this inside a configured Garden Ink installation.' >&2; exit 1;
    }
    /usr/bin/python3 -c 'import sys; from pathlib import Path; from gardenink.config import load; load(Path(sys.argv[1])).validate()' "$ROOT/config.json"
    LOGIN_USER=${SUDO_USER:-$(id -un)}
    [[ "$LOGIN_USER" != root ]] || {
        echo 'Run as the normal Pi login user, not a root-only session.' >&2; exit 1;
    }
    [[ "$LOGIN_USER" =~ ^[a-zA-Z_][a-zA-Z0-9_-]*\$?$ ]] || { echo 'Unsupported service username.' >&2; exit 1; }
    id "$LOGIN_USER" >/dev/null
    mkdir -p -- "$ROOT/state"
    TMP=$(mktemp -d)
    cat > "$TMP/$NAME" <<UNIT
[Unit]
Description=Garden Ink - hourly illustrated garden journal
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=$LOGIN_USER
WorkingDirectory=$ROOT
ExecStart=/usr/bin/python3 "$ROOT/dashboard.py" --config "$ROOT/config.json"
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1
Restart=on-failure
RestartSec=60
TimeoutStopSec=900
NoNewPrivileges=true
ProtectSystem=full
ProtectHome=read-only
ReadWritePaths=$ROOT/state
UMask=0077

[Install]
WantedBy=multi-user.target
UNIT
}

verify_unit() {
    command -v systemd-analyze >/dev/null || {
        echo 'systemd-analyze is required to validate the service before installation.' >&2; exit 1;
    }
    echo 'Validating candidate unit (no system service file changed yet)...'
    systemd-analyze verify "$TMP/$NAME"
    echo 'Candidate unit passed systemd-analyze verify.'
}

diagnostics() {
    echo '--- Service status ---'
    "${SUDO[@]}" systemctl --no-pager --full status "$NAME" || true
    echo '--- Installed unit and overrides ---'
    "${SUDO[@]}" systemctl --no-pager cat "$NAME" || true
    echo '--- Unit file validation ---'
    "${SUDO[@]}" systemd-analyze verify "/etc/systemd/system/$NAME" || true
    echo '--- Recent service logs ---'
    "${SUDO[@]}" journalctl -u "$NAME" -n 60 --no-pager || true
}

case "$ACTION" in
  print-unit) prepare_unit; cat "$TMP/$NAME" ;;
  verify) prepare_unit; verify_unit ;;
  install)
    prepare_unit
    verify_unit
    if [[ $EUID -ne 0 ]]; then sudo -v; fi
    if "${SUDO[@]}" test -f "/etc/systemd/system/$NAME"; then
        BACKUP="/etc/systemd/system/$NAME.backup-$(date +%Y%m%d-%H%M%S)-$$"
        "${SUDO[@]}" cp -p -- "/etc/systemd/system/$NAME" "$BACKUP"
        echo "Previous unit backed up to $BACKUP"
    fi
    "${SUDO[@]}" chown "$LOGIN_USER:$(id -gn "$LOGIN_USER")" "$ROOT/state"
    "${SUDO[@]}" chmod 700 "$ROOT/state"
    "${SUDO[@]}" install -m 0644 -- "$TMP/$NAME" "/etc/systemd/system/$NAME"
    "${SUDO[@]}" systemctl daemon-reload
    # Clear the original bad-setting/start-limit state before trying again.
    "${SUDO[@]}" systemctl reset-failed "$NAME" 2>/dev/null || true
    "${SUDO[@]}" systemctl enable "$NAME"
    if ! "${SUDO[@]}" systemctl restart "$NAME"; then
        diagnostics; exit 1
    fi
    sleep 2
    if ! "${SUDO[@]}" systemctl is-active --quiet "$NAME"; then
        diagnostics; exit 1
    fi
    echo 'Installed, enabled at boot, and currently active.'
    echo 'The application still respects its saved one-hour display cooldown.'
    echo 'Logs: ./service.sh logs  |  Diagnose: ./service.sh diagnose'
    "${SUDO[@]}" systemctl --no-pager --full status "$NAME"
    ;;
  start|stop|restart) "${SUDO[@]}" systemctl "$ACTION" "$NAME" ;;
  status) "${SUDO[@]}" systemctl --no-pager --full status "$NAME" ;;
  logs) "${SUDO[@]}" journalctl -u "$NAME" -f ;;
  diagnose) diagnostics ;;
  remove)
    "${SUDO[@]}" systemctl disable --now "$NAME" || true
    "${SUDO[@]}" rm -f -- "/etc/systemd/system/$NAME"
    "${SUDO[@]}" systemctl daemon-reload
    echo 'Service removed. Application, credentials, state and screen image retained.'
    ;;
  *) echo 'Usage: ./service.sh install|verify|print-unit|start|stop|restart|status|logs|diagnose|remove' >&2; exit 2 ;;
esac
