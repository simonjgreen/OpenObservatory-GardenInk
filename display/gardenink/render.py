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
        w, h = max(1, b[2]-b[0]), max(1, b[3]-b[1])
        mask = Image.new('L', (w,h), 0)
        ImageDraw.Draw(mask).text((-b[0],-b[1]),value,font=f,fill=255)
        # Crisp native-colour type, not noisy six-colour text dithering.
        mask = mask.point(lambda p: 255 if p >= 112 else 0)
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
        # selected light, genuinely chromatic ink with a native spot colour instead.
        bw=ImageOps.grayscale(im).convert('1',dither=getattr(Image,'Dither',Image).FLOYDSTEINBERG)
        shades=list(bw.get_flattened_data() if hasattr(bw,'get_flattened_data') else bw.getdata())
        him=im.convert('HSV')
        hsv=list(him.get_flattened_data() if hasattr(him,'get_flattened_data') else him.getdata())
        pixels=[]
        for i,(shade,(h,s,v)) in enumerate(zip(shades,hsv)):
            colour=WHITE if shade else BLACK
            if not shade and s>=68 and v>=135:
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
    return feature, others[:4]


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


def status_line(p, snap):
    state, _ = status_for(snap)
    labels = {'ok':'Recording OK when sampled', 'demo':'DEMO · sample detections',
              'offline':'OFFLINE · cached edition' if snap.get('cached') else 'OFFLINE · no station data',
              'paused':'Recording paused', 'not_live':'Not live microphone audio',
              'capture_error':'Capture needs attention', 'clock':'Station / Pi clock mismatch',
              'degraded':'Station needs attention', 'unknown':'Capture status unavailable'}
    colour = GREEN if state=='ok' else YELLOW if state in ('demo','paused','unknown') else RED
    p.d.ellipse((25,111,31,117),fill=colour,outline=BLACK)
    p.text((39,110),labels[state],10,'bold' if state not in ('ok','demo') else 'sans',width=280)
    p.text((456,110),'Hourly field notes',10,'italic',align='right',width=128)


def render(snapshot: dict, settings, layout=None) -> Image.Image:
    # New art is installed atomically by another process; do not retain stale PNGs.
    _load_art.cache_clear()
    manifest.cache_clear()
    p = Page()
    z = ZoneInfo(settings.timezone)
    now = timestamp(snapshot['as_of']).astimezone(z)
    p.tracked((25,19),'OPEN OBSERVATORY',9,1.6)
    p.text((24,42),settings.title,39,'serif',width=379)
    p.text((25,85),now.strftime('%A, %-d %B %Y'),11,width=321)
    p.sprig(443,82,0.78)
    p.rule(101)
    status_line(p,snapshot)
    if (layout or settings.layout) == 'gallery':
        today_gallery(p,snapshot,settings,z)
    else:
        hourly_journal(p,snapshot,settings,z)
    footer(p,snapshot,settings,z)
    return quantise(p.im,dither=False).convert('RGB')


def hourly_journal(p, snap, cfg, z):
    today, hour = snap['today'], snap['last_hour']
    main, daily = selections(snap)
    p.tracked((25,139),'HEARD IN THE LAST HOUR',10,1.2)
    p.text((25,158),report_period(hour,z),10,'sans',width=430)
    if main:
        path = artwork_path(main)
        if path:
            art(p,main,(24,181,232,210),cfg.artwork_mode)
        else:
            # An honest botanical accent, not a lookalike bird or giant missing-image error.
            p.sprig(116,331,1.7)
            p.sprig(153,343,1.1)
            p.text((139,367),'Illustration not yet available',10,align='centre',width=227)
        p.d.line((267,185,267,390),fill=BLACK,width=1)
        name = short_name(main)
        y = paragraph(p,(283,191),name,24,171,'serif',max_lines=3,leading=5)
        y = paragraph(p,(283,y+12),main['scientific_name'],12,171,'italic',max_lines=2,leading=4)
        y = max(303,y+18)
        p.text((283,y),'Heard at '+bird_time(main['last'],snap['as_of'],z),12,'bold',width=171)
        count = format(main['count'],',')+('+' if hour['incomplete'] else '')
        paragraph(p,(283,y+25),count+' '+('detection' if count=='1' else 'detections')+' this hour',
                  12,171,max_lines=2,leading=4)
        others = hour['species'][1:]
        if others:
            names = ' · '.join(short_name(b) for b in others[:3])
            if len(others)>3: names += ' · +%d more' % (len(others)-3)
            p.text((25,407),'Also this hour',10,'bold')
            p.text((25,424),names,12,'serif',width=431)
        else:
            p.text((25,416),'One species identified in this hour'+(' so far' if hour['incomplete'] else ''),
                   12,'italic',width=431)
    else:
        state = status_for(snap)[0]
        if snap.get('offline') and not snap.get('cached'):
            heading = 'Waiting for the station'
            detail = 'No current observations are available.'
        elif hour['incomplete']:
            heading = 'This hour is incomplete'
            detail = 'No qualifying IDs in the records received.'
        elif state in ('paused','not_live','capture_error','unknown','degraded','clock'):
            heading = 'No recent identifications'
            detail = 'Check the recording status above.'
        else:
            heading = 'No bird IDs this hour'
            detail = 'Earlier observations remain below.' if today['species'] else 'A new page in the garden journal.'
        garden_vignette(p,137,183,204,116)
        p.text((240,326),heading,24,'serif',align='centre',width=426)
        p.text((240,366),detail,12,align='centre',width=426)
        p.text((240,407),'No detection is not proof of silence.',10,'italic',align='centre',width=426)
    p.rule(448)
    p.tracked((25,465),'HEARD TODAY',10,1.4)
    p.text((456,466),'Other frequent callers',10,'italic',align='right',width=226)
    if not daily:
        if today['species']:
            msg = 'Only the featured species recorded today'
        elif snap.get('offline') and not snap.get('cached'):
            msg = 'Today’s observations are unavailable'
        else:
            msg = 'No qualifying bird IDs yet today'
        p.text((240,548),msg,19,'serif',align='centre',width=420)
        p.text((240,585),'Today begins at local midnight.',11,'italic',align='centre')
        return
    for i, bird in enumerate(daily):
        x = 24 + i*110
        if i: p.d.line((x-5,498,x-5,673),fill=BLACK,width=1)
        if artwork_path(bird):
            art(p,bird,(x,493,102,100),cfg.artwork_mode)
        else:
            p.sprig(x+43,566,0.75)
        paragraph(p,(x,601),short_name(bird),13,102,'serif',max_lines=2,leading=2)
        paragraph(p,(x,635),bird['scientific_name'],10,102,'italic',max_lines=2,leading=1)
        p.text((x,664),'Heard '+bird_time(bird['last'],snap['as_of'],z),10,'sans',width=100)
        # Counts are shown in the main total; timestamps make this row glanceable.


def today_gallery(p, snap, cfg, z):
    p.tracked((25,139),'HEARD TODAY',10,1.3)
    p.text((456,140),'Since local midnight',10,'italic',align='right')
    birds = snap['today']['species'][:6]
    if not birds:
        garden_vignette(p,128,241,224,132)
        p.text((240,420),'No qualifying bird IDs today',21,'serif',align='centre',width=425)
        return
    for i,bird in enumerate(birds):
        x=24+(i%2)*224; y=163+(i//2)*173
        art(p,bird,(x+7,y+1,194,103),cfg.artwork_mode)
        p.text((x+104,y+111),short_name(bird),18,'serif',align='centre',width=205)
        p.text((x+104,y+139),'Heard '+bird_time(bird['last'],snap['as_of'],z),11,align='centre',width=203)
        if i<4: p.rule(y+164,x,x+207)
    p.d.line((240,176,240,672),fill=BLACK,width=1)


def footer(p, snap, cfg, z):
    today, hour = snap['today'], snap['last_hour']
    p.rule(688)
    if snap.get('offline') and not snap.get('cached'):
        p.text((240,714),'No current station data',22,'serif',align='centre',width=426)
    else:
        for x,window,key,l1,l2,width in (
            (24,today,'species_count','species','today',94),
            (135,today,'record_count','detections','today',119),
            (269,hour,'species_count','species','last hour',85),
        ):
            p.text((x,703),number(window,key),29,'serif',width=width)
            p.text((x,741),l1,11,width=width)
            p.text((x,756),l2,11,width=width)
        p.d.line((123,704,123,767),fill=BLACK,width=1)
        p.d.line((258,704,258,767),fill=BLACK,width=1)
        garden_vignette(p,365,703,90,52)
        p.text((411,762),'Small moments.',8,'italic',align='centre',width=98)
    if snap.get('demo') or snap.get('fixture'):
        note='DEMO · invented records, not your garden'
    elif snap.get('offline') and snap.get('cached'):
        note='CACHED · both windows end at the printed report period'
    elif today['incomplete'] or hour['incomplete']:
        note='+ means at least · scan incomplete · counts are detections'
    else:
        note='Acoustic IDs, not visits · a new report each hour'
    p.text((240,784),note,9,align='centre',width=449)
