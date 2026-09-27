import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gardenink.app import main, choose_report
from gardenink.config import Settings
from gardenink.night_demo import demo_night_snapshot
from gardenink.model import timestamp


class NightAppTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Settings(base_url='http://station.example')
        self.snap = demo_night_snapshot(self.cfg)
        self.snap.update(demo=False)
        self.snap['night'].update(trigger_ready=True, recent={
            'bird_count':0, 'baseline_bird_count':20, 'bat_count':20,
            'bat_bins':4, 'owl_count':3})
        self.now = timestamp(self.snap['as_of'])

    def test_day_rotation_and_night_override(self):
        self.cfg.rotate_layouts=True
        day=copy.deepcopy(self.snap); day.pop('night')
        self.assertEqual(choose_report(day,self.cfg,{},1,self.now)[0],'gallery')
        self.assertEqual(choose_report(self.snap,self.cfg,{},1,self.now)[0],'night-journal')

    def test_preview_does_not_write_latch_or_call_hardware(self):
        with tempfile.TemporaryDirectory() as td:
            state=Path(td); saved={'cycle':4, 'night':{'unchanged':True}}
            (state/'display.json').write_text(json.dumps(saved))
            with patch.dict(os.environ,{'GARDEN_INK_STATE_DIR':td}), \
                 patch('gardenink.app.load',return_value=self.cfg), \
                 patch('gardenink.hardware.display') as display:
                self.assertEqual(main(['--demo','--preview','--night-page','journal']),0)
                display.assert_not_called()
            self.assertEqual(json.loads((state/'display.json').read_text()),saved)
            self.assertFalse((state/'snapshot.json').exists())

    def test_latch_committed_only_after_successful_hardware_frame(self):
        for fail in (False,True):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as td:
                with patch.dict(os.environ,{'GARDEN_INK_STATE_DIR':td}), \
                     patch('gardenink.app.load',return_value=self.cfg), \
                     patch('gardenink.config.Settings.token',return_value=''), \
                     patch('gardenink.app.Client.fetch',return_value=copy.deepcopy(self.snap)), \
                     patch('gardenink.night_client.enrich_snapshot',side_effect=lambda c,s,cfg:s), \
                     patch('gardenink.app.utcnow',return_value=self.now), \
                     patch('gardenink.app.lock_display',return_value=None), \
                     patch('gardenink.autoart.enqueue_snapshot',return_value=0), \
                     patch('gardenink.hardware.display',side_effect=RuntimeError('panel failed') if fail else None):
                    if fail:
                        with self.assertRaisesRegex(RuntimeError,'panel failed'):main(['--once'])
                    else:self.assertEqual(main(['--once']),0)
                meta=json.loads((Path(td)/'display.json').read_text())
                self.assertIn('attempted_at',meta)
                self.assertEqual(bool(meta.get('night')),not fail)

    def test_forced_night_layout_never_allowed_on_hardware(self):
        with self.assertRaises(SystemExit):main(['--demo','--night-page','rhythm','--once'])


class NightConfigTests(unittest.TestCase):
    def test_invalid_coordinates_and_thresholds_are_rejected(self):
        for values in ({'latitude':51}, {'latitude':float('nan'),'longitude':0},
                       {'night_mode':'yes'}, {'night_bat_bins':7},
                       {'night_bat_count':1.5}, {'night_coverage_fraction':0.1}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                Settings(**values).validate(require_url=False)

    def test_filter_changes_invalidate_night_latch_identity(self):
        self.assertNotEqual(Settings().identity(),Settings(night_bat_count=11).identity())
        Settings(latitude=51.5,longitude=-.1).validate(require_url=False)
