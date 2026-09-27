from __future__ import annotations
import argparse
from datetime import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import signal
import sys
import threading
import tempfile
import time
from zoneinfo import ZoneInfo
from .config import ROOT, load, save
from . import __version__
from .client import Client, APIError
from .model import utcnow, iso, status_for
from .storage import atomic_json, cached_or_empty

LOG=logging.getLogger('gardenink')


def atomic_image(path, image):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name+'.', suffix='.tmp', dir=str(path.parent))
    os.close(fd)
    tmp = Path(name)
    try:
        image.save(tmp, format='PNG', optimize=True)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def lock_display():
    import fcntl
    path='/tmp/garden-ink-spi0-ce0.lock'
    flags=os.O_CREAT|os.O_RDWR|getattr(os,'O_NOFOLLOW',0)
    try: fd=os.open(path,flags,0o644)
    except PermissionError: fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except (BlockingIOError,OSError):
        os.close(fd)
        raise RuntimeError('Another Garden Ink hardware process is running. Stop its service first.')
    return fd  # Keep this descriptor alive for the lifetime of the hardware process.


def read_meta(path):
    try:
        value=json.loads(path.read_text())
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError):return {}


def refresh_delay(meta: dict, cfg, wall: float, *, push=False) -> float:
    """Restart-persistent, start-to-start display cooldown.

    The first v2 frame may replace an old v1 frame after the existing 180-second
    hardware guard, so an upgrade doesn't make its first preview wait an hour.
    Scheduled attempts use the configured interval. Explicit pushes and service
    startup retain the 180-second guard. After a push, the next scheduled frame
    may return to the clock-hour schedule after that same minimum guard.
    """
    try:
        previous = float(meta.get('attempted_at', 0))
    except (ValueError, TypeError):
        previous = 0.0
    if not previous:
        return 0.0
    interval = cfg.refresh_seconds if meta.get('attempt_version') in ('2.0.0', __version__) else 180
    if (push or meta.get('attempt_kind') == 'artwork' or
            (meta.get('attempt_kind') == 'push' and cfg.refresh_seconds == 3600)):
        interval = 180
    elapsed = max(0.0, wall - previous)
    return max(0.0, interval - elapsed)


def next_hour(wall: float, timezone: str) -> float:
    """First local HH:00 at or after wall, traversing DST in timestamp order."""
    zone = ZoneInfo(timezone)
    candidate = wall
    while True:
        local = datetime.fromtimestamp(candidate, zone)
        elapsed = local.minute * 60 + local.second + local.microsecond / 1e6
        if elapsed == 0:
            return candidate
        candidate += 3600 - elapsed


def wait_for_hour(cfg, stop) -> bool:
    reason, _ = wait_for_update(cfg, stop)
    return reason == 'scheduled'


def wait_for_update(cfg, stop, artwork_ready=None, scheduled_at=None,
                    previous_wall=None, previous_monotonic=None):
    """Wait for a report deadline or relevant art; the report always wins ties."""
    wall = time.time()
    target = next_hour(wall, cfg.timezone) if scheduled_at is None else scheduled_at
    if previous_wall is not None:
        elapsed = time.monotonic() - previous_monotonic
        # A slow redraw can legitimately cross its deadline. Only a clock
        # correction should move that pending report to a new boundary.
        if wall < previous_wall or abs(wall - previous_wall - elapsed) > 30:
            target = (next_hour(wall, cfg.timezone) if cfg.refresh_seconds == 3600
                      else wall + cfg.refresh_seconds)
    LOG.info('Next scheduled update at %s',
             datetime.fromtimestamp(target, ZoneInfo(cfg.timezone)).isoformat())
    while not stop.is_set():
        remaining = target - wall
        if remaining <= 0:
            return 'scheduled', target
        if artwork_ready is not None and artwork_ready():
            return 'artwork', target
        if stop.wait(min(remaining, 30)):
            return None, target
        current = time.time()
        if current < wall or current > target + 30:
            target = (next_hour(current, cfg.timezone) if cfg.refresh_seconds == 3600
                      else current + cfg.refresh_seconds)
        wall = current
    return None, target


def missing_artwork(snap, layout):
    from .render import artwork_path, illustrated_species
    return [bird for bird in illustrated_species(snap, layout) if artwork_path(bird) is None]


def artwork_ready(missing, meta, meta_path, cfg):
    from .render import artwork_path
    if not any(artwork_path(bird) is not None for bird in missing):
        return False
    wall = time.time()
    # Apply the same backward-clock protection as the final hardware guard.
    if meta.get('attempted_at', 0) > wall:
        meta['attempted_at'] = wall
        atomic_json(meta_path, meta)
    return refresh_delay(meta, cfg, wall, push=True) <= 0


def wait_for_cooldown(meta, meta_path, cfg, stop, *, push=False) -> bool:
    """Keep the physical guard independent of the hourly report schedule."""
    while not stop.is_set():
        wall = time.time()
        try: previous = float(meta.get('attempted_at', 0))
        except (ValueError, TypeError): previous = 0
        if previous > wall:
            LOG.warning('Pi clock moved backwards; restarting the safe refresh interval')
            meta['attempted_at'] = wall
            atomic_json(meta_path, meta)
        remaining = refresh_delay(meta, cfg, wall, push=push)
        if remaining <= 0:
            return True
        if stop.wait(min(remaining, 30)):
            return False
    return False


def choose_report(snap, cfg, meta, edition, now):
    from .night import NIGHT_LAYOUTS, select_edition
    layout, proposed = select_edition(snap, cfg, meta.get('night', {}), now)
    if layout in NIGHT_LAYOUTS:
        # A damaged/expired cache cannot supply a report for a saved latch.
        if (snap.get('night') or {}).get('evening_date') == proposed.get('evening_date'):
            return layout, proposed
    return (('journal', 'gallery')[edition % 2] if cfg.rotate_layouts else cfg.layout), proposed


def check_report(snap: dict, cfg) -> dict:
    from .render import artwork_path
    today, hour = snap['today'], snap['last_hour']
    def counts(window):
        return {key: window[key] for key in ('since','as_of','species_count','record_count',
                                              'incomplete','incomplete_reason','excluded')}
    missing = sorted({b['scientific_name'] for w in (today,hour) for b in w['species']
                      if artwork_path(b) is None})
    return {'version': __version__, 'station': cfg.base_url, 'timezone': cfg.timezone,
            'status': status_for(snap)[1], 'as_of': snap['as_of'],
            'today': counts(today), 'last_hour': counts(hour),
            'refresh_seconds': cfg.refresh_seconds, 'scan': snap.get('scan', {}),
            'artwork_missing': missing, 'error': snap.get('error',''),
            'health_error': snap.get('health_error',''),
            'night': snap.get('night', {}),
            'problems': (snap.get('health') or {}).get('problems',[])}


def main(argv=None):
    ap = argparse.ArgumentParser(description='Garden Ink 2 · heard today / heard in the last hour')
    ap.add_argument('--config', type=Path, default=ROOT/'config.json')
    ap.add_argument('--url', help='Override station URL for this run')
    ap.add_argument('--configure', metavar='URL', help='Save station URL, then exit')
    ap.add_argument('--demo', action='store_true', help='Clearly labelled invented sample data')
    ap.add_argument('--preview', action='store_true', help='Write a PNG; no GPIO and no cooldown')
    ap.add_argument('--output', type=Path, help='PNG output (default state/latest.png)')
    ap.add_argument('--once', action='store_true', help='One physical frame, respecting cooldown')
    ap.add_argument('--refresh-now', action='store_true',
                    help='Push one fresh frame, skipping hourly timing but keeping the 180-second guard; stop service first')
    ap.add_argument('--check', action='store_true', help='Read API and report both windows, no GPIO')
    ap.add_argument('--layout', choices=['journal','gallery'])
    ap.add_argument('--night-page', choices=['rhythm','history','journal'],
                    help='Select a night page for a preview/check only')
    ap.add_argument('--rotation', type=int, choices=[90,270])
    ap.add_argument('--verbose', action='store_true')
    ap.add_argument('--version', action='version', version=__version__)
    args = ap.parse_args(argv)
    if args.night_page and not (args.preview or args.check):
        ap.error('--night-page requires --preview or --check; it cannot force the panel')
    if args.refresh_now and (args.preview or args.check or args.configure):
        ap.error('--refresh-now cannot be combined with --preview, --check or --configure')
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s')
    cfg = load(args.config)
    if args.configure:
        cfg.base_url = args.configure
        cfg.validate()
        args.config.parent.mkdir(parents=True, exist_ok=True)
        save(args.config, cfg)
        print('Saved configuration to', args.config)
        return 0
    if args.url: cfg.base_url = args.url
    if args.layout: cfg.layout = args.layout
    if args.rotation: cfg.rotation = args.rotation
    cfg.validate(require_url=not args.demo)
    state = Path(os.environ.get('GARDEN_INK_STATE_DIR', str(ROOT/'state'))).expanduser()
    state.mkdir(parents=True, exist_ok=True)
    try: state.chmod(0o700)
    except OSError: pass
    cache = state/'snapshot.json'
    client = None if args.demo else Client(cfg, cfg.token(args.config))
    stop = threading.Event()
    def stopping(signum, frame):
        LOG.info('Stopping after any in-progress panel refresh finishes...')
        stop.set()
    signal.signal(signal.SIGINT, stopping)
    signal.signal(signal.SIGTERM, stopping)
    hardware = not (args.preview or args.check)
    single_frame = args.once or args.refresh_now
    hourly = hardware and not single_frame and cfg.refresh_seconds == 3600
    lockfd = lock_display() if hardware else None
    meta_path = state/'display.json'
    meta = read_meta(meta_path)
    cycle = int(meta.get('cycle', 0))
    edition = int(meta.get('edition', cycle))
    try:
        first_frame = True
        missing = []
        report_at = None
        previous_wall = None
        previous_monotonic = None
        while not stop.is_set():
            art_refresh = False
            push = hardware and (args.refresh_now or (first_frame and not args.once))
            # Wait BEFORE querying the station or rendering. A manual --once after
            # an earlier frame must not display a snapshot fetched an hour ago.
            if push:
                LOG.info('Fresh frame requested; honouring the saved 180-second panel guard')
                if not wait_for_cooldown(meta, meta_path, cfg, stop, push=True): break
            elif hardware and not single_frame:
                reason, report_at = wait_for_update(
                    cfg, stop, lambda: artwork_ready(missing, meta, meta_path, cfg),
                    report_at, previous_wall, previous_monotonic)
                previous_wall = time.time()
                previous_monotonic = time.monotonic()
                if reason is None: break
                art_refresh = reason == 'artwork'
                push = art_refresh
            elif hardware:
                wall = time.time()
                try: previous = float(meta.get('attempted_at', 0))
                except (ValueError, TypeError): previous = 0
                if previous > wall:
                    LOG.warning('Pi clock moved backwards; restarting the safe refresh interval')
                    meta['attempted_at'] = wall
                    atomic_json(meta_path, meta)
                remaining = refresh_delay(meta, cfg, wall)
                if remaining > 0:
                    LOG.info('Next hourly update in %.0fs (Ctrl-C exits safely)', remaining)
                    if stop.wait(remaining): break
            if art_refresh:
                LOG.info('Relevant artwork available; redrawing the displayed %s report', layout)
            elif args.demo:
                if args.night_page:
                    from .night_demo import demo_night_snapshot
                    snap = demo_night_snapshot(cfg)
                else:
                    from .demo import demo_snapshot
                    snap = demo_snapshot(cfg)
            else:
                try:
                    snap = client.fetch()
                    if cfg.night_mode:
                        from .night_client import enrich_snapshot
                        snap = enrich_snapshot(client, snap, cfg)
                        if not (snap.get('night') or {}).get('available'):
                            previous = cached_or_empty(cache, cfg, 'Night data unavailable')
                            old_night = previous.get('night') or {}
                            if old_night.get('evening_date') == (meta.get('night') or {}).get('evening_date') and old_night:
                                snap['night'] = dict(old_night, available=False, cached=True)
                    if not (args.check or args.preview):
                        atomic_json(cache, snap)
                except APIError as exc:
                    LOG.warning('%s', exc)
                    snap = cached_or_empty(cache, cfg, str(exc))
            LOG.info('%s | today %s species / %s records%s | last hour %s species / %s records%s',
                     status_for(snap)[1], snap['today']['species_count'], snap['today']['record_count'],
                     '+' if snap['today']['incomplete'] else '',
                     snap['last_hour']['species_count'], snap['last_hour']['record_count'],
                     '+' if snap['last_hour']['incomplete'] else '')
            if args.check:
                print(json.dumps(check_report(snap,cfg), indent=2, ensure_ascii=False))
                return 2 if snap.get('offline') else 0
            if stop.is_set(): break
            from .render import render
            if not art_refresh:
                layout, proposed_night = choose_report(snap, cfg, meta, edition, utcnow())
                if args.night_page:
                    if not (snap.get('night') or {}).get('evening_date'):
                        raise ValueError('No night report available for this preview; use --demo for sample pages')
                    layout = 'night-' + args.night_page
            # Capture before rendering so an arrival during rendering is never lost.
            frame_missing = missing_artwork(snap, layout)
            frame = render(snap, cfg, layout)
            frame_hash = hashlib.sha256(frame.tobytes()).hexdigest()
            if art_refresh and frame_hash == meta.get('frame_hash'):
                missing = frame_missing
                continue
            out = args.output or state/'latest.png'
            atomic_image(out, frame)
            if args.preview:
                print('Wrote', out, '(480×800; actual six-colour render; no GPIO touched)')
                return 2 if snap.get('offline') else 0
            # Recheck after fetching as well: a clock correction during a scan
            # must not let a push or scheduled frame escape the persisted guard.
            if ((hardware and not single_frame) or push) and not wait_for_cooldown(
                    meta, meta_path, cfg, stop, push=push): break
            # Persist BEFORE imports/initialisation, so even setup failures or
            # restarts cannot hammer the panel. Existing v1 hardware is unchanged.
            meta.update({'attempted_at': time.time(), 'attempt_version': __version__,
                         'attempt_kind': 'artwork' if art_refresh else 'push' if push else 'scheduled'})
            atomic_json(meta_path, meta)
            first_frame = False
            from .hardware import display
            LOG.info('Refreshing panel (%s); full refresh flashing is expected', layout)
            display(frame, cfg)
            cycle += 1
            if not art_refresh:
                edition += 1
                meta['night'] = proposed_night
                report_at = (next_hour(time.time(), cfg.timezone) if hourly
                             else meta['attempted_at'] + cfg.refresh_seconds)
            missing = frame_missing
            meta.update({'success_at': time.time(), 'cycle': cycle, 'edition': edition,
                         'snapshot_at': snap['as_of'], 'version': __version__, 'frame_hash': frame_hash})
            atomic_json(meta_path, meta)
            if hourly:
                LOG.info('Panel asleep. Next report is scheduled on the hour.')
            else:
                LOG.info('Panel asleep. Refresh cadence: %ss.', cfg.refresh_seconds)
            # Queue only after a real frame succeeds: preview/check/demo never spend.
            # This is metadata-only; a separate worker owns HTTPS and image decoding.
            if not args.demo and not art_refresh:
                try:
                    from .autoart import enqueue_snapshot
                    added = enqueue_snapshot(snap, cfg)
                    if added: LOG.info('Queued %s missing bird illustrations (background worker)', added)
                except (OSError, ValueError, RuntimeError) as exc:
                    LOG.warning('Artwork queue unavailable (%s); dashboard continues', type(exc).__name__)
            if single_frame: return 2 if snap.get('offline') else 0
        return 0
    finally:
        if lockfd is not None: os.close(lockfd)


def entry():
    try: return main()
    except ImportError as exc:
        LOG.error('Missing Python dependency: %s. Run ./install.sh first.', exc)
        return 1
    except (RuntimeError, ValueError, OSError) as exc:
        LOG.error('%s', exc)
        return 1
