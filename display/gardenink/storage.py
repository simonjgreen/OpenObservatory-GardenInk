from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
from .model import utcnow, timestamp, build_snapshot


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=path.name+'.', suffix='.tmp', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            os.fchmod(f.fileno(), 0o600)
            json.dump(value, f, separators=(',', ':'), ensure_ascii=False)
            f.write('\n')
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def cached_or_empty(path: Path, settings, message: str) -> dict:
    now = utcnow()
    try:
        if path.stat().st_size > 8 * 1024 * 1024:
            raise ValueError('Cache too large')
        snap = json.loads(path.read_text(encoding='utf-8'))
        age = (now-timestamp(snap['fetched_at'])).total_seconds()
        if snap.get('schema_version') != 2 or snap.get('cache_identity') != settings.identity() or snap.get('demo'):
            raise ValueError('Cache is for a different schema, site or filter')
        if not 0 <= age <= settings.cache_max_age_hours*3600:
            raise ValueError('Cache too old or in the future')
        for field in ('today', 'last_hour'):
            if not isinstance(snap.get(field), dict) or not isinstance(snap[field].get('species'), list):
                raise ValueError('Bad cache')
        # Preserve BOTH original time windows, not merely the original image date.
        snap.update({'offline': True, 'cached': True, 'error': message})
        return snap
    except (OSError, ValueError, KeyError, TypeError):
        snap = build_snapshot([], now, settings)
        snap.update({'offline': True, 'cached': False, 'error': message})
        return snap
