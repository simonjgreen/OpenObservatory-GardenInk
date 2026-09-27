# Deployment

`display/` is the deployable Pi application. It depends on a reachable [Open Observatory](https://github.com/simonjgreen/OpenObservatory) station. CAD and workstation tools do not need to be installed on the Pi.

## Existing installations

Before changing a running device, compare its source with this checkout and make a private backup. Stop the services cleanly, allowing in-flight requests to finish:

```bash
cd ~/garden_ink
./service.sh stop
# If the optional worker is installed:
./autoart-service.sh stop
cd ~
umask 077
tar -czf "garden_ink-private-$(date +%Y%m%d-%H%M%S).tar.gz" garden_ink
```

Keep the backup outside Git. It may contain credentials, observations and paid artwork. An active SQLite database must be backed up coherently with its WAL; a stopped-service copy avoids a partial ledger snapshot.

Preserve `config.json`, `autoart.json`, token paths, `.secrets/`, custom PNGs/manifests/catalogue and all `state/`. See [local recovery](LOCAL_RECOVERY.md). Review and dry-run source synchronisation before copying files. Avoid broad deletion or copying workstation state onto the device. `upgrade.sh` is a legacy v1-to-v2 migration, not a general updater.

After copying only reviewed program files, validate the installation and generated units before restarting. Never clear `state/display.json` or the artwork ledger to force a refresh or retry.

## Fresh installation

Copy `display/` into `~/garden_ink`, then run as the normal Pi user:

```bash
cd ~/garden_ink
./install.sh http://YOUR-STATION:8080
./run.sh --check
./run.sh --once
./service.sh install
```

The installer uses OS packages and may require a reboot/re-login for SPI and group membership. The workstation virtual environment is not a transferable Pi runtime. Configure your own station URL, timezone and optional token locally; these are not committed.

`--check` reads the station without GPIO. `--preview` reads the station and writes an image without GPIO or paid work. `--demo --preview` uses invented data and no network. `--once` drives the panel and honours the persisted cooldown. Do not run unrelated Waveshare demos alongside the service; they do not share its advisory hardware lock.

## Push an update

From the installed application folder, run:

```bash
./service.sh refresh
```

This cleanly restarts the display service and requests a fresh frame. Installation, startup and ordinary service restart now request a frame too, followed by the regular hourly schedule. The request skips hourly timing but retains at least 180 seconds since the last saved panel attempt (successful or failed); it waits before fetching current data when necessary. This is the minimum interval recommended in the [HAT (E) manual](https://www.waveshare.com/wiki/7.3inch_e-Paper_HAT_%28E%29_Manual). No cooldown file or counter is cleared. Use `./service.sh logs` to confirm `Panel asleep` after the refresh; the refresh command returns when the service starts, not when the pigment has settled.

With the service already stopped, `./run.sh --refresh-now` performs one pushed update and exits. It uses the same persisted minimum and advisory hardware lock. `--once` continues to use the ordinary saved interval; preview/check modes cannot be combined with `--refresh-now`.

## Service diagnostics

```bash
./service.sh print-unit
./service.sh verify
./service.sh install
./service.sh status
./service.sh diagnose
./service.sh logs
```

The installer validates the generated unit with `systemd-analyze verify`. `WorkingDirectory` uses an unquoted path; `ExecStart` argument quoting has different rules. After its startup frame, a healthy service with the default hourly cadence waits for the next local `HH:00` before fetching a report. Fetching and physical refresh take time, and the saved panel cooldown can delay the physical attempt further. Controller sleep does not mean the Pi is suspended.

## Optional paid artwork

Read [automatic artwork](AUTOART.md) before running `./autoart.sh enable` and `./autoart-service.sh install`. This is a separate service and spending decision. Validate it on the device with an explicit request budget before unattended use. Offline tests do not submit paid requests.
