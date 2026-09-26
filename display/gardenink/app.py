from __future__ import annotations
import argparse
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


def refresh_delay(meta: dict, cfg, wall: float) -> float:
    """Restart-persistent, start-to-start display cooldown.

    The first v2 frame may replace an old v1 frame after the existing 180-second
    hardware guard, so an upgrade doesn't make its first preview wait an hour.
    Subsequent attempts (including failed attempts) use the configured hour.
    """
    try:
        previous = float(meta.get('attempted_at', 0))
    except (ValueError, TypeError):
        previous = 0.0
    if not previous:
        return 0.0
    interval = cfg.refresh_seconds if meta.get('attempt_version') in ('2.0.0', __version__) else 180
    elapsed = max(0.0, wall - previous)
    return max(0.0, interval - elapsed)


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
    ap.add_argument('--check', action='store_true', help='Read API and report both windows, no GPIO')
    ap.add_argument('--layout', choices=['journal','gallery'])
    ap.add_argument('--rotation', type=int, choices=[90,270])
    ap.add_argument('--verbose', action='store_true')
    ap.add_argument('--version', action='version', version=__version__)
    args = ap.parse_args(argv)
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
    lockfd = lock_display() if hardware else None
    meta_path = state/'display.json'
    meta = read_meta(meta_path)
    cycle = int(meta.get('cycle', 0))
    try:
        while not stop.is_set():
            # Wait BEFORE querying the station or rendering. A manual --once after
            # an earlier frame must not display a snapshot fetched an hour ago.
            if hardware:
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
            if args.demo:
                from .demo import demo_snapshot
                snap = demo_snapshot(cfg)
            else:
                try:
                    snap = client.fetch()
                    if not args.check:
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
            layout = ('journal','gallery')[cycle%2] if cfg.rotate_layouts else cfg.layout
            frame = render(snap, cfg, layout)
            out = args.output or state/'latest.png'
            atomic_image(out, frame)
            if args.preview:
                print('Wrote', out, '(480×800; actual six-colour render; no GPIO touched)')
                return 2 if snap.get('offline') else 0
            # Persist BEFORE imports/initialisation, so even setup failures or
            # restarts cannot hammer the panel. Existing v1 hardware is unchanged.
            meta.update({'attempted_at': time.time(), 'attempt_version': __version__})
            atomic_json(meta_path, meta)
            from .hardware import display
            LOG.info('Refreshing panel (%s); full refresh flashing is expected', layout)
            display(frame, cfg)
            cycle += 1
            meta.update({'success_at': time.time(), 'cycle': cycle, 'snapshot_at': snap['as_of'],
                         'version': __version__, 'frame_hash': hashlib.sha256(frame.tobytes()).hexdigest()})
            atomic_json(meta_path, meta)
            LOG.info('Panel asleep. Next update in approximately one hour (%ss cadence).',
                     cfg.refresh_seconds)
            # Queue only after a real frame succeeds: preview/check/demo never spend.
            # This is metadata-only; a separate worker owns HTTPS and image decoding.
            if not args.demo:
                try:
                    from .autoart import enqueue_snapshot
                    added = enqueue_snapshot(snap, cfg)
                    if added: LOG.info('Queued %s missing bird illustrations (background worker)', added)
                except (OSError, ValueError, RuntimeError) as exc:
                    LOG.warning('Artwork queue unavailable (%s); dashboard continues', type(exc).__name__)
            if args.once: return 2 if snap.get('offline') else 0
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
