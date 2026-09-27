"""Gallery editions follow local report hours, independently of frame counters."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gardenink.app import choose_report, main
from gardenink.config import Settings, load, save
from gardenink.demo import demo_snapshot
from gardenink.model import timestamp
from gardenink.night_demo import demo_night_snapshot


class GalleryScheduleTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Settings()
        self.snap = demo_snapshot(self.cfg, timestamp('2026-09-27T08:00:00Z'))

    def layout_at(self, when, *, cfg=None, snap=None, edition=0):
        return choose_report(snap or self.snap, cfg or self.cfg, {}, edition, timestamp(when))[0]

    def test_default_slots_and_return_to_journal_follow_local_hour(self):
        for hour in range(24):
            expected = 'gallery' if hour in (10, 14) else 'journal'
            for minute in (0, 37, 59):
                when = '2026-09-27T%02d:%02d:00+01:00' % (hour, minute)
                with self.subTest(when=when):
                    self.assertEqual(self.layout_at(when, edition=99), expected)

    def test_dst_change_dates_still_use_ten_and_two_local_time(self):
        for day, utc_hours in [('2026-03-28', (10, 14)), ('2026-03-29', (9, 13)),
                               ('2026-10-24', (9, 13)), ('2026-10-25', (10, 14))]:
            for hour in utc_hours:
                with self.subTest(day=day, hour=hour):
                    self.assertEqual(self.layout_at(f'{day}T{hour:02d}:00:00Z'), 'gallery')
                    self.assertEqual(self.layout_at(f'{day}T{hour+1:02d}:00:00Z'), 'journal')

    def test_uses_configured_timezone_and_current_edition_not_cached_date(self):
        cfg = Settings(timezone='Asia/Kathmandu')
        snap = deepcopy(self.snap)
        snap.update(offline=True, cached=True)
        self.assertEqual(self.layout_at('2026-09-28T04:15:00Z', cfg=cfg, snap=snap), 'gallery')
        self.assertEqual(self.layout_at('2026-09-28T05:15:00Z', cfg=cfg, snap=snap), 'journal')

    def test_night_page_takes_precedence_over_gallery_slot(self):
        cfg = Settings(gallery_hours=[22])
        snap = demo_night_snapshot(cfg)
        snap['night'].update(trigger_ready=True, recent={
            'bird_count':0, 'baseline_bird_count':20, 'bat_count':20,
            'bat_bins':4, 'owl_count':3})
        self.assertEqual(self.layout_at(snap['as_of'], cfg=cfg, snap=snap), 'night-journal')

    def test_custom_disabled_and_legacy_explicit_layout_choices(self):
        self.assertEqual(self.layout_at('2026-09-27T09:00:00Z', cfg=Settings(gallery_hours=[])), 'journal')
        self.assertEqual(self.layout_at('2026-09-27T11:00:00Z', cfg=Settings(gallery_hours=[12])), 'gallery')
        self.assertEqual(self.layout_at('2026-09-27T11:00:00Z', cfg=Settings(layout='gallery')), 'gallery')
        cfg = Settings(rotate_layouts=True)
        self.assertEqual(self.layout_at('2026-09-27T09:00:00Z', cfg=cfg, edition=0), 'journal')
        self.assertEqual(self.layout_at('2026-09-27T11:00:00Z', cfg=cfg, edition=1), 'gallery')

    def test_explicit_cli_journal_can_preview_during_gallery_hour_without_state_changes(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td)
            saved = {'cycle':8, 'edition':5, 'attempted_at':1234}
            (state/'display.json').write_text(json.dumps(saved))
            from gardenink.render import render as real_render
            with patch.dict(os.environ, {'GARDEN_INK_STATE_DIR':td}), \
                 patch('gardenink.app.load', return_value=self.cfg), \
                 patch('gardenink.app.utcnow', return_value=timestamp('2026-09-27T09:10:00Z')), \
                 patch('gardenink.render.render', wraps=real_render) as renderer, \
                 patch('gardenink.hardware.display') as hardware:
                self.assertEqual(main(['--demo', '--preview', '--layout', 'journal']), 0)
                self.assertEqual(renderer.call_args.args[2], 'journal')
                hardware.assert_not_called()
            self.assertEqual(json.loads((state/'display.json').read_text()), saved)


class GalleryConfigTests(unittest.TestCase):
    def test_missing_setting_in_existing_config_gets_slots_and_roundtrips(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/'config.json'
            path.write_text('{"layout":"journal"}')
            cfg = load(path).validate(require_url=False)
            self.assertEqual(cfg.gallery_hours, [10,14])
            cfg.gallery_hours = [9,15]
            save(path,cfg)
            self.assertEqual(load(path).gallery_hours, [9,15])

    def test_invalid_hours_are_rejected(self):
        for hours in (None, '10,14', [True], [10.5], [-1], [24], [10,10]):
            with self.subTest(hours=hours), self.assertRaises(ValueError):
                Settings(gallery_hours=hours).validate(require_url=False)

    def test_layout_schedule_does_not_invalidate_observations_or_night_latch(self):
        self.assertEqual(Settings().identity(), Settings(gallery_hours=[]).identity())
