"""Render real pages: catch small fitted type, clipped labels and collisions."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gardenink.config import Settings
from gardenink.demo import demo_snapshot
from gardenink.night_demo import demo_night_snapshot
from gardenink.model import timestamp
from gardenink.render import Page, font, render, illustrated_species


def text_runs(snapshot, layout, settings=None):
    runs = []
    rules = []
    original_rule = Page.rule
    def rule(page,y,x1=24,x2=456,**kwargs):
        rules.append((x1,y,x2))
        return original_rule(page,y,x1,x2,**kwargs)
    original = Page.text
    def capture(page, xy, value, size=16, style='sans', colour=(0,0,0), **kw):
        w, h = original(page, xy, value, size, style, colour, **kw)
        x,y = xy
        if kw.get('align') == 'centre': x -= w//2
        if kw.get('align') == 'right': x -= w
        runs.append(((x,y,x+w,y+h), str(value), size, style, kw.get('width')))
        return w,h
    with patch.object(Page, 'text', capture), patch.object(Page,'rule',rule):
        image = render(snapshot, settings or Settings(), layout)
    return image,runs,rules


class PageReadabilityTests(unittest.TestCase):
    def assert_readable(self, snap, layout):
        _,runs,rules = text_runs(snap,layout)
        for box,value,size,style,width in runs:
            self.assertGreaterEqual(size,14,value)
            self.assertNotEqual(style,'italic',value)
            if width is not None:
                self.assertLessEqual(font(size,style).getlength(value),width,('silently fitted',value))
            self.assertGreaterEqual(box[0],23,value)
            self.assertLessEqual(box[2],457,value)
            self.assertGreaterEqual(box[1],16,value)
            self.assertLessEqual(box[3],793,value)
        for box,value,*_ in runs:
            for x1,y,x2 in rules:
                self.assertFalse(box[0]<x2 and box[2]>x1 and box[1]<y<box[3],('rule crosses text',value,y))
        for i,(a,av,*_) in enumerate(runs):
            for b,bv,*_ in runs[i+1:]:
                self.assertFalse(a[0]<b[2] and a[2]>b[0] and a[1]<b[3] and a[3]>b[1],(av,bv))
        return ' '.join(v for _,v,*_ in runs)

    def test_all_night_editions_keep_selected_type_legible(self):
        for layout in ('night-rhythm','night-history','night-journal'):
            for variant in ('normal','no-owl','partial-cached','long-night','long-owl','dst','large-counts','maximum-labels'):
                with self.subTest(layout=layout,variant=variant):
                    snap=demo_night_snapshot(Settings())
                    night=snap['night']
                    if variant=='no-owl': night['owls']=[]
                    if variant=='partial-cached':
                        night.update(incomplete=True,cached=True,available=False)
                        snap.update(offline=True,cached=True)
                        snap['health']['pause']['active']=True
                    if variant=='long-night':
                        night['bins']=[dict(start_hour=i,end_hour=i+1,count=10+i,median=None,owl_count=0) for i in range(16)]
                    if variant=='long-owl':
                        night['owls'][0].update(name='A very long local name for this owl in the garden',scientific_name='Unknownus verylongspeciesname')
                    if variant=='maximum-labels':
                        night['owls'][0].update(name='W'*100,scientific_name='Strix '+'W'*94)
                    if variant=='large-counts':
                        night['record_count']=32000
                        for row in night['bins']: row.update(count=8000,median=7500)
                        for row in night['history']: row['total']=32000
                    if variant=='dst':
                        night.update(since='2026-10-25T00:30:00Z',as_of='2026-10-25T01:30:00Z')
                    text=self.assert_readable(snap,layout)
                    if variant=='partial-cached':
                        for word in ('cached','at least','PAUSED'): self.assertIn(word,text)

    def test_unknown_interval_is_visible_even_between_thinned_axis_labels(self):
        from gardenink.night_render import hourly_chart
        bins=[dict(start_hour=i,end_hour=i+1,count=0,median=None,owl_count=0) for i in range(16)]
        known=Page()
        hourly_chart(known,{'bins':bins},(64,342,392,100))
        bins[1]['count']=None
        unknown=Page()
        hourly_chart(unknown,{'bins':bins},(64,342,392,100))
        self.assertTrue(known.im.tobytes()!=unknown.im.tobytes(),'Unknown interval vanished')

    def test_gallery_reflows_long_labels_instead_of_overlapping_next_row(self):
        snap=demo_snapshot(Settings(),timestamp('2026-09-27T11:01:00Z'))
        snap['today']['species'][0].update(name='A very long local name for a bird identified in this garden awaiting review by the local station operator before the identification can be confirmed',scientific_name='Unknownus longname')
        text=self.assert_readable(snap,'gallery')
        self.assertIn(snap['today']['species'][0]['name'],text)
        self.assertLessEqual(len(illustrated_species(snap,'gallery')),4)
