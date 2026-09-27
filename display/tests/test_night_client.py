"""Night transport contracts with an in-memory read-only station."""
import itertools
from datetime import timedelta
import unittest
from unittest.mock import patch

from gardenink.client import APIError
from gardenink.config import Settings
from gardenink.model import iso, timestamp
from gardenink.solar import night_window
from gardenink.night_client import enrich_snapshot

NOW = timestamp('2026-09-27T21:00:00Z')


def detection(ident, when, group='bat', **changes):
    row = dict(id=ident, event_start_utc=iso(when), source_kind='alsa',
               is_live_source=True, taxonomic_group=group, score=.9,
               rank='species' if group == 'bird' else None,
               scientific_name='Strix aluco' if group == 'bird' else None,
               common_name='Tawny Owl' if group == 'bird' else None,
               review=None, flags={}, withdrawn=False,
               detector={'plugin_id': 'birdnet-v2.4' if group == 'bird' else 'ultrasonic-pass-v1',
                         'model_version': '1.0.0'})
    row.update(changes)
    return row


class Station:
    def __init__(self):
        self.rows, self.calls = [], []
        self.coverage = True
        self.rate = 384000
        self.fail = None
        self.malformed = None
        self.pipeline = {'station': {
            'station': {'latitude': 51.5, 'longitude': -.1, 'location_configured': True},
            'detectors': [dict(plugin_id=plugin, model_version='1.0.0', state='ok',
                lag_s=9, circuit_open=False, window={'sample_rate': rate})
                for plugin, rate in [('birdnet-v2.4', 48000), ('ultrasonic-pass-v1', 384000)]]}}

    def get(self, endpoint, params=None):
        self.calls.append((endpoint, params))
        if endpoint == self.fail:
            raise APIError('station unavailable')
        if endpoint == 'debug/pipeline':
            return self.pipeline
        start, end = timestamp(params['since']), timestamp(params['until'])
        if endpoint == 'history':
            return {'coverage': {'streams': [dict(source_kind='alsa', sample_rate=self.rate,
                start_utc=iso(start), end_utc=iso(end), suspect=False, discontinuity_count=0)]
                if self.coverage else [], 'pauses': []}}
        assert endpoint == 'detections'
        assert params['min_score'] == 0
        assert params['include_synthetic'] == 'false'
        assert params['identified_only'] == ('true' if params['group'] == 'bird' else 'false')
        if self.malformed:
            return self.malformed
        rows = sorted((r for r in self.rows if r['taxonomic_group'] == params['group']
                       and start <= timestamp(r['event_start_utc']) < end),
                      key=lambda r: r['event_start_utc'], reverse=True)
        return {'detections': rows[:params['limit']], 'truncated': len(rows) > params['limit']}


class NightClientTests(unittest.TestCase):
    def setUp(self):
        self.client = Station()
        self.settings = Settings()
        self.snapshot = {'as_of': iso(NOW), 'today': {'record_count': 15}}
        self.sunset = night_window(NOW, 'Europe/London', 51.5, -.1)['sunset']

    def report(self):
        return enrich_snapshot(self.client, self.snapshot, self.settings)['night']

    def test_station_coordinates_and_snapshot_time_determine_evening(self):
        result = self.report()
        self.assertTrue(result['available'])
        self.assertTrue(result['trigger_ready'])
        self.assertEqual(result['evening_date'], '2026-09-27')
        self.assertEqual(result['as_of'], iso(NOW))
        self.assertEqual(self.snapshot['today']['record_count'], 15)

    def test_absent_recording_is_not_quiet(self):
        self.client.coverage = False
        result = self.report()
        self.assertTrue(result['available'])
        self.assertFalse(result['trigger_ready'])

    def test_unhealthy_bird_pipeline_never_infers_quiet(self):
        for change in ({'state': 'unavailable'}, {'lag_s': None}, {'lag_s': 400},
                       {'circuit_open': True}):
            with self.subTest(change=change):
                station = Station()
                station.pipeline['station']['detectors'][0].update(change)
                result = enrich_snapshot(station, self.snapshot, self.settings)['night']
                self.assertFalse(result['trigger_ready'])

    def test_owl_allows_audible_only_capture_but_bats_need_ultrasound(self):
        self.client.rate = 48000
        self.client.pipeline['station']['detectors'][1]['state'] = 'unavailable'
        self.assertFalse(self.report()['trigger_ready'])
        self.client.rows = [detection('owl', NOW-timedelta(minutes=10), 'bird')]
        self.assertTrue(self.report()['trigger_ready'])

    def test_explicit_coordinates_override_unconfigured_station(self):
        self.client.pipeline['station']['station'] = {'location_configured': False}
        self.assertFalse(self.report()['available'])
        self.settings.latitude, self.settings.longitude = 51.5, -.1
        self.assertTrue(self.report()['available'])

    def test_daylight_skips_detection_and_coverage_scans(self):
        self.snapshot['as_of'] = '2026-09-27T12:00:00Z'
        self.assertFalse(self.report()['available'])
        self.assertEqual([e for e, _ in self.client.calls], ['debug/pipeline'])

    def test_after_midnight_retains_previous_evening(self):
        self.snapshot['as_of'] = '2026-09-28T01:00:00Z'
        self.assertEqual(self.report()['evening_date'], '2026-09-27')

    def test_transport_failure_preserves_day_snapshot(self):
        self.client.fail = 'debug/pipeline'
        result = enrich_snapshot(self.client, self.snapshot, self.settings)
        self.assertFalse(result['night']['available'])
        self.assertEqual(result['today'], {'record_count': 15})
        self.assertIn('reason', result['night'])

    def test_shared_page_budget_withholds_trigger_on_partial_current_scan(self):
        self.settings.night_max_pages = 1
        result = self.report()
        self.assertTrue(result['incomplete'])
        self.assertFalse(result['trigger_ready'])
        self.assertEqual(len([e for e, _ in self.client.calls if e == 'detections']), 1)

    def test_tied_page_boundary_deduplicates_and_marks_unresolved_cohort_partial(self):
        self.settings.page_size = 2
        self.client.rows = [detection(str(i), NOW-timedelta(minutes=5)) for i in range(3)]
        result = self.report()
        self.assertEqual(result['record_count'], 2)
        self.assertTrue(result['incomplete'])
        self.assertFalse(result['trigger_ready'])
        self.assertIn('tie', result['reason'].lower())

    def test_low_score_confirmed_bat_is_included_and_rejected_is_excluded(self):
        self.client.rows = [detection('confirmed', NOW-timedelta(minutes=5), score=.1,
                           review={'status': 'confirmed'}),
                           detection('rejected', NOW-timedelta(minutes=6), review={'status': 'rejected'})]
        self.assertEqual(self.report()['record_count'], 1)

    def test_unhonoured_api_bounds_cannot_create_a_new_trigger(self):
        self.client.malformed = {'detections': [detection('future', NOW+timedelta(seconds=1))],
                                 'truncated': False}
        result = self.report()
        self.assertFalse(result['available'])

    def test_recording_without_historical_detector_evidence_remains_gap(self):
        result = self.report()
        self.assertEqual(len(result['history']), 8)
        self.assertTrue(all(n['count'] is None for n in result['history'][:-1]))
        self.assertEqual(result['baseline_nights'], 0)
        self.assertTrue(all(b['median'] is None for b in result['bins']))

    def test_history_uses_equal_completed_hours_and_can_include_zero_bins(self):
        self.client.rows.append(detection('current', self.sunset+timedelta(minutes=20)))
        previous = night_window(NOW-timedelta(days=1), 'Europe/London', 51.5, -.1)['sunset']
        self.client.rows += [detection('old', previous+timedelta(minutes=20)),
                            detection('future-hour', previous+timedelta(hours=3, minutes=10))]
        result = self.report()
        self.assertEqual(result['comparison_hours'], 3)
        self.assertEqual(result['history'][-2]['count'], 1)
        self.assertEqual(result['baseline_nights'], 1)
        self.assertEqual([b['median'] for b in result['bins']], [1, 0, 0, None])

    def test_incompatible_historical_model_is_a_gap(self):
        previous = night_window(NOW-timedelta(days=1), 'Europe/London', 51.5, -.1)['sunset']
        self.client.rows = [detection('old', previous+timedelta(minutes=20),
            detector={'plugin_id': 'ultrasonic-pass-v1', 'model_version': 'old'})]
        result = self.report()
        self.assertIsNone(result['history'][-2]['count'])
        self.assertEqual(result['baseline_nights'], 0)

    def test_history_schema_is_chronological_and_includes_current_completed_hours(self):
        self.client.rows = [detection('complete', self.sunset+timedelta(minutes=20)),
                           detection('ongoing', self.sunset+timedelta(hours=3, minutes=5))]
        result = self.report()
        self.assertEqual([r['date'] for r in result['history']],
                         ['2026-09-%d' % d for d in range(20, 28)])
        current = result['history'][-1]
        self.assertEqual(current['total'], 1)
        self.assertTrue(current['comparable'])
        self.assertFalse(current['incomplete'])
        self.assertEqual(result['record_count'], 2)

    def test_unsorted_api_cannot_create_trigger(self):
        self.client.malformed = {'detections': [
            detection('older', NOW-timedelta(minutes=3)),
            detection('newer', NOW-timedelta(minutes=1))], 'truncated': False}
        self.assertFalse(self.report()['available'])

    def test_coverage_endpoint_failure_keeps_counts_but_withholds_trigger(self):
        self.client.fail = 'history'
        self.client.rows = [detection('bat', NOW-timedelta(minutes=5))]
        result = self.report()
        self.assertEqual(result['record_count'], 1)
        self.assertFalse(result['trigger_ready'])
        self.assertFalse(result['history'][-1]['comparable'])

    def test_disabled_night_mode_makes_no_requests(self):
        self.settings.night_mode = False
        self.assertEqual(enrich_snapshot(self.client, self.snapshot, self.settings), self.snapshot)
        self.assertEqual(self.client.calls, [])

    def test_overlap_page_recovers_boundary_records_without_double_counting(self):
        self.settings.page_size = 2
        self.client.rows = [detection('new', NOW-timedelta(minutes=1)),
                           detection('tie-a', NOW-timedelta(minutes=2)),
                           detection('tie-b', NOW-timedelta(minutes=2))]
        result = self.report()
        self.assertEqual(result['record_count'], 3)
        self.assertFalse(result['incomplete'])
        self.assertTrue(result['trigger_ready'])

    def test_current_empty_scan_with_live_worker_is_not_historical_zero_evidence(self):
        result = self.report()
        self.assertFalse(result['history'][-1]['comparable'])
        self.assertIsNone(result['history'][-1]['total'])

    def test_a_coverage_gap_in_one_hour_cannot_hide_in_three_hour_average(self):
        self.client.rows = [detection('current', self.sunset+timedelta(minutes=20))]
        previous = night_window(NOW-timedelta(days=1), 'Europe/London', 51.5, -.1)['sunset']
        self.client.rows += [detection('old', previous+timedelta(minutes=20))]
        original_get = self.client.get
        def get(endpoint, params=None):
            response = original_get(endpoint, params)
            if endpoint == 'history' and timestamp(params['since']) == previous:
                response['coverage']['streams'][0]['start_utc'] = iso(previous+timedelta(minutes=10))
            return response
        self.client.get = get
        result = self.report()
        self.assertIsNone(result['history'][-2]['total'])
        self.assertEqual(result['baseline_nights'], 0)

    def test_missing_current_coverage_withholds_otherwise_supported_median(self):
        previous = night_window(NOW-timedelta(days=1), 'Europe/London', 51.5, -.1)['sunset']
        self.client.rows = [detection('current', self.sunset+timedelta(minutes=20)),
                           detection('old', previous+timedelta(minutes=20))]
        original_get = self.client.get
        def get(endpoint, params=None):
            response = original_get(endpoint, params)
            if endpoint == 'history' and params['until'] == iso(NOW):
                response['coverage']['streams'] = []
            return response
        self.client.get = get
        result = self.report()
        self.assertEqual(result['history'][-2]['total'], 1)
        self.assertFalse(result['history'][-1]['comparable'])
        self.assertEqual(result['baseline_nights'], 0)
        self.assertTrue(all(b['median'] is None for b in result['bins']))

    def test_historical_bat_evidence_does_not_imply_owl_detector_ran(self):
        previous = night_window(NOW-timedelta(days=1), 'Europe/London', 51.5, -.1)['sunset']
        self.client.rows = [detection('current', self.sunset+timedelta(minutes=20)),
                           detection('old', previous+timedelta(minutes=20))]
        result = self.report()
        self.assertEqual(result['history'][-2]['total'], 1)
        self.assertIsNone(result['history'][-2]['owl_count'])

    def test_time_budget_prevents_later_requests(self):
        with patch('gardenink.night_client.time.monotonic', side_effect=itertools.chain([0, 0], itertools.repeat(1000))):
            result = self.report()
        self.assertFalse(result.get('trigger_ready', False))
        self.assertLessEqual(len(self.client.calls), 1)


if __name__ == '__main__':
    unittest.main()
