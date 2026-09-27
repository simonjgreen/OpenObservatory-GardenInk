"""Deterministic after-dark editions for the portrait Spectra 6 panel.

Unknown observations and unsupported comparison periods remain gaps. Rendering
uses only the supplied snapshot and local artwork, with no state or network I/O.
"""
from __future__ import annotations

from datetime import date
import math
from zoneinfo import ZoneInfo

from .model import status_for, timestamp
from .palette import quantise
from .render import (ASSETS, BLACK, BLUE, RED, WHITE, Page, _load_art, art,
                     bird_time, manifest, paragraph, report_period, short_name)


LAYOUTS = ('night-rhythm', 'night-history', 'night-journal')
GUIDE_OWL = {'scientific_name': 'Strix aluco', 'name': 'Tawny owl'}


def count_label(value, incomplete=False):
    return '—' if value is None else format(value, ',') + ('+' if incomplete else '')


def bat_total(night):
    value = night.get('record_count') if night.get('available', True) or night.get('cached') else None
    return count_label(value, night.get('incomplete'))


def bat_art(p, box, mode):
    x, y, width, height = box
    path = ASSETS / 'night' / 'bat.png'
    if path.is_file():
        image = _load_art(str(path), width, height, mode)
        p.im.paste(image, (x + (width - image.width) // 2, y + (height - image.height) // 2))


def diamond(p, x, y, radius=4):
    p.d.polygon(((x, y-radius), (x+radius, y), (x, y+radius), (x-radius, y)), fill=BLACK)


def dash_line(p, start, end):
    x1, y1 = start
    x2, y2 = end
    distance = math.hypot(x2-x1, y2-y1)
    if not distance:
        return
    for step in range(0, math.ceil(distance), 9):
        a, b = step/distance, min(step+5, distance)/distance
        p.d.line((x1+(x2-x1)*a, y1+(y2-y1)*a,
                  x1+(x2-x1)*b, y1+(y2-y1)*b), fill=BLACK, width=1)


def masthead(p, snapshot, settings, night, zone):
    p.tracked((24, 17), 'OPEN OBSERVATORY', 9, 1.5)
    p.text((23, 39), settings.title, 40, 'serif', width=382)
    p.text((24, 84), 'After dark', 28, 'italic', width=385)
    evening = date.fromisoformat(night['evening_date'])
    p.text((24, 120), 'Night of '+evening.strftime('%-d %B %Y'), 12, width=427)
    p.sprig(441, 97, 0.85)
    p.rule(141)
    p.text((24, 153), report_period(night, zone), 11, width=432)


def edition_footer(p, snapshot, layout):
    p.rule(776)
    state, label = status_for(snapshot)
    if snapshot['night'].get('cached'):
        state, label = 'cached', 'Night data unavailable · cached report'
    if state != 'ok':
        # A small operational status remains visible without displacing the art.
        p.text((24, 783), label, 9, colour=BLACK if state == 'demo' else RED, width=292)
    p.text((456, 783), 'Night edition · %d / 3' % (LAYOUTS.index(layout)+1),
           9, align='right', width=132)


def featured_owl(night):
    owls = night.get('owls') or []
    return max(owls, key=lambda row: (row.get('last', ''), row['scientific_name'])) if owls else None


def owl_panel(p, snapshot, settings, zone, y=588):
    night = snapshot['night']
    owl = featured_owl(night)
    p.rule(y-11)
    art(p, owl or GUIDE_OWL, (24, y, 197, 173), settings.artwork_mode)
    p.d.line((234, y+5, 234, y+163), fill=BLACK)
    p.tracked((253, y+6), 'OWLS TONIGHT' if owl else 'OWL FIELD GUIDE', 10, 1.15)
    if owl:
        end = paragraph(p, (253, y+32), short_name(owl), 25, 203, 'serif', max_lines=2, leading=2)
        end = paragraph(p, (253, end+6), owl['scientific_name'], 13, 203, 'italic', max_lines=1, leading=2)
        p.text((253, max(y+108, end+10)), 'Last heard at '+bird_time(owl['last'], night['as_of'], zone),
               12, width=203)
        total = count_label(owl['count'], night.get('incomplete'))
        p.text((253, y+145), total+' '+('detection' if total == '1' else 'detections')+' in this report', 11, width=203)
    else:
        p.text((253, y+39), 'Owls after dark', 23, 'serif', width=203)
        message = 'Owl records unavailable' if not night.get('available', True) else (
            'No owl detections in the records received' if night.get('incomplete') else 'No owl detections in this report')
        paragraph(p, (253, y+91), message, 12, 200, max_lines=3, leading=5)


def hourly_chart(p, night, box, *, baseline=False, owl_row=False, compact=False):
    """Plot only elapsed bins; None values never produce bars or joined medians."""
    x, y, width, height = box
    bins = night.get('bins') or []
    bottom = y+height
    if not bins:
        p.text((x+width/2, y+height/2), 'No interval data', 12, align='centre', width=width)
        return
    values = [row['count'] for row in bins if row.get('count') is not None]
    medians = [row['median'] for row in bins if baseline and row.get('median') is not None]
    highest = max(values+medians+[1])
    # Four divisions, round the ceiling upward to a useful readable interval.
    step = max(1, math.ceil(highest/4/10)*10) if highest > 4 else 1
    ceiling = max(step*4, highest)
    p.d.line((x, y, x, bottom, x+width, bottom), fill=BLACK)
    if not compact:
        for i in range(5):
            tick_y = bottom - height*i/4
            p.d.line((x-4, tick_y, x, tick_y), fill=BLACK)
            p.text((x-10, tick_y-4), '%g' % (ceiling*i/4), 10, align='right', width=31)
    slot = width/len(bins)
    gap = max(3, slot*.28)
    previous = None
    sparse = max(1, math.ceil(len(bins)/min(8, max(1, width//30))))
    label_width = slot*sparse-4 if sparse > 1 else slot-1
    for index, row in enumerate(bins):
        centre = x+slot*(index+.5)
        value = row.get('count')
        if value is not None:
            top = bottom-height*value/ceiling
            if value > 0:
                p.d.rectangle((centre-(slot-gap)/2, top, centre+(slot-gap)/2, bottom-1), fill=BLUE)
            if index % sparse == 0:
                p.text((centre, top-17), count_label(value, row.get('incomplete')), 11,
                       'bold' if not compact else 'sans', align='centre', width=label_width)
        else:
            p.text((centre, bottom-19), '—', 11, align='centre', width=slot-1)
        median = row.get('median') if baseline else None
        if median is not None:
            point = (centre, bottom-height*median/ceiling)
            if previous is not None:
                dash_line(p, previous, point)
            p.d.ellipse((point[0]-3, point[1]-3, point[0]+3, point[1]+3), fill=BLACK)
            if len(bins) <= 6:
                p.text((centre, point[1]+7), '%g' % median, 10, align='centre', width=slot-1)
            previous = point
        else:
            previous = None
        if index % sparse == 0:
            label = '%g–%g' % (row['start_hour'], row['end_hour'])
            if len(bins) > 8:
                label = '%g' % row['start_hour']
            p.text((centre, bottom+10), label, 10, align='centre', width=max(slot-1, 22))
        if owl_row:
            if row.get('owl_count'):
                diamond(p, centre, bottom+39)
            else:
                p.text((centre, bottom+34), '—', 10, align='centre', width=slot-1)


def rhythm(p, snapshot, settings, zone):
    night = snapshot['night']
    p.text((24, 186), 'THE NIGHT’S RHYTHM', 18, 'serif_bold', width=213)
    p.text((25, 220), bat_total(night), 54, 'serif', width=215)
    p.text((27, 281), 'bat detections', 17, width=210)
    bat_art(p, (244, 178, 213, 128), settings.artwork_mode)
    baseline = bool(night.get('baseline_nights'))
    hourly_chart(p, night, (55, 332, 401, 134), baseline=baseline, owl_row=True)
    p.text((24, 501), 'Owls heard', 10, width=90)
    p.text((263, 527), 'Hours after sunset', 12, align='centre', width=340)
    p.d.rectangle((95, 554, 105, 564), fill=BLUE)
    p.text((113, 554), 'Tonight', 10)
    if baseline and any(row.get('median') is not None for row in night.get('bins', [])):
        dash_line(p, (183, 559), (211, 559))
        p.d.ellipse((195, 556, 201, 562), fill=BLACK)
        p.text((220, 554), 'Previous %d nights · median' % night['baseline_nights'], 10, width=235)
    owl_panel(p, snapshot, settings, zone)


def history(p, snapshot, settings, zone):
    night = snapshot['night']
    p.tracked((24, 190), 'SEVEN NIGHTS', 10, 1.35)
    p.text((23, 214), 'An evening in', 31, 'serif', width=280)
    p.text((23, 250), 'context', 31, 'serif', width=245)
    bat_art(p, (292, 177, 165, 97), settings.artwork_mode)
    hours = night.get('comparison_hours', 0)
    p.text((24, 294), 'First %g hours after sunset' % hours if hours else 'Completed hours after sunset', 11, width=380)
    rows = (night.get('history') or [])[-7:]
    if not rows:
        p.text((240, 412), 'Night history unavailable', 20, 'serif', align='centre', width=420)
    else:
        highest = max([row['total'] for row in rows if row.get('comparable') and row.get('total') is not None]+[1])
        axis, span = 111, 283
        p.text((443, 312), 'Owl', 10, align='centre')
        p.d.line((axis, 330, axis, 523), fill=BLACK)
        for i, row in enumerate(rows):
            y = 334+i*27
            current = row['date'] == night['evening_date']
            label = date.fromisoformat(row['date']).strftime('%-d %b')
            p.text((24, y+5), label, 11, 'bold' if current else 'sans', width=80,
                   colour=BLUE if current else BLACK)
            total = row.get('total') if row.get('comparable') else None
            if total is None:
                p.text((axis+9, y+5), '—', 12)
            else:
                length = span*total/highest
                if total > 0:
                    p.d.rectangle((axis+1, y, axis+length, y+17), fill=BLUE if current else WHITE, outline=BLUE if current else BLACK)
                    if not current:
                        for offset in range(3, max(4, int(length)-2), 4):
                            p.d.line((axis+offset, y+15, min(axis+offset+13, axis+length-1), y+2), fill=BLACK)
                p.text((min(axis+length+6, 401), y+5), count_label(total, row.get('incomplete')), 10, width=34)
            if row.get('owl_count') is None or not row.get('comparable'):
                p.text((443, y+5), '—', 10, align='centre')
            elif row['owl_count'] > 0:
                diamond(p, 443, y+9)
        p.text((263, 537), 'Bat detections', 12, align='centre')
        known = [row for row in rows if row.get('owl_count') is not None and row.get('comparable')]
        heard = sum(row['owl_count'] > 0 for row in known)
        if known:
            p.text((240, 559), 'Owls heard on %d of %d recorded nights' % (heard, len(known)), 13,
                   'serif', align='centre', width=428)
    owl_panel(p, snapshot, settings, zone)


def journal(p, snapshot, settings, zone):
    night = snapshot['night']
    owl = featured_owl(night)
    if not owl:
        p.tracked((24, 185), 'THE NIGHT FIELD JOURNAL', 10, 1.2)
        p.text((24, 211), 'Bats after sunset', 32, 'serif', width=432)
        bat_art(p, (24, 258, 432, 216), settings.artwork_mode)
        p.text((24, 495), bat_total(night), 42, 'serif', width=190)
        p.text((211, 507), 'bat detections', 19, width=245)
        if night.get('first_bat') and not night.get('incomplete'):
            p.text((24, 550), 'First recorded at '+bird_time(night['first_bat'], night['as_of'], zone), 12, width=432)
        owl_panel(p, snapshot, settings, zone)
        return
    p.tracked((24, 185), 'HEARD TONIGHT', 10, 1.3)
    p.text((24, 209), short_name(owl), 35, 'serif', width=432)
    p.text((24, 251), owl['scientific_name'], 20, 'italic', width=432)
    art(p, owl, (24, 282, 285, 275), settings.artwork_mode)
    p.text((322, 343), 'Last heard at', 12, width=134)
    p.text((322, 365), bird_time(owl['last'], night['as_of'], zone), 20, 'serif', width=134)
    total = count_label(owl['count'], night.get('incomplete'))
    p.text((322, 407), total+' '+('detection' if total == '1' else 'detections'), 18, 'serif', width=134)
    p.text((322, 435), 'in this report', 12, width=134)
    p.rule(470, 322, 381)
    paragraph(p, (322, 489), 'A voice after dark.', 17, 132, 'italic', max_lines=3)
    p.rule(573)
    p.tracked((24, 591), 'BATS THIS EVENING', 10, 1.0)
    bat_art(p, (24, 613, 203, 99), settings.artwork_mode)
    p.text((125, 716), bat_total(night), 34, 'serif', align='centre', width=201)
    p.text((125, 755), 'bat detections', 12, align='centre', width=201)
    p.d.line((244, 592, 244, 763), fill=BLACK)
    p.text((353, 596), 'Bat detections', 12, align='centre', width=199)
    hourly_chart(p, night, (266, 641, 190, 91), compact=True)
    p.text((361, 760), 'Hours after sunset', 10, align='centre', width=190)


def render_night(snapshot, settings, layout):
    if layout not in LAYOUTS:
        raise ValueError('Unknown night layout: '+str(layout))
    _load_art.cache_clear()
    manifest.cache_clear()
    p = Page()
    zone = ZoneInfo(settings.timezone)
    masthead(p, snapshot, settings, snapshot['night'], zone)
    {'night-rhythm': rhythm, 'night-history': history, 'night-journal': journal}[layout](p, snapshot, settings, zone)
    edition_footer(p, snapshot, layout)
    return quantise(p.im, dither=False).convert('RGB')
