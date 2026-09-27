from __future__ import annotations
import json
import math
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont, ImageOps
from .config import ROOT
from .model import timestamp, status_for
from .palette import COLOURS, RESAMPLE, quantise

BLACK, WHITE, YELLOW, RED, BLUE, GREEN = COLOURS
WIDTH, HEIGHT = 480, 800
ASSETS = ROOT / 'assets'
# Ordered coverage for the selected strong wash: fill ~70% of eligible white gaps.
WASH_PATTERN = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))

@lru_cache(maxsize=128)
def font(size: int, style: str = 'sans'):
    names = {'sans':'DejaVuSans.ttf', 'bold':'DejaVuSans-Bold.ttf',
             'serif':'DejaVuSerif.ttf', 'serif_bold':'DejaVuSerif-Bold.ttf',
             'italic':'DejaVuSerif-Italic.ttf'}
    name = names[style]
    choices = [Path('/usr/share/fonts/truetype/dejavu')/name,
               Path('/usr/share/fonts/dejavu')/name]
    for p in choices:
        if p.exists(): return ImageFont.truetype(str(p), size)
    raise RuntimeError('DejaVu fonts missing. Run ./install.sh (fonts-dejavu-core).')

class Page:
    def __init__(self):
        self.im = Image.new('RGB', (WIDTH, HEIGHT), WHITE)
        self.d = ImageDraw.Draw(self.im)

    def text(self, xy, value, size=16, style='sans', colour=BLACK, align='left', width=None):
        value = str(value)
        f = font(size, style)
        if width is not None:
            while size > 10 and f.getlength(value) > width:
                size -= 1; f = font(size, style)
            while f.getlength(value) > width and len(value) > 1:
                value = value[:-2].rstrip('…') + '…'
        b = f.getbbox(value)
        # Render monochrome glyphs directly (selected physical trial E).
        # Padding retains hinted pixels beyond the antialiased font bounds.
        mask = Image.new('L', (max(1,b[2]-b[0])+8,max(1,b[3]-b[1])+8), 0)
        draw = ImageDraw.Draw(mask)
        draw.fontmode = '1'
        draw.text((4-b[0],4-b[1]),value,font=f,fill=255)
        ink = mask.getbbox()
        if ink:
            mask = mask.crop(ink)
        w,h = mask.size
        x,y = xy
        if align == 'right': x -= w
        if align == 'centre': x -= w//2
        self.im.paste(colour, (int(x),int(y)), mask)
        return w,h

    def tracked(self,xy,value,size=11,spacing=2,colour=BLACK):
        x,y=xy
        for ch in value:
            self.text((x,y),ch,size,'sans',colour)
            x += font(size).getlength(ch)+spacing
        return x

    def rule(self,y,x1=24,x2=456,colour=BLACK):
        self.d.line((x1,y,x2,y),fill=colour,width=1)

    def sprig(self,x,y,scale=1,colour=BLACK):
        points=[]
        for i in range(41):
            t=i/40
            points.append((x+scale*(9*math.sin(t*2)),y-scale*t*61))
        self.d.line(points,fill=colour,width=max(1,round(scale)))
        for i in range(2,8):
            t=i/8
            cx=x+scale*9*math.sin(t*2); cy=y-scale*t*61
            side=-1 if i%2 else 1
            self.d.polygon([(cx,cy),(cx+side*scale*12,cy-scale*9),
                            (cx+side*scale*8,cy+scale*1)],fill=colour)

@lru_cache(maxsize=1)
def manifest():
    return json.loads((ASSETS/'manifest.json').read_text(encoding='utf-8'))


def artwork_path(species: dict):
    from .artfiles import find_art
    return find_art(species, ASSETS)


def short_name(species):
    entry=manifest().get(species['scientific_name'].casefold())
    if entry:
        return entry.get('display_name') or entry['aliases'][0].title()
    return species['name']

@lru_cache(maxsize=80)
def _load_art(path: str, width: int, height: int, mode: str):
    with Image.open(path) as source:
        if source.width*source.height > 12000000:
            raise ValueError('Custom artwork exceeds 12 megapixels')
        source=source.convert('RGBA')
        bg=Image.new('RGBA',source.size,WHITE+(255,))
        bg.alpha_composite(source)
        im=ImageOps.contain(bg.convert('RGB'),(width,height),RESAMPLE.LANCZOS)
    if mode == 'ink':
        im=ImageOps.grayscale(im).convert('1',dither=getattr(Image,'Dither',Image).FLOYDSTEINBERG).convert('RGB')
    else:
        # Keep graphite/neutral tones in black and white. A generic RGB-to-six-colour
        # Floyd quantiser makes grey feathers into red/blue confetti; replace only
        # light, genuinely chromatic ink with a native spot colour instead. The
        # strong wash also fills selected white gaps without changing dark detail.
        bw=ImageOps.grayscale(im).convert('1',dither=getattr(Image,'Dither',Image).FLOYDSTEINBERG)
        shades=list(bw.get_flattened_data() if hasattr(bw,'get_flattened_data') else bw.getdata())
        him=im.convert('HSV')
        hsv=list(him.get_flattened_data() if hasattr(him,'get_flattened_data') else him.getdata())
        pixels=[]
        for i,(shade,(h,s,v)) in enumerate(zip(shades,hsv)):
            colour=WHITE if shade else BLACK
            x,y=i%im.width,i//im.width
            wash_gap = (WASH_PATTERN[y%4][x%4]+0.5)/16 < 0.70
            if (not shade or wash_gap) and s>=68 and v>=135:
                if h<20:
                    colour=YELLOW if h>=10 and (i%im.width+ i//im.width)%4==0 else RED
                elif h<48: colour=YELLOW
                elif h<126: colour=GREEN
                elif h<190: colour=BLUE
            pixels.append(colour)
        im=Image.new('RGB',im.size);im.putdata(pixels)
    return im


def art(page: Page, species, box, mode):
    x,y,w,h=box
    path=artwork_path(species)
    if path:
        im=_load_art(str(path),w,h,mode)
        page.im.paste(im,(x+(w-im.width)//2,y+(h-im.height)//2))
    else:
        page.sprig(x+w//2-5,y+h//2+23,0.9)
        page.text((x+w//2,y+h-19),'No species sketch',11,align='centre',width=w)


def prose_time(t):
    """An observation timestamp, never digital-clock typography."""
    hour = t.hour % 12 or 12
    minutes = ('.%02d' % t.minute) if t.minute else ''
    return str(hour) + minutes + ('am' if t.hour < 12 else 'pm')


def bird_time(when,as_of,zone):
    t=timestamp(when).astimezone(zone)
    now=timestamp(as_of).astimezone(zone)
    label=prose_time(t)
    if t.date()!=now.date(): label=t.strftime('%d %b, ')+label
    if t.utcoffset()!=now.utcoffset(): label+=' '+t.strftime('%Z')
    return label


def report_period(window, zone):
    a,b=timestamp(window['since']).astimezone(zone),timestamp(window['as_of']).astimezone(zone)
    left=prose_time(a)
    right=prose_time(b)+' '+b.strftime('%Z')
    if a.utcoffset()!=b.utcoffset(): left+=' '+a.strftime('%Z')
    if a.date()!=b.date(): left=a.strftime('%d %b, ')+left
    return 'Report covers '+left+' to '+right


def paragraph(p, xy, value, size, width, style='sans', max_lines=3, leading=4, colour=BLACK):
    """Measured wrapping, with bounded ellipsis rather than overflowing a card."""
    words = str(value).split()
    lines, line = [], ''
    for word in words:
        trial = (line + ' ' + word).strip()
        if line and font(size, style).getlength(trial) > width:
            lines.append(line)
            line = word
        else:
            line = trial
    if line: lines.append(line)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip('…') + '…'
    y = xy[1]
    for line in lines:
        p.text((xy[0], y), line, size, style, width=width, colour=colour)
        y += size + leading
    return y


def number(window, key):
    return format(window.get(key, 0), ',') + ('+' if window.get('incomplete') else '')


def time_range(window, zone, with_date=False):
    a, b = timestamp(window['since']).astimezone(zone), timestamp(window['as_of']).astimezone(zone)
    if a.utcoffset() != b.utcoffset():
        # Disambiguate the repeated clock hour in autumn.
        return a.strftime('%H:%M %Z') + '–' + b.strftime('%H:%M %Z')
    if a.date() != b.date() or with_date:
        return a.strftime('%d %b %H:%M') + '–' + b.strftime('%H:%M')
    return a.strftime('%H:%M') + '–' + b.strftime('%H:%M')


def selections(snap):
    hour = snap['last_hour']['species']
    feature = hour[0] if hour else None
    key = feature['scientific_name'].casefold() if feature else ''
    daily = sorted(snap['today']['species'],
                   key=lambda b: (-b['count'], b['scientific_name'].casefold()))
    others = [b for b in daily if b['scientific_name'].casefold() != key]
    return feature, others[:3]


def illustrated_species(snap, layout):
    """Species with image slots on this page, excluding text-only mentions."""
    if layout in ('night-rhythm', 'night-history', 'night-journal'):
        from .night_render import featured_owl, GUIDE_OWL
        return [featured_owl(snap.get('night') or {}) or GUIDE_OWL]
    if layout == 'gallery':
        return snap['today']['species'][:6]
    feature, daily = selections(snap)
    daily, _ = daily_cards(daily, snap)
    return ([feature] if feature else []) + daily


def garden_vignette(p, x, y, w, h):
    """Small procedural woodcut-style hedgerow; decoration, never a data chart."""
    import random
    rng = random.Random(42)
    im = Image.new('RGB', (300, 170), WHITE)
    d = ImageDraw.Draw(im)
    # Ground, fence and a small tree, with sparse stippled leaves.
    d.line([(0,146),(60,148),(108,145),(168,151),(245,148),(300,152)],fill=BLACK,width=2)
    for fx in range(10,291,18):
        d.line((fx,134,fx,158),fill=BLACK,width=1)
    d.line((0,141,300,145),fill=BLACK,width=1)
    d.line([(165,147),(165,111),(157,75)],fill=BLACK,width=4)
    for end in ((113,55),(136,40),(177,37),(205,65)):
        d.line([(165,124),(154,83),end],fill=BLACK,width=2)
    for _ in range(630):
        px,py=rng.gauss(155,36),rng.gauss(65,22)
        if ((px-155)/64)**2+((py-65)/42)**2 < 1:
            r=rng.choice([1,1,2])
            d.ellipse((px-r,py-r,px+r,py+r),fill=BLACK)
    for i in range(21):
        bx=i*15+rng.randrange(-4,5); by=149+rng.randrange(-4,4)
        top=by-rng.randrange(22,78)
        d.line((bx,by,bx+5,top),fill=BLACK,width=1)
        for k in range(3):
            yy=top+9+k*11
            d.line((bx+3,yy,bx-6,yy-5),fill=BLACK,width=1)
            d.line((bx+3,yy+5,bx+12,yy),fill=BLACK,width=1)
        for a in range(6):
            px=bx+5+math.cos(a*math.pi/3)*4
            py=top+math.sin(a*math.pi/3)*4
            d.ellipse((px-1,py-1,px+1,py+1),fill=BLACK)
    p.im.paste(im.resize((w,h),RESAMPLE.LANCZOS).convert('1').convert('RGB'),(x,y))


def text_lines(value, width, size=14, style='sans'):
    """Wrap at native size; break an overlong token instead of shrinking it."""
    lines, line = [], ''
    for word in str(value).split():
        trial = (line+' '+word).strip()
        if line and font(size, style).getlength(trial) > width-2:
            lines.append(line)
            line = ''
        while font(size, style).getlength(word) > width-2:
            end = 1
            while end < len(word) and font(size, style).getlength(word[:end+1]) <= width-2:
                end += 1
            lines.append(word[:end])
            word = word[end:]
        line = (line+' '+word).strip()
    if line: lines.append(line)
    return lines


def write_lines(p, xy, lines, size=14, style='sans', leading=4):
    y = xy[1]
    for line in lines:
        p.text((xy[0], y), line, size, style)
        y += size+leading
    return y


def readable(p, xy, value, width=432, size=14, style='sans'):
    return write_lines(p, xy, text_lines(value, width, size, style), size, style)


def daily_cards(daily, snap):
    """Default to three; give exceptional long metadata wider cards.

    Reserve two timestamp lines independent of timezone, so the same selection
    is used by the artwork watcher and the renderer.
    """
    for columns in (3, 2, 1):
        width = 432//columns-12
        chosen = daily[:columns]
        if all(len(text_lines(short_name(b),width,18))*22 + 36 +
               len(text_lines(b['scientific_name'],width))*18 <= 168 for b in chosen):
            return chosen, columns
    return daily[:1], 1


def status_line(p, snap):
    state, _ = status_for(snap)
    labels = {'ok':'Recording OK when sampled', 'demo':'SAMPLE · invented observations',
              'offline':'OFFLINE · cached edition' if snap.get('cached') else 'OFFLINE · no station data',
              'paused':'Recording paused', 'not_live':'Not live microphone audio',
              'capture_error':'Capture needs attention', 'clock':'Station / Pi clock mismatch',
              'degraded':'Station needs attention', 'unknown':'Capture status unavailable'}
    colour = GREEN if state=='ok' else YELLOW if state in ('demo','paused','unknown') else RED
    p.d.ellipse((25,130,31,136), fill=colour, outline=BLACK)
    p.text((40,127), labels[state], 14, 'bold' if state not in ('ok','demo') else 'sans')


def render(snapshot: dict, settings, layout=None) -> Image.Image:
    _load_art.cache_clear()
    manifest.cache_clear()
    if layout in ('night-rhythm', 'night-history', 'night-journal'):
        from .night_render import render_night
        return render_night(snapshot, settings, layout)
    p = Page()
    z = ZoneInfo(settings.timezone)
    now = timestamp(snapshot['as_of']).astimezone(z)
    identifier = 'SAMPLE · OPEN OBSERVATORY' if snapshot.get('demo') or snapshot.get('fixture') else 'OPEN OBSERVATORY'
    p.text((24,18), identifier, 14)
    p.text((24,46), settings.title, 34, 'serif', width=379)
    p.text((24,89), now.strftime('%A, %-d %B %Y'), 14)
    p.sprig(443,96,.7)
    p.rule(113)
    status_line(p,snapshot)
    gallery = (layout or settings.layout) == 'gallery'
    p.text((24,159), 'Heard today · since local midnight' if gallery else 'Heard in the last hour', 16, 'bold')
    period = report_period(snapshot['last_hour'],z)
    if gallery: period = period.replace('Report covers ', 'Report-hour totals · ', 1)
    end = readable(p,(24,185),period)
    top = max(215,end+12)
    if gallery:
        today_gallery(p,snapshot,settings,z,top)
    else:
        hourly_journal(p,snapshot,settings,z,top)
    footer(p,snapshot,settings,z)
    return quantise(p.im,dither=False).convert('RGB')


def hourly_journal(p, snap, cfg, z, top=215):
    today, hour = snap['today'], snap['last_hour']
    main, daily = selections(snap)
    daily, columns = daily_cards(daily, snap)
    if main:
        count = number({'count': main['count'], 'incomplete': hour['incomplete']}, 'count')
        count_text = count+' '+('detection' if count=='1' else 'detections')+' this hour'
        heard = 'Heard at '+bird_time(main['last'],snap['as_of'],z)
        width, x, size = 173, 283, 24
        name = text_lines(short_name(main),width,size)
        latin = text_lines(main['scientific_name'],width)
        times = text_lines(heard,width)
        counts = text_lines(count_text,width)
        def positions():
            latin_y = top+5+len(name)*(size+4)+12
            heard_y = max(top+110,latin_y+len(latin)*18+18)
            count_y = heard_y+len(times)*18+8
            return latin_y, heard_y, count_y
        latin_y, heard_y, count_y = positions()
        if count_y+len(counts)*18 > 399:
            size = 18
            name = text_lines(short_name(main),width,size)
            latin_y = top+5+len(name)*22+8
            heard_y = latin_y+len(latin)*18+8
            count_y = heard_y+len(times)*18+6
        if count_y+len(counts)*18 > 399:
            # Rare long local labels get the art's width, not tiny type.
            x, width = 24, 432
            name = text_lines(short_name(main),width,size)
            latin = text_lines(main['scientific_name'],width)
            times = text_lines(heard,width)
            counts = text_lines(count_text,width)
            latin_y = top+5+len(name)*22+8
            heard_y = latin_y+len(latin)*18+8
            count_y = heard_y+len(times)*18+6
        else:
            if artwork_path(main):
                art(p,main,(24,top,228,388-top),cfg.artwork_mode)
            else:
                p.sprig(125,top+105,1.25)
                readable(p,(24,top+130),'Illustration not yet available',228)
            p.d.line((266,top+1,266,390),fill=BLACK,width=1)
        write_lines(p,(x,top+5),name,size)
        write_lines(p,(x,latin_y),latin)
        write_lines(p,(x,heard_y),times)
        write_lines(p,(x,count_y),counts)
        others = hour['species'][1:]
        if others:
            shown = min(3,len(others))
            while True:
                names = ' · '.join(short_name(b) for b in others[:shown])
                if shown < len(others): names += (' · ' if names else '')+'+%d more' % (len(others)-shown)
                if font(14).getlength(names) <= 430: break
                shown -= 1
            p.text((24,404),'Also this hour',14,'bold')
            p.text((24,427),names,14)
        else:
            p.text((24,416),'One species identified in this hour'+(' so far' if hour['incomplete'] else ''),14)
    else:
        state = status_for(snap)[0]
        if snap.get('offline') and not snap.get('cached'):
            heading, detail = 'Waiting for the station', 'No current observations are available.'
        elif hour['incomplete']:
            heading, detail = 'This hour is incomplete', 'No qualifying IDs in the records received.'
        elif state in ('paused','not_live','capture_error','unknown','degraded','clock'):
            heading, detail = 'No recent identifications', 'Check the recording status above.'
        else:
            heading = 'No bird IDs this hour'
            detail = 'Earlier observations remain below.' if today['species'] else 'A new page in the garden journal.'
        garden_vignette(p,137,top,204,94)
        p.text((240,326),heading,22,align='centre',width=432)
        p.text((240,366),detail,14,align='centre')
        p.text((240,416),'No detection is not proof of silence.',14,align='centre')
    p.rule(453)
    label = 'Heard today · %d frequent species shown' % len(daily) if daily else 'Heard today'
    p.text((24,467),label,14,'bold')
    if not daily:
        if today['species']: msg = 'Only the featured species recorded today'
        elif snap.get('offline') and not snap.get('cached'): msg = 'Today’s observations are unavailable'
        else: msg = 'No qualifying bird IDs yet today'
        readable(p,(24,548),msg,size=18)
        p.text((24,604),'Today begins at local midnight.',14)
        return
    for i, bird in enumerate(daily):
        step = 432//columns
        x, width = 24+i*step, step-12
        if i: p.d.line((x-6,494,x-6,661),fill=BLACK,width=1)
        names = text_lines(short_name(bird),width,18)
        times = text_lines('Heard '+bird_time(bird['last'],snap['as_of'],z),width)
        latin = text_lines(bird['scientific_name'],width)
        # Grow the text area upwards for wraps, reducing illustration space.
        height = len(names)*22 + (len(times)+len(latin))*18
        y = min(577,660-height+4)
        art_height = min(77,max(0,y-491-8))
        if art_height >= 25 and artwork_path(bird):
            art(p,bird,(x,491,width,art_height),cfg.artwork_mode)
        elif art_height >= 50:
            p.sprig(x+width//2,491+art_height-8,.6)
        y = write_lines(p,(x,y),names,18)
        y = write_lines(p,(x,y+3),times)
        write_lines(p,(x,y),latin)


def today_gallery(p, snap, cfg, z, top=215):
    if snap.get('offline') and not snap.get('cached'):
        garden_vignette(p,128,top+20,224,132)
        readable(p,(24,420),'Today’s observations unavailable',size=21)
        return
    birds = snap['today']['species'][:6]
    if not birds:
        garden_vignette(p,128,top+20,224,132)
        p.text((240,420),'No qualifying bird IDs today',21,align='centre')
        return
    height = (666-top)//3
    for i,bird in enumerate(birds):
        x, y = 24+(i%2)*224, top+(i//2)*height
        names = text_lines(short_name(bird),205,18)
        times = text_lines('Heard '+bird_time(bird['last'],snap['as_of'],z),205)
        text_height = len(names)*22+len(times)*18
        art_height = max(0,height-text_height-14)
        if art_height >= 25 and artwork_path(bird):
            art(p,bird,(x+7,y,194,art_height),cfg.artwork_mode)
        elif art_height >= 50:
            p.sprig(x+100,y+art_height-8,.6)
        end = write_lines(p,(x,y+art_height+7),names,18)
        write_lines(p,(x,end),times)
        if i<4: p.rule(y+height-3,x,x+207)
    p.d.line((240,top,240,665),fill=BLACK,width=1)


def footer_note(snap):
    """Two readable lines; retain independent availability/count qualifications."""
    cached = snap.get('offline') and snap.get('cached')
    paused = ((snap.get('health') or {}).get('pause') or {}).get('active')
    prefix = ('CACHED · ' if cached else '')+('PAUSED · ' if paused else '')
    if snap['today']['incomplete'] or snap['last_hour']['incomplete']:
        return prefix+'+ means at least\nIncomplete scan · Acoustic IDs, not birds'
    if cached or paused:
        return prefix+'Totals end at report time\nAcoustic IDs, not individual birds'
    if not snap['last_hour']['record_count']:
        return 'No IDs in report hour · Not proof of silence\nAcoustic IDs, not individual birds'
    return 'Acoustic IDs, not individual birds'


def footer(p, snap, cfg, z):
    p.rule(672)
    if snap.get('offline') and not snap.get('cached'):
        p.text((240,704),'No current station data',22,align='centre')
        p.text((240,745),'Report totals are unavailable.',14,align='centre')
        p.text((240,779),'No cached report · Waiting for the station',14,align='centre')
        return
    for offset,window,title in ((0,snap['today'],'Today'),(216,snap['last_hour'],'Report hour')):
        p.text((132+offset,685),title,14,align='centre')
        for x,key,label in ((73,'species_count','species'),(181,'record_count','detections')):
            # Extremely large totals wrap within their cell at a readable size.
            value = number(window,key)
            size = 28 if font(28).getlength(value) <= 98 else 18
            p.text((x+offset,710),value,size,align='centre',width=98)
            p.text((x+offset,743),label,14,align='centre')
    p.d.line((240,684,240,757),fill=BLACK,width=1)
    lines = footer_note(snap).split('\n')
    for i,line in enumerate(lines):
        p.text((240,779-(len(lines)-1-i)*18),line,14,align='centre')
