"""Rendered report totals must retain window and availability semantics."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gardenink.config import Settings
from gardenink.demo import demo_snapshot
from gardenink.model import timestamp
from gardenink.render import Page, render


class FooterTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Settings()
        self.snap = demo_snapshot(self.cfg, timestamp('2026-09-27T17:15:00Z'))
        self.snap['demo'] = False

    def draw(self, snap=None, layout='journal'):
        labels = []
        original = Page.text
        def capture(page, xy, value, *args, **kwargs):
            labels.append((xy, str(value)))
            return original(page, xy, value, *args, **kwargs)
        with patch.object(Page, 'text', capture):
            image = render(snap or self.snap, self.cfg, layout)
        return image, labels

    def footer_text(self, snap=None, layout='journal'):
        return [text for (x, y), text in self.draw(snap, layout)[1] if y > 688]

    def test_each_window_has_its_own_species_and_detection_totals(self):
        for layout in ('journal', 'gallery'):
            text = self.footer_text(layout=layout)
            self.assertEqual([t for t in text if t.isdigit()], ['9', '103', '4', '43'])

    def test_only_incomplete_window_totals_get_plus_and_explanation(self):
        self.snap['today']['incomplete'] = True
        text = self.footer_text()
        self.assertEqual([t for t in text if t.rstrip('+').isdigit()], ['9+', '103+', '4', '43'])
        self.assertTrue(any('at least' in t.lower() for t in text))

    def test_cached_incomplete_report_keeps_both_qualifications(self):
        self.snap.update(offline=True, cached=True)
        self.snap['last_hour']['incomplete'] = True
        text = '\n'.join(self.footer_text())
        self.assertIn('CACHED', text)
        self.assertIn('at least', text.lower())
        self.assertIn('43+', text)
        page_text = ' '.join(t for _, t in self.draw()[1])
        self.assertIn('5.15pm to 6.15pm BST', page_text)

    def test_paused_report_retains_its_historical_totals(self):
        self.snap['health']['pause']['active'] = True
        text = self.footer_text()
        self.assertIn('43', text)
        self.assertTrue(any('PAUSED' in t for t in text))

    def test_no_cache_means_unavailable_not_empty_in_both_layouts(self):
        self.snap.update(offline=True, cached=False)
        for window in ('today', 'last_hour'):
            self.snap[window].update(species=[], record_count=0, species_count=0)
        for layout in ('journal', 'gallery'):
            labels = self.draw(layout=layout)[1]
            text = '\n'.join(t for _, t in labels)
            self.assertIn('unavailable', text)
            self.assertNotIn('No qualifying bird IDs today', text)
            self.assertFalse(any(t.isdigit() for (_, y), t in labels if y > 688))
            self.assertNotIn('Report covers', '\n'.join(t for (_, y), t in labels if y > 688))

    def test_gallery_report_interval_disambiguates_midnight_and_dst(self):
        for at, expected in (
            ('2026-09-26T23:05:00Z', '26 Sep, 11.05pm to 12.05am BST'),
            ('2026-10-25T01:30:00Z', '1.30am BST to 1.30am GMT'),
        ):
            snap = demo_snapshot(self.cfg, timestamp(at))
            text = ' '.join(t for _, t in self.draw(snap, 'gallery')[1])
            self.assertIn(expected, text)
            self.assertIn('since local midnight', text)
            self.assertIn('Report-hour totals', text)

    def test_sample_label_does_not_hide_partial_explanation(self):
        self.snap['fixture'] = True
        self.snap['today']['incomplete'] = True
        text = '\n'.join(self.footer_text())
        self.assertIn('at least', text.lower())
        # Page.tracked emits individual glyphs; inspect the raster masthead too.
        sample = self.draw()[0].crop((24, 17, 330, 31)).tobytes()
        self.snap['fixture'] = False
        real = self.draw()[0].crop((24, 17, 330, 31)).tobytes()
        self.assertNotEqual(sample, real)


if __name__ == '__main__':
    unittest.main()
