"""Protect the physically selected type treatment and report semantics."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gardenink.config import Settings
from gardenink.demo import demo_snapshot
from gardenink.model import timestamp
from gardenink.render import Page, render, illustrated_species


class ReadabilityTests(unittest.TestCase):
    def test_capital_h_has_equal_vertical_stems_at_selected_body_size(self):
        page = Page()
        width, height = page.text((24, 24), 'H', 14)
        # A row above the crossbar has two stems of equal width, not 2 px vs 1 px.
        row = [page.im.getpixel((24+x, 25)) == (0, 0, 0) for x in range(width)]
        runs = []
        for pixel in row:
            if pixel:
                if not runs or runs[-1] == 0: runs.append(1)
                else: runs[-1] += 1
            elif runs and runs[-1] != 0:
                runs.append(0)
        stems = [n for n in runs if n]
        self.assertEqual(len(stems), 2)
        self.assertEqual(stems[0], stems[1])

    def test_journal_tracks_only_feature_and_three_daily_art_slots(self):
        cfg = Settings()
        snap = demo_snapshot(cfg, timestamp('2026-09-27T11:01:00Z'))
        before = deepcopy(snap)
        birds = illustrated_species(snap, 'journal')
        self.assertEqual(len(birds), 4)
        self.assertEqual(len({b['scientific_name'] for b in birds}), 4)
        render(snap, cfg)
        self.assertEqual(snap, before)
        self.assertEqual((snap['today']['species_count'], snap['today']['record_count']), (9, 103))

    def test_long_names_and_dst_labels_stay_legible_without_collisions(self):
        cfg = Settings()
        snap = demo_snapshot(cfg, timestamp('2026-10-25T01:30:00Z'))
        bird = snap['last_hour']['species'][0]
        bird.update(name='Short-toed Treecreeper', scientific_name='Certhia brachydactyla')
        snap['today']['species'][0].update(name='Long-tailed Tit', scientific_name='Aegithalos caudatus')
        snap.update(offline=True, cached=True)
        snap['today']['incomplete'] = True
        snap['health']['pause']['active'] = True
        drawn = []
        original = Page.text

        def capture(page, xy, value, size=16, style='sans', colour=(0,0,0), **kw):
            w, h = original(page, xy, value, size, style, colour, **kw)
            x, y = xy
            if kw.get('align') == 'centre': x -= w//2
            if kw.get('align') == 'right': x -= w
            drawn.append(((x, y, x+w, y+h), str(value), size))
            return w, h

        with patch.object(Page, 'text', capture):
            render(snap, cfg)
        for box, value, size in drawn:
            self.assertGreaterEqual(size, 14, value)
            self.assertGreaterEqual(box[0], 23, value)
            self.assertLessEqual(box[2], 457, value)
            self.assertLessEqual(box[3], 793, value)
        for i, (a, av, _) in enumerate(drawn):
            for b, bv, _ in drawn[i+1:]:
                overlaps = a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]
                self.assertFalse(overlaps, (av, bv))
        text = ' '.join(value for _, value, _ in drawn)
        for required in ('1.30am BST', '1.30am GMT', 'CACHED', 'PAUSED', 'at least', 'Acoustic IDs'):
            self.assertIn(required, text)

    def test_long_station_name_cannot_grow_up_into_hourly_report(self):
        cfg = Settings()
        snap = demo_snapshot(cfg, timestamp('2026-09-27T11:01:00Z'))
        name = 'Long-tailed Tit (European form, identification awaiting detailed review by the station operator)'
        snap['today']['species'][0].update(name=name, scientific_name='Aegithalos caudatus europaeus', count=999)
        original = Page.text
        daily_text = []
        recording = False
        def capture(page, xy, value, *args, **kwargs):
            nonlocal recording
            if str(value).startswith('Heard today'): recording = True
            elif recording: daily_text.append((xy[1],str(value)))
            return original(page,xy,value,*args,**kwargs)
        with patch.object(Page,'text',capture): render(snap,cfg)
        self.assertTrue(all(y >= 491 for y, _ in daily_text),daily_text)
        self.assertIn(name, ' '.join(value for _,value in daily_text))


if __name__ == '__main__':
    unittest.main()
