"""Pure reduction and selection for the sunset-to-sunrise field journal.

No I/O or hardware timing lives here. An edition decision becomes durable only
after the caller successfully displays it. Observation windows are UTC instants.
"""
from __future__ import annotations

import math
from collections import Counter
from datetime import timedelta

from .model import iso, timestamp, normalise_record, text

NIGHT_LAYOUTS = ('night-rhythm', 'night-history', 'night-journal')
OWL_GENERA = frozenset(('strix', 'tyto', 'asio', 'athene', 'bubo', 'otus',
                       'aegolius', 'surnia', 'glaucidium', 'megascops', 'pulsatrix'))


def is_owl(record):
    return str(record.get('scientific_name', '')).lower().split(' ')[0] in OWL_GENERA


def normalise_bat(row, start, end, threshold):
    """Generic bat passes are eligible without inventing a species identity."""
    if not isinstance(row, dict) or row.get('taxonomic_group') != 'bat':
        return None
    if row.get('source_kind') != 'alsa' or row.get('is_live_source') is not True:
        return None
    flags, review = row.get('flags') or {}, row.get('review') or {}
    if not isinstance(flags, dict) or not isinstance(review, dict):
        return None
    if row.get('withdrawn') or flags.get('withdrawn'):
        return None
    status = review.get('status', '')
    if status not in ('', 'held', 'confirmed', 'corrected'):
        return None
    if status == 'corrected':
        corrected = text(row.get('effective_scientific_name') or review.get('corrected_scientific_name'))
        if len(corrected.split()) < 2:
            return None
    detector = row.get('detector') or {}
    if not isinstance(detector, dict):
        return None
    if status not in ('confirmed', 'corrected'):
        score = row.get('score')
        if (isinstance(score, bool) or not isinstance(score, (int, float)) or
                not math.isfinite(score) or not threshold <= score <= 1):
            return None
        # Scores from an unknown plugin do not share this detector's policy.
        if detector.get('plugin_id') != 'ultrasonic-pass-v1':
            return None
    try:
        when = timestamp(row.get('event_start_utc'))
    except (ValueError, TypeError):
        return None
    ident = text(row.get('id'))
    if not ident or not start <= when < end:
        return None
    return {'id': ident, 'when': iso(when),
            'detector': (str(detector.get('plugin_id', '')),
                         str(detector.get('model_version', '')))}


def reduce_night(bird_rows, bat_rows, sunset, end, settings):
    """Summarise one evening and its pre-sunset bird reference hour."""
    baseline = sunset - timedelta(hours=1)
    recent_start = end - timedelta(minutes=30)
    span = max(0, (end - sunset).total_seconds() / 3600)
    bins = [{'start_hour': i, 'end_hour': min(i+1, span), 'count': 0,
             'owl_count': 0, 'incomplete': False, 'median': None}
            for i in range(math.ceil(span))]
    recent = {'bird_count': 0, 'baseline_bird_count': 0, 'bat_count': 0,
              'bat_bins': 0, 'owl_count': 0}
    owls, seen, occupied = {}, set(), set()
    for row in bird_rows:
        rec, _ = normalise_record(row, min(baseline, recent_start), end, settings.min_score)
        if rec is None or rec['id'] in seen:
            continue
        seen.add(rec['id'])
        when = timestamp(rec['when'])
        if not is_owl(rec):
            recent['bird_count'] += when >= recent_start
            recent['baseline_bird_count'] += baseline <= when < sunset
        elif when >= sunset:
            recent['owl_count'] += 1
            key = rec['scientific_name'].casefold()
            if key not in owls:
                owls[key] = {**rec, 'count': 0, 'first': rec['when'], 'last': rec['when']}
            owl = owls[key]
            owl['count'] += 1
            if when > timestamp(owl['last']):
                owl.update({**rec, 'last': rec['when']})
            if when < timestamp(owl['first']):
                owl['first'] = rec['when']
            bins[int((when-sunset).total_seconds()//3600)]['owl_count'] += 1
    first_bat, signatures = None, set()
    seen = set()
    for row in bat_rows:
        rec = normalise_bat(row, sunset, end, settings.bat_min_score)
        if rec is None or rec['id'] in seen:
            continue
        seen.add(rec['id'])
        when = timestamp(rec['when'])
        first_bat = when if first_bat is None else min(first_bat, when)
        signatures.add(rec['detector'])
        bins[int((when-sunset).total_seconds()//3600)]['count'] += 1
        if when >= recent_start:
            recent['bat_count'] += 1
            occupied.add(int((when-recent_start).total_seconds()//300))
    recent['bat_bins'] = len(occupied)
    return {'since': iso(sunset), 'as_of': iso(end), 'sunset': iso(sunset),
            'record_count': len(seen), 'bins': bins, 'recent': recent,
            'owls': sorted(owls.values(), key=lambda r: timestamp(r['last']), reverse=True),
            'first_bat': iso(first_bat) if first_bat else None,
            'detector_signatures': sorted(signatures), 'comparison_hours': int(span),
            'baseline_nights': 0, 'history': [], 'incomplete': False}


def _merge(intervals):
    merged = []
    for start, end in sorted(intervals):
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def capture_fraction(coverage, start, end, min_rate):
    """Merge frame-bounded live spans and subtract deliberate pauses.

    This measures recording, not detector analysis. Analysis is checked
    independently when deciding whether a new night transition is justified.
    """
    if not isinstance(coverage, dict) or end <= start:
        return 0.0
    streams = coverage.get('streams')
    pauses = coverage.get('pauses')
    if not isinstance(streams, list) or not isinstance(pauses, list):
        return 0.0
    intervals, excluded, rates = [], [], []
    for row in streams:
        if not isinstance(row, dict):
            continue
        rate = row.get('sample_rate')
        if (row.get('source_kind') != 'alsa' or row.get('suspect') or
                isinstance(rate, bool) or
                not isinstance(rate, (int, float)) or not math.isfinite(rate) or rate < min_rate):
            continue
        try:
            a, b = max(start, timestamp(row['start_utc'])), min(end, timestamp(row['end_utc']))
            if b > a:
                intervals.append((a, b))
                rates.append(rate)
        except (KeyError, TypeError, ValueError):
            continue
    for row in pauses:
        try:
            excluded.append((max(start, timestamp(row['start_utc'])),
                             min(end, timestamp(row['end_utc']))))
        except (KeyError, TypeError, ValueError):
            return 0.0
    intervals, excluded = _merge(intervals), _merge(excluded)
    seconds = sum((b-a).total_seconds() for a,b in intervals)
    for a,b in intervals:
        seconds -= sum(max(0, (min(b,y)-max(a,x)).total_seconds()) for x,y in excluded)
    # discontinuity_count is a stream-lifetime counter, not window coverage.
    # The history endpoint's missing frames are scoped to its requested range.
    # Charge all of them to any subwindow as a conservative lower bound; the
    # API does not locate those gaps inside its clipped spans.
    missing = coverage.get('estimated_missing_frames', 0)
    gaps = coverage.get('gaps', 0)
    if (isinstance(missing, bool) or not isinstance(missing, (int, float))
            or not math.isfinite(missing) or missing < 0
            or not isinstance(gaps, int) or gaps < 0 or (gaps > 0 and missing == 0)):
        return 0.0
    if rates:
        seconds -= missing / min(rates)
    return max(0, min(1, seconds / (end-start).total_seconds()))


def select_edition(snapshot, settings, previous, now):
    """Return (layout, proposed state); caller commits state after success."""
    day_layout = settings.layout
    if not settings.night_mode:
        return day_layout, {}
    data = snapshot.get('night') or {}
    state = dict(previous) if isinstance(previous, dict) else {}
    valid_state = (isinstance(state.get('page'), int) and not isinstance(state.get('page'), bool)
                   and state['page'] in range(3)
                   and isinstance(state.get('next_page'), int) and state['next_page'] in range(3)
                   and isinstance(state.get('slot'), int)
                   and isinstance(state.get('seen_owls'), list)
                   and all(isinstance(name, str) for name in state['seen_owls']))
    if not valid_state or state.get('identity') != settings.identity():
        state = {}
    try:
        latched = bool(state) and timestamp(state['sunset']) <= now < timestamp(state['sunrise'])
    except (KeyError, TypeError, ValueError):
        latched = False
    if not latched:
        state = {}
    if snapshot.get('offline') or snapshot.get('clock_skew'):
        return (NIGHT_LAYOUTS[state['page']], state) if state else (day_layout, {})
    try:
        within = timestamp(data['sunset']) <= now < timestamp(data['sunrise'])
    except (KeyError, TypeError, ValueError):
        within = False
    if not within and not latched:
        return day_layout, {}
    if not latched:
        if not data.get('available') or not data.get('trigger_ready'):
            return day_layout, {}
        recent = data.get('recent') or {}
        count, baseline = recent.get('bird_count', 0), recent.get('baseline_bird_count', 0)
        quiet = count <= settings.night_bird_quiet_count or count * 2 <= baseline * settings.night_bird_ratio
        bats = (recent.get('bat_count', 0) >= settings.night_bat_count and
                recent.get('bat_bins', 0) >= settings.night_bat_bins)
        owl = recent.get('owl_count', 0) > 0
        if not quiet or not (bats or owl):
            return day_layout, {}
        state = {'identity': settings.identity(), 'evening_date': data['evening_date'],
                 'sunset': data['sunset'], 'sunrise': data['sunrise'],
                 'next_page': 0, 'seen_owls': []}
    # No data / an older retained report must never advance the carousel.
    if not data.get('available') or data.get('evening_date') != state['evening_date']:
        return NIGHT_LAYOUTS[state.get('page', 0)], state
    slot = int(now.timestamp() // 3600)
    if state.get('slot', -1) >= slot:
        return NIGHT_LAYOUTS[state['page']], state
    seen_owls = set(state.get('seen_owls', []))
    present = {o['scientific_name'].casefold() for o in data.get('owls', [])}
    if present - seen_owls:
        page = 2
    else:
        page = state.get('next_page', 0)
        state['next_page'] = (page+1) % len(NIGHT_LAYOUTS)
    state.update(page=page, slot=slot, seen_owls=sorted(seen_owls | present))
    return NIGHT_LAYOUTS[page], state
