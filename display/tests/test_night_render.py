"""Night editions keep unknown coverage distinct from zero observations."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gardenink.config import Settings
from gardenink.palette import COLOURS
from gardenink.render import Page, font
from gardenink.night_demo import demo_night_snapshot
from gardenink.night_render import render_night


PAGES = ('night-rhythm', 'night-history', 'night-journal')


class NightRenderTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings()
        self.snapshot = demo_night_snapshot(self.settings)

    def render_text(self, layout, snapshot=None):
        texts = []
        original = Page.text
        def record(page, xy, value, *args, **kwargs):
            texts.append(str(value))
            return original(page, xy, value, *args, **kwargs)
        with patch.object(Page, 'text', record):
            image = render_night(snapshot or self.snapshot, self.settings, layout)
        return image, '\n'.join(texts)

    def test_three_distinct_deterministic_native_panel_pages_without_mutating_snapshot(self):
        before = deepcopy(self.snapshot)
        pages = []
        for layout in PAGES:
            image = render_night(self.snapshot, self.settings, layout)
            self.assertEqual(image.size, (480, 800))
            self.assertEqual(image.mode, 'RGB')
            pixels = image.get_flattened_data() if hasattr(image, 'get_flattened_data') else image.getdata()
            self.assertTrue(set(pixels) <= set(COLOURS))
            self.assertEqual(image.tobytes(), render_night(self.snapshot, self.settings, layout).tobytes())
            pages.append(image.tobytes())
        self.assertEqual(len(set(pages)), 3)
        self.assertEqual(self.snapshot, before)

    def test_report_bounds_and_owl_persist_outside_latest_hour(self):
        for layout in PAGES:
            _, text = self.render_text(layout)
            self.assertIn('Report covers 6.45pm to 10.45pm BST', text)
            self.assertIn('tawny owl', text.casefold())
            self.assertIn('9.18pm', text)
            self.assertIn('3 detections', text)
            self.assertIn('184', text)
            self.assertNotIn('not identified', text)
            self.assertNotIn('not visits', text)

    def test_partial_totals_are_marked(self):
        self.snapshot['night']['incomplete'] = True
        self.snapshot['night']['bins'][1]['incomplete'] = True
        _, text = self.render_text('night-rhythm')
        self.assertIn('184+', text)
        self.assertIn('72+', text)

    def test_partial_newest_first_scan_does_not_claim_first_bat_time(self):
        self.snapshot['night'].update(incomplete=True, owls=[])
        _, text = self.render_text('night-journal')
        self.assertNotIn('First recorded at', text)

    def test_unknown_baseline_and_history_are_gaps(self):
        for row in self.snapshot['night']['bins']:
            row['median'] = None
        self.snapshot['night']['baseline_nights'] = 0
        _, rhythm = self.render_text('night-rhythm')
        self.assertNotIn('median', rhythm)
        self.snapshot['night']['history'][0].update(total=999, comparable=False)
        self.snapshot['night']['history'][1].update(total=None, owl_count=None)
        _, history = self.render_text('night-history')
        self.assertNotIn('999', history)
        self.assertGreaterEqual(history.count('—'), 2)

    def test_no_owl_uses_bat_journal_without_inventing_observation(self):
        self.snapshot['night']['owls'] = []
        for layout in PAGES:
            _, text = self.render_text(layout)
            self.assertNotIn('tawny owl', text.casefold())
            self.assertNotIn('Last heard', text)
            self.assertNotIn('3 detections', text)
        _, text = self.render_text('night-journal')
        self.assertIn('Bats after sunset', text)

    def test_operational_status_is_visible_but_good_status_is_quiet(self):
        self.snapshot['demo'] = False
        _, text = self.render_text('night-rhythm')
        self.assertNotIn('CAPTURE OK', text)
        self.snapshot.update(offline=True, cached=True)
        _, text = self.render_text('night-rhythm')
        self.assertIn('OFFLINE', text)
        self.snapshot.update(offline=False, cached=False)
        self.snapshot['health']['pause']['active'] = True
        _, text = self.render_text('night-journal')
        self.assertIn('PAUSED', text)

    def test_sixteen_bins_and_long_names_remain_inside_panel(self):
        self.snapshot['night']['bins'] = [dict(start_hour=i, end_hour=i+1,
            count=i, incomplete=False, owl_count=0, median=None) for i in range(16)]
        self.snapshot['night']['owls'][0]['name'] = 'A very long local name for this owl in the garden'
        self.snapshot['night']['owls'][0]['scientific_name'] = 'Unknownus verylongspeciesname'
        for layout in PAGES:
            image, _ = self.render_text(layout)
            # Content keeps an outer paper margin, including extreme labels.
            for box in ((0, 0, 10, 800), (470, 0, 480, 800), (0, 795, 480, 800)):
                crop = image.crop(box)
                pixels = crop.get_flattened_data() if hasattr(crop, 'get_flattened_data') else crop.getdata()
                self.assertEqual(set(pixels), {(255, 255, 255)})

    def test_unknown_layout_rejected(self):
        with self.assertRaises(ValueError):
            render_night(self.snapshot, self.settings, 'unknown')

    def test_unavailable_report_does_not_present_zero_as_observed_silence(self):
        self.snapshot['night'].update(available=False, record_count=0, bins=[], owls=[])
        for layout in ('night-rhythm', 'night-journal'):
            _, text = self.render_text(layout)
            self.assertIn('—', text)
            self.assertIn('Owl records unavailable', text)
            self.assertNotIn('0', text.splitlines())

    def test_cached_night_keeps_original_total_and_discloses_staleness(self):
        self.snapshot['demo'] = False
        self.snapshot['night'].update(available=False, cached=True)
        for layout in PAGES:
            _, text = self.render_text(layout)
            self.assertIn('Night data unavailable · cached report', text)
            if layout != 'night-history':
                self.assertIn('184', text.splitlines())

    def test_long_night_compact_chart_labels_are_legible_and_separate(self):
        from gardenink.night_render import hourly_chart
        page = Page()
        labels = []
        original = Page.text
        def record(page, xy, value, size=16, style='sans', **kwargs):
            result = original(page, xy, value, size, style, **kwargs)
            labels.append((xy, str(value), kwargs, result))
            return result
        with patch.object(Page, 'text', record):
            hourly_chart(page, {'bins': [dict(start_hour=i, end_hour=i+1,
                count=10+i, median=None) for i in range(16)]},
                (266, 641, 190, 91), compact=True)
        axis = [(xy[0]-size[0]//2, xy[0]+size[0]//2)
                for xy, value, kwargs, size in labels if xy[1] == 742]
        for previous, following in zip(axis, axis[1:]):
            self.assertLessEqual(previous[1]+3, following[0])
        for xy, value, kwargs, size in labels:
            if xy[1] < 732:
                self.assertGreaterEqual(kwargs['width'], font(10).getlength(value))

    def test_hourly_gap_does_not_join_baseline_across_missing_interval(self):
        from gardenink.night_render import hourly_chart
        page = Page()
        hourly_chart(page, {'bins': [
            dict(start_hour=0, end_hour=1, count=None, median=20),
            dict(start_hour=1, end_hour=2, count=None, median=None),
            dict(start_hour=2, end_hour=3, count=None, median=20),
        ]}, (50, 200, 360, 160), baseline=True)
        # A spurious line joining the two medians would cross this central gap.
        self.assertEqual(set(page.im.crop((180, 220, 280, 310)).get_flattened_data()), {(255, 255, 255)})


if __name__ == '__main__':
    unittest.main()
