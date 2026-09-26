from __future__ import annotations
from collections import Counter
from datetime import datetime, timedelta, timezone
import math
from typing import Any

UTC = timezone.utc

def utcnow() -> datetime:
    return datetime.now(UTC)


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace('+00:00', 'Z')


def timestamp(value: Any) -> datetime:
    if not isinstance(value, str): raise ValueError('Missing timestamp')
    d = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if d.tzinfo is None: raise ValueError('A timestamp must include its timezone')
    return d.astimezone(UTC)


def text(value: Any, limit: int = 100) -> str:
    if not isinstance(value, str): return ''
    return ' '.join(value.split())[:limit]


def normalise_record(row: dict, start: datetime, end: datetime, threshold: float):
    """Fail closed on identity/source ambiguity. Scores are NOT probabilities."""
    if row.get('taxonomic_group') != 'bird': return None, 'not_bird'
    if row.get('source_kind') != 'alsa' or row.get('is_live_source') is not True:
        return None, 'not_microphone'
    flags = row.get('flags') or {}
    if not isinstance(flags, dict): return None, 'malformed'
    if row.get('withdrawn') or flags.get('withdrawn'):
        return None, 'withdrawn'
    review = row.get('review') or {}
    if not isinstance(review, dict): return None, 'malformed'
    status = review.get('status', '')
    if status == 'rejected': return None, 'rejected'
    if status and status not in ('confirmed', 'corrected', 'held'):
        return None, 'unknown_review'
    try:
        when = timestamp(row.get('event_start_utc'))
    except (ValueError, TypeError): return None, 'bad_timestamp'
    if not start <= when < end: return None, 'outside_window'
    reviewed = status in ('confirmed', 'corrected')
    score = row.get('score')
    if not reviewed:
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
            return None, 'invalid_score'
        if not 0 <= score <= 1 or score < threshold: return None, 'below_threshold'
    # Human corrections MUST NOT fall back to the original bird or its artwork.
    if status == 'corrected':
        sci = text(row.get('effective_scientific_name') or review.get('corrected_scientific_name'))
        name = text(row.get('effective_common_name') or review.get('corrected_common_name'))
    else:
        sci = text(row.get('effective_scientific_name') or row.get('scientific_name'))
        name = text(row.get('effective_common_name') or row.get('common_name') or row.get('display_name'))
    # Do not invent a species for a genus / non-taxonomic sound class.
    if len(sci.split()) < 2: return None, 'no_species_name'
    if row.get('rank') not in ('species', 'subspecies') and status != 'corrected':
        return None, 'not_species_rank'
    record_id = text(row.get('id'), 100)
    if not record_id: return None, 'missing_id'
    return {
        'id': record_id, 'scientific_name': sci, 'name': name or sci,
        'when': iso(when), 'reviewed': reviewed,
        'corrected': status == 'corrected',
    }, None


def summarise(rows: list, start: datetime, end: datetime, threshold: float,
              incomplete: bool = False, incomplete_reason: str = '') -> dict:
    dropped = Counter()
    seen = set()
    records = []
    for row in rows:
        if not isinstance(row, dict):
            dropped['malformed'] += 1
            continue
        rec, reason = normalise_record(row, start, end, threshold)
        if rec is None:
            dropped[reason] += 1
            continue
        if rec['id'] in seen: continue
        seen.add(rec['id'])
        records.append(rec)
    records.sort(key=lambda r: (r['when'], r['id']), reverse=True)
    species = {}
    for r in records:
        key = r['scientific_name'].casefold()
        if key not in species:
            species[key] = {**r, 'count': 0, 'first': r['when'], 'last': r['when']}
        species[key]['count'] += 1
        species[key]['first'] = min(species[key]['first'], r['when'])
    # A chart describes returned detection records, never animals or microphone coverage.
    bins = [0] * 24
    span = max(1, (end-start).total_seconds())
    for r in records:
        i = min(23, max(0, int((timestamp(r['when'])-start).total_seconds()/span*24)))
        bins[i] += 1
    return {'as_of': iso(end), 'since': iso(start), 'species': list(species.values()),
            'record_count': len(records), 'species_count': len(species),
            'incomplete': incomplete, 'incomplete_reason': incomplete_reason,
            'raw_rows': len(rows), 'excluded': dict(dropped), 'bins': bins}


def status_for(snapshot: dict) -> tuple[str, str]:
    if snapshot.get('demo'): return 'demo', 'DEMO — invented detections'
    if snapshot.get('offline'):
        return 'offline', 'OFFLINE — cached records' if snapshot.get('cached') else 'OFFLINE — no current data'
    health = snapshot.get('health') or {}
    if (health.get('pause') or {}).get('active'):
        return 'paused', 'PAUSED BY THE OPERATOR'
    capture = health.get('capture') or {}
    if capture.get('is_live_hardware') is False:
        return 'not_live', 'NOT LIVE MICROPHONE AUDIO'
    if capture.get('state') and capture.get('state') != 'capturing':
        return 'capture_error', 'CAPTURE NEEDS ATTENTION'
    if snapshot.get('clock_skew'):
        return 'clock', 'PI / STATION CLOCKS DISAGREE'
    if health.get('status') in ('critical', 'degraded'):
        return 'degraded', 'STATION NEEDS ATTENTION'
    if capture.get('state') == 'capturing' and capture.get('is_live_hardware') is True:
        if health.get('status') == 'ok': return 'ok', 'CAPTURE OK AT SNAPSHOT TIME'
    return 'unknown', 'CAPTURE STATUS UNAVAILABLE'


def window_bounds(end: datetime, zone_name: str) -> tuple[datetime, datetime]:
    """Today's midnight and the trailing elapsed hour, both as UTC instants.

    Local midnight is NOT end-minus-24h. The two boundaries may be in different
    UTC offsets on the spring/autumn DST changeovers. A trailing hour is always
    3600 seconds, even across midnight or a repeated local clock hour.
    """
    from zoneinfo import ZoneInfo
    local = end.astimezone(ZoneInfo(zone_name))
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0, fold=0)
    return midnight.astimezone(UTC), end.astimezone(UTC) - timedelta(hours=1)


class WindowAccumulator:
    """Streaming reduction: no clips, media metadata or full raw rows retained."""
    def __init__(self, start: datetime, end: datetime, threshold: float, zone_name: str):
        from zoneinfo import ZoneInfo
        self.start, self.end, self.threshold = start, end, threshold
        self.zone = ZoneInfo(zone_name)
        self.species: dict = {}
        self.excluded = Counter()
        self.raw_rows = 0
        self.record_count = 0
        self.bins = [0] * 24

    def add(self, row: dict) -> None:
        try:
            when = timestamp(row.get('event_start_utc'))
        except (ValueError, TypeError):
            self.excluded['bad_timestamp'] += 1
            return
        if not self.start <= when < self.end:
            return
        self.raw_rows += 1
        rec, reason = normalise_record(row, self.start, self.end, self.threshold)
        if rec is None:
            self.excluded[reason] += 1
            return
        self.record_count += 1
        self.bins[when.astimezone(self.zone).hour] += 1
        key = rec['scientific_name'].casefold()
        if key not in self.species:
            self.species[key] = {**rec, 'count': 0, 'first': rec['when'], 'last': rec['when']}
        item = self.species[key]
        item['count'] += 1
        if when < timestamp(item['first']):
            item['first'] = rec['when']
        if when > timestamp(item['last']):
            # Current name/review annotation comes from this species' newest record.
            item.update({k: rec[k] for k in ('id','name','scientific_name','when','reviewed','corrected')})
            item['last'] = rec['when']

    def finish(self, incomplete: bool = False, reason: str = '') -> dict:
        birds = sorted(self.species.values(),
                       key=lambda s: (timestamp(s['last']), s['scientific_name']), reverse=True)
        return {'since': iso(self.start), 'as_of': iso(self.end),
                'species': birds, 'species_count': len(birds),
                'record_count': self.record_count, 'raw_rows': self.raw_rows,
                'excluded': dict(self.excluded), 'bins': self.bins,
                'incomplete': bool(incomplete), 'incomplete_reason': reason if incomplete else ''}


def build_snapshot(rows: list, end: datetime, settings, incomplete: bool = False) -> dict:
    """Convenient fixture helper; the HTTP client uses the same reducers per page."""
    today_start, hour_start = window_bounds(end, settings.timezone)
    today = WindowAccumulator(today_start, end, settings.min_score, settings.timezone)
    hour = WindowAccumulator(hour_start, end, settings.min_score, settings.timezone)
    seen = set()
    for row in rows:
        key = row.get('id') if isinstance(row, dict) else None
        if not key or key in seen:
            continue
        seen.add(key)
        today.add(row)
        hour.add(row)
    result = today.finish(incomplete, 'Fixture incomplete' if incomplete else '')
    result.update({'schema_version': 2, 'today': today.finish(incomplete),
                   'last_hour': hour.finish(incomplete), 'health': {},
                   'offline': False, 'cached': False, 'demo': False,
                   'fetched_at': iso(end), 'cache_identity': settings.identity()})
    return result
