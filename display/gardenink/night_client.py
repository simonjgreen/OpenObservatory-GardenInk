"""Bounded, read-only enrichment for the after-dark journal.

Recording coverage is independent of API pagination. Historical comparisons
require matching observed detector identities as well as recording coverage;
an empty historical scan alone cannot establish that a detector was running.
"""
from __future__ import annotations

from datetime import datetime, time as daytime, timedelta
import math
import statistics
import time
from zoneinfo import ZoneInfo

from .client import APIError
from .model import iso, timestamp, normalise_record
from .night import capture_fraction, reduce_night
from .solar import night_window

BIRD_RATE = 48000
BAT_RATE = 96000  # Open Observatory UltrasonicDetector.MIN_SAMPLE_RATE
# API rows may contain clips and large diagnostics. Keep only reducer inputs
# so a bounded multi-page scan also has a reasonable Pi memory footprint.
_RECORD_FIELDS = ('id', 'event_start_utc', 'source_kind', 'is_live_source',
                  'taxonomic_group', 'score', 'rank', 'withdrawn',
                  'scientific_name', 'common_name', 'display_name',
                  'effective_scientific_name', 'effective_common_name')


def _compact(row):
    result = {key: row[key] for key in _RECORD_FIELDS if key in row}
    for name, keys in (('flags', ('withdrawn',)),
                       ('review', ('status', 'corrected_scientific_name', 'corrected_common_name')),
                       ('detector', ('plugin_id', 'model_version'))):
        value = row.get(name)
        result[name] = ({key: value[key] for key in keys if key in value}
                        if isinstance(value, dict) else value)
    return result


class _Budget:
    def __init__(self, client, settings):
        self.client, self.settings = client, settings
        self.started, self.pages = time.monotonic(), 0

    def get(self, endpoint, params=None):
        if time.monotonic() - self.started >= self.settings.fetch_budget_seconds:
            raise APIError('Night fetch time budget reached')
        if endpoint == 'detections':
            if self.pages >= self.settings.night_max_pages:
                raise APIError('Night page budget reached')
            self.pages += 1
        return self.client.get(endpoint, params)


def _scan(budget, group, start, end):
    """Newest-first scan with a one-microsecond overlap at timestamp ties."""
    rows, seen, until, previous_oldest = [], set(), end, None
    required = {'id', 'event_start_utc', 'source_kind', 'is_live_source', 'taxonomic_group'}
    while True:
        try:
            payload = budget.get('detections', {
                'since': iso(start), 'until': iso(until), 'group': group,
                'identified_only': 'true' if group == 'bird' else 'false',
                'include_synthetic': 'false', 'min_score': 0,
                'limit': budget.settings.page_size,
            })
        except APIError as exc:
            return rows, False, str(exc)
        batch = payload.get('detections')
        if not isinstance(batch, list) or len(batch) > budget.settings.page_size:
            raise APIError('Malformed or oversized night detection page')
        oldest, prior = None, None
        for row in batch:
            if not isinstance(row, dict) or not required <= row.keys():
                raise APIError('Night detection lacks identity/source fields')
            ident = row['id']
            if not isinstance(ident, str) or not ident:
                raise APIError('Malformed night detection ID')
            try:
                when = timestamp(row['event_start_utc'])
            except (ValueError, TypeError):
                raise APIError('Malformed night detection timestamp') from None
            if not start <= when < until:
                raise APIError('Night API did not honour detection time bounds')
            if prior is not None and when > prior:
                raise APIError('Night API is not sorted newest first')
            prior = oldest = when
            if ident not in seen:
                seen.add(ident)
                rows.append(_compact(row))
        truncated = payload.get('truncated', len(batch) >= budget.settings.page_size)
        if not isinstance(truncated, bool):
            raise APIError('Malformed night truncated flag')
        if not truncated:
            return rows, True, ''
        if oldest is None:
            return rows, False, 'Truncated night page without records'
        if previous_oldest is not None and oldest >= previous_oldest:
            return rows, False, 'Timestamp tie exceeds one API page'
        previous_oldest, until = oldest, oldest + timedelta(microseconds=1)


def _coverage(budget, start, end):
    response = budget.get('history', {'since': iso(start), 'until': iso(end),
        'bucket_seconds': 3600, 'min_score': 0, 'include_synthetic': 'false',
        'include_unidentified': 'false'})
    coverage = response.get('coverage')
    return coverage if isinstance(coverage, dict) else {}


def _worker(detectors, plugin, min_rate):
    for row in detectors:
        if not isinstance(row, dict) or row.get('plugin_id') != plugin:
            continue
        lag, rate = row.get('lag_s'), (row.get('window') or {}).get('sample_rate')
        if (row.get('state') == 'ok' and row.get('circuit_open') is False
                and isinstance(lag, (int, float)) and not isinstance(lag, bool)
                and math.isfinite(lag) and 0 <= lag <= 60
                and isinstance(rate, (int, float)) and not isinstance(rate, bool)
                and math.isfinite(rate) and rate >= min_rate
                and isinstance(row.get('model_version'), str) and row['model_version']):
            return (plugin, row['model_version'])
    return None


def _history(budget, data, coordinates, settings, signature, bird_signature, current_coverage):
    hours = data['comparison_hours']
    comparable = []
    current_signatures = {tuple(s) for s in data['detector_signatures']}
    compatible_current = bool(signature and current_signatures == {signature})
    evening = timestamp(data['sunset']).astimezone(ZoneInfo(settings.timezone)).date()
    for offset in range(1, 8):
        # Solar lookup at local noon reliably selects the requested civil date,
        # even if the current snapshot is on the morning side of midnight.
        day = evening - timedelta(days=offset)
        entry = {'date': day.isoformat(), 'evening_date': day.isoformat(), 'count': None,
                 'total': None, 'comparable': False, 'owl_count': None,
                 'incomplete': True, 'reason': 'No completed comparison period', 'bins': []}
        data['history'].append(entry)
        if hours < 1:
            continue
        window = night_window(datetime.combine(day, daytime(12), ZoneInfo(settings.timezone)),
                              settings.timezone, *coordinates)
        if not window:
            entry['reason'] = 'No trustworthy solar window'
            continue
        sunset, sunrise = window['sunset'], window['sunrise']
        end = sunset + timedelta(hours=hours)
        entry.update(sunset=iso(sunset), since=iso(sunset), as_of=iso(min(end, sunrise)))
        # A shorter historical night cannot represent the same elapsed hours.
        if end > sunrise:
            entry['reason'] = 'Historical night shorter than comparison period'
            continue
        try:
            coverage = _coverage(budget, sunset, end)
            if any(capture_fraction(coverage, sunset+timedelta(hours=i),
                                    sunset+timedelta(hours=i+1), BAT_RATE)
                   < settings.night_coverage_fraction for i in range(hours)):
                entry['reason'] = 'Insufficient historical microphone coverage'
                continue
            bats, bat_complete, reason = _scan(budget, 'bat', sunset, end)
            birds, bird_complete, bird_reason = _scan(budget, 'bird', sunset, end)
            reduced = reduce_night(birds, bats, sunset, end, settings)
            entry['detector_signatures'] = reduced['detector_signatures']
            if not bat_complete or not bird_complete:
                entry['reason'] = reason or bird_reason
                continue
            # Current worker metadata cannot prove past availability. Require
            # observed, compatible bat records in the actual compared window.
            # This is a compatibility check, not a claim of detector effort.
            signatures = {tuple(s) for s in reduced['detector_signatures']}
            if not compatible_current or signatures != {signature}:
                entry['reason'] = 'Historical detector identity unavailable or incompatible'
                continue
            bird_signatures = set()
            for row in birds:
                record, _ = normalise_record(row, sunset, end, settings.min_score)
                if record is not None:
                    detector = row.get('detector') or {}
                    if not isinstance(detector, dict):
                        detector = {}
                    bird_signatures.add((detector.get('plugin_id'), detector.get('model_version')))
            owl_count = (sum(b['owl_count'] for b in reduced['bins'])
                         if bird_signature and bird_signatures == {bird_signature} else None)
            entry.update(count=reduced['record_count'], total=reduced['record_count'], comparable=True, owl_count=owl_count,
                         bins=reduced['bins'], incomplete=False, reason='',
                         comparison_basis='recording coverage and observed detector identity')
            comparable.append(reduced)
        except (APIError, ValueError, TypeError, KeyError) as exc:
            entry['reason'] = str(exc)
    data['history'].reverse()
    sunset = timestamp(data['sunset'])
    current_comparable = bool(hours and compatible_current and not data['incomplete']
        and all(capture_fraction(current_coverage, sunset+timedelta(hours=i),
                                  sunset+timedelta(hours=i+1), BAT_RATE)
                >= settings.night_coverage_fraction for i in range(hours)))
    completed = data['bins'][:hours]
    current_total = sum(b['count'] for b in completed) if current_comparable else None
    data['history'].append({'date': evening.isoformat(), 'evening_date': evening.isoformat(),
        'total': current_total, 'count': current_total,
        'owl_count': sum(b['owl_count'] for b in completed) if current_comparable else None,
        'comparable': current_comparable, 'incomplete': data['incomplete'], 'bins': completed,
        'reason': '' if current_comparable else 'Current comparison coverage or detector evidence unavailable'})
    if not current_comparable:
        comparable = []
    data['baseline_nights'] = len(comparable)
    for index, bucket in enumerate(data['bins']):
        if index < hours and comparable:
            bucket['median'] = statistics.median(item['bins'][index]['count'] for item in comparable)


def enrich_snapshot(client, snapshot, settings):
    """Return a day snapshot plus optional night data; failures stay local."""
    result = dict(snapshot)
    if not settings.night_mode:
        return result
    budget = _Budget(client, settings)
    try:
        now = timestamp(snapshot['as_of'])
        pipeline = budget.get('debug/pipeline').get('station') or {}
        station = pipeline.get('station') or {}
        coordinates = settings.latitude, settings.longitude
        if coordinates[0] is None or coordinates[1] is None:
            if station.get('location_configured') is not True:
                raise APIError('Station coordinates are unavailable')
            coordinates = station.get('latitude'), station.get('longitude')
        window = night_window(now, settings.timezone, *coordinates)
        if not window:
            raise APIError('No trustworthy sunset/sunrise window')
        if not window['sunset'] <= now < window['sunrise']:
            result['night'] = {'available': False, 'reason': 'Outside the night window',
                'sunset': iso(window['sunset']), 'sunrise': iso(window['sunrise']),
                'evening_date': window['evening_date']}
            return result
        sunset = window['sunset']
        baseline = sunset - timedelta(hours=1)
        coverage_error = ''
        try:
            coverage = _coverage(budget, baseline, now)
        except APIError as exc:
            coverage, coverage_error = {}, str(exc)
        birds, bird_complete, bird_reason = _scan(budget, 'bird', baseline, now)
        bats, bat_complete, bat_reason = _scan(budget, 'bat', sunset, now)
        data = reduce_night(birds, bats, sunset, now, settings)
        data.update(available=True, evening_date=window['evening_date'], sunrise=iso(window['sunrise']),
                    incomplete=not (bird_complete and bat_complete), reason=bird_reason or bat_reason)
        for bucket in data['bins']:
            bucket['incomplete'] = data['incomplete']
        detectors = pipeline.get('detectors') or []
        bird_worker = _worker(detectors, 'birdnet-v2.4', BIRD_RATE)
        bat_worker = _worker(detectors, 'ultrasonic-pass-v1', BAT_RATE)
        recent_start = now - timedelta(minutes=30)
        bird_coverage = capture_fraction(coverage, recent_start, now, BIRD_RATE)
        bat_coverage = capture_fraction(coverage, max(sunset, recent_start), now, BAT_RATE)
        baseline_coverage = capture_fraction(coverage, baseline, sunset, BIRD_RATE)
        enough = settings.night_coverage_fraction
        # Baseline coverage is required too: a partial baseline should not
        # silently alter the rate comparison used by the edition selector.
        data['trigger_ready'] = bool(bird_complete and bat_complete and bird_worker
            and bird_coverage >= enough and baseline_coverage >= enough
            and ((bat_worker and bat_coverage >= enough) or data['recent']['owl_count'] > 0)
            and not snapshot.get('offline') and not snapshot.get('clock_skew'))
        data['coverage'] = {'recent_bird_fraction': bird_coverage, 'recent_bat_fraction': bat_coverage,
                            'baseline_bird_fraction': baseline_coverage, 'reason': coverage_error}
        data['pipeline'] = {'bird_ready': bool(bird_worker), 'bat_ready': bool(bat_worker)}
        data['comparison_hours'] = int((min(now, window['sunrise'])-sunset).total_seconds() // 3600)
        _history(budget, data, coordinates, settings, bat_worker, bird_worker, coverage)
        data['scan'] = {'pages': budget.pages}
        result['night'] = data
    except (APIError, ValueError, TypeError, KeyError, AttributeError) as exc:
        result['night'] = {'available': False, 'trigger_ready': False, 'reason': str(exc)}
    return result
