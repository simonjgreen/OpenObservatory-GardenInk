"""Frozen, sample-only full-page comparisons for the selected E typography.

Not a production renderer: only the included complete daytime fixture is supported.
No network, GPIO, live state or paid artwork calls.
"""
from datetime import datetime, timezone
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'display'))
from PIL import Image, ImageDraw
from gardenink.config import Settings
from gardenink.demo import demo_snapshot
from gardenink.render import Page, font, art, selections, short_name, bird_time, report_period, number
from gardenink.palette import COLOURS

BLACK = COLOURS[0]


class MonoPage(Page):
    def __init__(self):
        super().__init__()
        self.text_boxes = []

    def text(self, xy, value, size=14, style='sans', colour=BLACK, align='left', width=None):
        value = str(value)
        face = font(size, style)
        box = face.getbbox(value)
        mask = Image.new('L', (480, size*3+20), 0)
        draw = ImageDraw.Draw(mask)
        draw.fontmode = '1'
        draw.text((4-box[0], 4-box[1]), value, font=face, fill=255)
        ink = mask.getbbox()
        assert ink and ink[0] > 0 and ink[1] > 0 and ink[2] < 479
        mask = mask.crop(ink)
        w, h = mask.size
        assert width is None or w <= width, (value, size, w, width)
        x, y = xy
        if align == 'centre': x -= w//2
        if align == 'right': x -= w
        bounds = (int(x), int(y), int(x)+w, int(y)+h)
        assert bounds[0] >= 24 and bounds[2] <= 456 and bounds[1] >= 16 and bounds[3] <= 791, (value, bounds)
        for old, label in self.text_boxes:
            assert not (bounds[0] < old[2] and bounds[2] > old[0] and bounds[1] < old[3] and bounds[3] > old[1]), (value, label)
        self.text_boxes.append((bounds, value))
        self.im.paste(colour, bounds[:2], mask)
        return w, h

    def wrap(self, x, y, value, width, size=14, style='sans', lines=2):
        result = []
        line = ''
        for word in value.split():
            trial = (line+' '+word).strip()
            if line and font(size, style).getlength(trial) > width:
                result.append(line)
                line = word
            else:
                line = trial
        if line: result.append(line)
        assert len(result) <= lines, (value, result)
        for index, line in enumerate(result):
            self.text((x, y+index*(size+4)), line, size, style, width=width)
        return y + len(result)*(size+4)


def render_trial(cards):
    assert cards in (2, 3)
    cfg = Settings()
    snap = demo_snapshot(cfg, datetime(2026, 9, 27, 11, 1, tzinfo=timezone.utc))
    assert snap['demo'] and not snap['today']['incomplete'] and not snap['last_hour']['incomplete']
    p = MonoPage()
    z = ZoneInfo(cfg.timezone)
    main, daily = selections(snap)
    letter = 'H' if cards == 2 else 'I'
    p.text((24, 18), f'SAMPLE {letter} · {cards} daily cards · selected font E', 14)
    p.text((24, 46), 'The garden', 34, 'serif')
    p.sprig(443, 96, .7)
    p.text((24, 89), 'Sunday, 27 September 2026', 14)
    p.rule(113)
    p.text((24, 127), 'Sample observations · layout comparison', 14)
    p.text((24, 159), 'Heard in the last hour', 16, 'bold')
    p.text((24, 185), report_period(snap['last_hour'], z), 14)
    art(p, main, (24, 215, 228, 173), cfg.artwork_mode)
    p.d.line((266, 216, 266, 383), fill=BLACK, width=1)
    y = p.wrap(283, 220, short_name(main), 173, 24, lines=2)
    p.wrap(283, y+12, main['scientific_name'], 173, 14, lines=2)
    p.text((283, 325), 'Heard at '+bird_time(main['last'], snap['as_of'], z), 14, width=173)
    p.wrap(283, 352, str(main['count'])+' detections this hour', 173, 14)
    p.text((24, 404), 'Also this hour', 14, 'bold')
    other = ' · '.join(short_name(b) for b in snap['last_hour']['species'][1:])
    p.text((24, 427), other, 14, width=432)
    p.rule(453)
    p.text((24, 467), f'Heard today · {cards} other frequent species', 14, 'bold')
    step = 432//cards
    for i, bird in enumerate(daily[:cards]):
        x = 24+i*step
        width = step-12
        if i: p.d.line((x-6, 494, x-6, 661), fill=BLACK, width=1)
        art(p, bird, (x, 491, width, 77), cfg.artwork_mode)
        p.wrap(x, 577, short_name(bird), width, 18, lines=2)
        p.wrap(x, 620, bird['scientific_name'], width, 14, lines=2)
        # The time sits above the scientific name for no compression of either.
        p.text((x, 602), 'Heard '+bird_time(bird['last'], snap['as_of'], z), 14, width=width)
    p.rule(672)
    for offset, window, label in ((0, snap['today'], 'Today'), (216, snap['last_hour'], 'Report hour')):
        p.text((132+offset, 685), label, 14, align='centre')
        for x, key, noun in ((73, 'species_count', 'species'), (181, 'record_count', 'detections')):
            p.text((x+offset, 710), number(window, key), 28, align='centre', width=98)
            p.text((x+offset, 743), noun, 14, align='centre')
    p.d.line((240, 684, 240, 757), fill=BLACK, width=1)
    p.text((240, 776), 'Acoustic IDs, not individual birds', 14, align='centre')
    pixels = p.im.get_flattened_data() if hasattr(p.im, 'get_flattened_data') else p.im.getdata()
    assert p.im.size == (480, 800) and set(pixels) <= set(COLOURS)
    return p.im, snap, p.text_boxes


if __name__ == '__main__':
    import json
    folder = Path('local/previews/readability-layout')
    folder.mkdir(parents=True, exist_ok=True)
    snapshots = []
    for cards, label in ((2, 'H'), (3, 'I')):
        image, snapshot, boxes = render_trial(cards)
        image.save(folder / (label+'.png'))
        snapshots.append(snapshot)
        (folder / (label+'-text.json')).write_text(json.dumps(boxes, indent=2)+'\n')
        print(f'{label}: {len(boxes)} text runs checked for bounds and overlap')
    assert snapshots[0] == snapshots[1]
    (folder/'sample.json').write_text(json.dumps(snapshots[0], indent=2)+'\n')
