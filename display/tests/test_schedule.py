import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gardenink import __version__
from gardenink.app import main, next_hour, wait_for_hour, wait_for_cooldown, refresh_delay
from gardenink.config import Settings
from gardenink.demo import demo_snapshot
from gardenink.model import timestamp


class Clock:
    def __init__(self, wall):
        self.wall = wall
        self.stopped = False

    def is_set(self):
        return self.stopped

    def set(self):
        self.stopped = True

    def wait(self, seconds):
        self.wall += seconds
        return self.stopped


class HourBoundaryTests(unittest.TestCase):
    def run_display(self, start, durations, meta=None, timezone='Europe/London', clock=None, args=None,
                    stop_after=True):
        clock = clock or Clock(start)
        cfg = Settings(timezone=timezone)
        fetches, attempts = [], []

        def fetch(settings):
            fetches.append(clock.wall)
            clock.wall += durations[len(fetches) - 1]
            return demo_snapshot(settings)

        def display(*args):
            attempts.append(clock.wall)
            clock.wall += 40  # The panel itself takes time, too.
            if stop_after and len(attempts) == len(durations):
                clock.set()

        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / 'display.json'
            if meta:
                state.write_text(json.dumps(meta))
            with patch.dict(os.environ, {'GARDEN_INK_STATE_DIR': td}), \
                 patch('gardenink.app.load', return_value=cfg), \
                 patch('gardenink.app.threading.Event', return_value=clock), \
                 patch('gardenink.app.time.time', side_effect=lambda: clock.wall), \
                 patch('gardenink.app.signal.signal'), \
                 patch('gardenink.app.lock_display', return_value=None), \
                 patch('gardenink.demo.demo_snapshot', side_effect=fetch), \
                 patch('gardenink.hardware.display', side_effect=display):
                self.assertEqual(main(['--demo'] + (args or [])), 0)
            saved = json.loads(state.read_text())
        return fetches, attempts, saved

    def test_cycles_start_on_hour_without_scan_or_panel_time_drift(self):
        fetches, attempts, saved = self.run_display(1000, [20, 5, 50])
        self.assertEqual(fetches, [1000, 3600, 7200])
        self.assertEqual(attempts, [1020, 3605, 7250])
        self.assertEqual(saved['attempted_at'], 7250)
        self.assertEqual(saved['cycle'], 3)

    def test_restart_refreshes_after_minimum_guard_even_after_failed_attempt(self):
        meta = {'attempted_at': 3500, 'attempt_version': __version__, 'cycle': 7}
        fetches, attempts, saved = self.run_display(3550, [10], meta)
        self.assertEqual(fetches, [3680])
        self.assertEqual(attempts, [3690])
        self.assertEqual(saved['cycle'], 8)

    def test_refresh_now_bypasses_hour_but_waits_before_fetching(self):
        meta = {'attempted_at': 1000, 'attempt_version': __version__, 'cycle': 4}
        fetches, attempts, saved = self.run_display(1100, [10], meta, args=['--refresh-now'],
                                                  stop_after=False)
        self.assertEqual(fetches, [1180])
        self.assertEqual(attempts, [1190])
        self.assertEqual(saved['cycle'], 5)

    def test_push_rechecks_guard_if_clock_moves_back_during_fetch(self):
        meta = {'attempted_at': 1000, 'attempt_version': __version__, 'cycle': 4}
        fetches, attempts, _ = self.run_display(1180, [-200], meta, args=['--refresh-now'])
        self.assertEqual(fetches, [1180])
        self.assertEqual(attempts, [1160])

    def test_push_does_not_delay_next_regular_report_by_an_hour(self):
        fetches, attempts, _ = self.run_display(3000, [10, 5])
        self.assertEqual(fetches, [3000, 3600])
        self.assertEqual(attempts, [3010, 3605])

    def test_push_just_before_hour_keeps_minimum_guard(self):
        fetches, attempts, _ = self.run_display(3550, [0, 0])
        self.assertEqual(fetches, [3550, 3600])
        self.assertEqual(attempts, [3550, 3730])

    def test_custom_cadence_is_retained_after_startup_push(self):
        cfg = Settings(refresh_seconds=7200)
        meta = {'attempted_at': 1000, 'attempt_version': __version__, 'attempt_kind': 'push'}
        self.assertEqual(refresh_delay(meta, cfg, 1100), 7100)

    def test_local_hours_include_midnight_and_both_dst_occurrences(self):
        cases = [
            ('2026-09-27T22:50:00Z', 'Europe/London', ['2026-09-27T23:00:00Z', '2026-09-28T00:00:00Z']),
            ('2026-03-29T00:50:00Z', 'Europe/London', ['2026-03-29T01:00:00Z', '2026-03-29T02:00:00Z']),
            ('2026-10-24T23:50:00Z', 'Europe/London', ['2026-10-25T00:00:00Z', '2026-10-25T01:00:00Z']),
            ('2026-09-27T10:10:00Z', 'Asia/Kathmandu', ['2026-09-27T10:15:00Z', '2026-09-27T11:15:00Z']),
        ]
        for start, zone, expected in cases:
            with self.subTest(start=start, zone=zone):
                fetches, _, _ = self.run_display(timestamp(start).timestamp(), [0, 0, 0], timezone=zone)
                self.assertEqual(fetches, [timestamp(start).timestamp()] +
                                 [timestamp(value).timestamp() for value in expected])

    def test_start_at_boundary_does_not_wait_another_hour(self):
        fetches, _, _ = self.run_display(3600, [0])
        self.assertEqual(fetches, [3600])

    def test_long_cycle_skips_missed_boundaries(self):
        fetches, _, _ = self.run_display(1000, [4000, 0])
        self.assertEqual(fetches, [1000, 7200])

    def test_fractional_dst_transition_uses_next_real_local_hour(self):
        # Lord Howe jumps from 01:59:59 to 02:30, so 03:00 is next.
        wall = timestamp('2026-10-03T15:20:00Z').timestamp()
        self.assertEqual(next_hour(wall, 'Australia/Lord_Howe'),
                         timestamp('2026-10-03T16:00:00Z').timestamp())

    def test_clock_corrections_realign_wait_to_new_hour(self):
        for corrected, expected in [(500, 3600), (7500, 10800)]:
            with self.subTest(corrected=corrected):
                clock = Clock(4000)
                original_wait = clock.wait
                def jump(seconds):
                    clock.wall = corrected
                    clock.wait = original_wait
                    return False
                clock.wait = jump
                with patch('gardenink.app.time.time', side_effect=lambda: clock.wall):
                    self.assertTrue(wait_for_hour(Settings(), clock))
                self.assertEqual(clock.wall, expected)

    def test_backward_clock_preserves_full_cooldown_on_disk(self):
        clock = Clock(1000)
        meta = {'attempted_at': 2000, 'attempt_version': __version__, 'cycle': 9}
        with tempfile.TemporaryDirectory() as td, \
             patch('gardenink.app.time.time', side_effect=lambda: clock.wall):
            path = Path(td) / 'display.json'
            self.assertTrue(wait_for_cooldown(meta, path, Settings(), clock))
            self.assertEqual(json.loads(path.read_text())['attempted_at'], 1000)
            self.assertEqual(meta['cycle'], 9)
        self.assertEqual(clock.wall, 4600)

    def test_stopping_during_hour_wait_exits_without_refresh(self):
        clock = Clock(1000)
        def stop(seconds):
            clock.set()
            return True
        clock.wait = stop
        with patch('gardenink.app.time.time', side_effect=lambda: clock.wall):
            self.assertFalse(wait_for_hour(Settings(), clock))


if __name__ == '__main__':
    unittest.main()
