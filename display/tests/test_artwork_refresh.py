"""Exercise artwork arrivals through the real scheduler, lookup and renderer."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from gardenink.app import main
from gardenink.config import Settings
from gardenink.demo import demo_snapshot
from test_schedule import Clock


class ArtworkRefreshTests(unittest.TestCase):
    def run_arrival(self, publications, *, layout='journal', rotate=False,
                    start=1000, stop_at=3650, during_render=False, refresh_seconds=3600,
                    render_jump=None, fail_art=False, display_seconds=40):
        cfg = Settings(base_url='http://station.example', layout=layout,
                       rotate_layouts=rotate, refresh_seconds=refresh_seconds)
        clock = Clock(start)
        elapsed = [0]
        snap = demo_snapshot(cfg)
        snap['demo'] = False
        template = snap['today']['species'][0]
        names = ['Tyto alba', 'Strix aluco', 'Corvus corax', 'Anas platyrhynchos',
                 'Grus grus', 'Cettia cetti', 'Spinus spinus']
        birds = [dict(template, scientific_name=n, name=n, count=10-i) for i,n in enumerate(names)]
        snap['last_hour']['species'] = birds[:2]
        snap['today']['species'] = birds
        frames, fetches, render_layouts = [], [], []
        pending = list(publications)
        with tempfile.TemporaryDirectory() as td:
            state = Path(td)
            assets = state/'assets'
            assets.mkdir()
            (assets/'manifest.json').write_text('{}')

            def publish_due():
                for when, name, folder in pending[:]:
                    if clock.wall >= when:
                        path = state/'autoart'/folder/(name.replace(' ', '_').lower()+'.png')
                        path.parent.mkdir(parents=True, exist_ok=True)
                        im = Image.new('RGB', (160, 160), 'white')
                        ImageDraw.Draw(im).ellipse((30, 20, 130, 140), fill='black')
                        im.save(path)
                        pending.remove((when, name, folder))

            def wait(seconds):
                clock.wall += seconds
                elapsed[0] += seconds
                publish_due()
                if clock.wall >= stop_at:
                    clock.set()
                return clock.is_set()

            def fetch():
                fetches.append(clock.wall)
                return copy.deepcopy(snap)

            from gardenink.render import render as real_render
            def render(snapshot, settings, selected_layout):
                render_layouts.append(selected_layout)
                if render_jump is not None and len(render_layouts) == 2:
                    clock.wall = render_jump
                if during_render:
                    publish_due()
                return real_render(snapshot, settings, selected_layout)

            def display(frame, settings):
                frames.append((clock.wall, frame.tobytes()))
                if fail_art and len(frames) == 2:
                    raise RuntimeError('simulated panel failure')
                clock.wall += display_seconds
                elapsed[0] += display_seconds

            clock.wait = wait
            with patch.dict(os.environ, {'GARDEN_INK_STATE_DIR':td}), \
                 patch('gardenink.render.ASSETS', assets), \
                 patch('gardenink.app.load', return_value=cfg), \
                 patch('gardenink.config.Settings.token', return_value=''), \
                 patch('gardenink.app.Client.fetch', side_effect=fetch), \
                 patch('gardenink.app.threading.Event', return_value=clock), \
                 patch('gardenink.app.time.time', side_effect=lambda:clock.wall), \
                 patch('gardenink.app.time.monotonic', side_effect=lambda:elapsed[0]), \
                 patch('gardenink.app.signal.signal'), \
                 patch('gardenink.app.lock_display', return_value=None), \
                 patch('gardenink.autoart.enqueue_snapshot', return_value=0), \
                 patch('gardenink.render.render', side_effect=render), \
                 patch('gardenink.hardware.display', side_effect=display):
                if fail_art:
                    with self.assertRaisesRegex(RuntimeError, 'simulated panel failure'):
                        main([])
                    # Restart after failure: persisted attempt must still protect the panel.
                    self.assertEqual(main(['--refresh-now']), 0)
                else:
                    self.assertEqual(main([]), 0)
            meta = json.loads((state/'display.json').read_text())
        return fetches, frames, render_layouts, meta

    def test_feature_art_redraws_same_report_after_guard_then_resumes_hour(self):
        fetches, frames, layouts, meta = self.run_arrival([(1080,'Tyto alba','images')])
        self.assertEqual(fetches, [1000, 3600])
        self.assertEqual(len(frames), 3)
        self.assertGreaterEqual(frames[1][0], 1180)
        self.assertLessEqual(frames[1][0], 1210)
        self.assertNotEqual(frames[0][1], frames[1][1])
        self.assertEqual(frames[2][0], 3600)
        self.assertEqual(meta['cycle'], 3)

    def test_daily_card_art_is_relevant(self):
        _, frames, _, _ = self.run_arrival([(1250,'Anas platyrhynchos','images')], stop_at=1600)
        self.assertEqual(len(frames), 2)

    def test_unpictured_species_and_review_candidates_do_not_refresh(self):
        for name, folder in [('Spinus spinus','images'), ('Tyto alba','candidates')]:
            with self.subTest(name=name, folder=folder):
                _, frames, _, _ = self.run_arrival([(1080,name,folder)], stop_at=1600)
                self.assertEqual(len(frames), 1)

    def test_gallery_watches_its_sixth_card(self):
        _, frames, _, _ = self.run_arrival([(1080,'Cettia cetti','images')],
                                          layout='gallery', stop_at=1600)
        self.assertEqual(len(frames), 2)

    def test_multiple_arrivals_during_guard_are_one_refresh(self):
        _, frames, _, _ = self.run_arrival([(1050,'Tyto alba','images'),
                                          (1100,'Strix aluco','images')], stop_at=1600)
        self.assertEqual(len(frames), 2)

    def test_art_refresh_does_not_rotate_the_page_or_skip_next_layout(self):
        _, frames, layouts, _ = self.run_arrival([(1080,'Tyto alba','images')], rotate=True)
        self.assertEqual(len(frames), 3)
        self.assertEqual(layouts, ['journal','journal','gallery'])

    def test_hourly_report_wins_over_art_waiting_for_guard(self):
        fetches, frames, _, _ = self.run_arrival([(3570,'Tyto alba','images')],
                                               start=3500, stop_at=3900)
        self.assertEqual(fetches, [3500, 3600])
        self.assertEqual(len(frames), 2)
        self.assertGreaterEqual(frames[1][0], 3680)

    def test_publication_during_render_does_not_repeat_identical_frame(self):
        _, frames, _, _ = self.run_arrival([(1000,'Tyto alba','images')],
                                          during_render=True, stop_at=1600)
        self.assertEqual(len(frames), 1)

    def test_custom_report_cadence_is_not_shifted_by_artwork(self):
        fetches, frames, _, _ = self.run_arrival([(1080,'Tyto alba','images')],
                                               refresh_seconds=7200, stop_at=8300)
        self.assertEqual(fetches, [1000, 8200])
        self.assertEqual(len(frames), 3)

    def test_backward_clock_during_art_redraw_realigns_next_report(self):
        fetches, frames, _, _ = self.run_arrival([(4500,'Tyto alba','images')],
                                               start=4000, stop_at=7300, render_jump=1000)
        self.assertEqual(fetches, [4000, 3600, 7200])
        self.assertGreaterEqual(frames[1][0], 1180)

    def test_forward_clock_during_art_redraw_skips_missed_report(self):
        fetches, _, _, _ = self.run_arrival([(1080,'Tyto alba','images')],
                                          render_jump=7500, stop_at=10900)
        self.assertEqual(fetches, [1000, 10800])

    def test_slow_art_redraw_crossing_hour_keeps_due_report(self):
        fetches, frames, _, _ = self.run_arrival([(3580,'Tyto alba','images')],
                                               stop_at=7500, display_seconds=60)
        self.assertEqual(fetches, [1000, 3640, 7200])
        self.assertEqual([when for when, _ in frames], [1000, 3580, 3760, 7360])

    def test_failed_art_attempt_keeps_persisted_guard_on_restart(self):
        _, frames, _, meta = self.run_arrival([(1080,'Tyto alba','images')], fail_art=True)
        self.assertEqual(len(frames), 3)
        self.assertGreaterEqual(frames[2][0] - frames[1][0], 180)
        self.assertEqual(meta['cycle'], 2)


if __name__ == '__main__':
    unittest.main()
