"""Native, readable after-dark editions. Unknown coverage remains a gap."""
from __future__ import annotations
from datetime import date
import math
from zoneinfo import ZoneInfo
from .model import status_for
from .palette import quantise
from .render import (ASSETS, BLACK, BLUE, WHITE, Page, _load_art, art, artwork_path,
                     bird_time, manifest, report_period, short_name, font,
                     text_lines, write_lines, readable)

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
        p.im.paste(image, (x + (width-image.width)//2, y + (height-image.height)//2))


def diamond(p, x, y, radius=4):
    p.d.polygon(((x,y-radius),(x+radius,y),(x,y+radius),(x-radius,y)),fill=BLACK)


def dash_line(p, start, end):
    x1,y1=start; x2,y2=end
    distance=math.hypot(x2-x1,y2-y1)
    if not distance: return
    for step in range(0,math.ceil(distance),9):
        a,b=step/distance,min(step+5,distance)/distance
        p.d.line((x1+(x2-x1)*a,y1+(y2-y1)*a,x1+(x2-x1)*b,y1+(y2-y1)*b),fill=BLACK)


def masthead(p, snapshot, settings, night, zone, layout):
    sample = snapshot.get('demo') or snapshot.get('fixture')
    p.text((24,18),'SAMPLE · OPEN OBSERVATORY' if sample else 'OPEN OBSERVATORY',14)
    p.text((24,46),settings.title,34,'serif',width=379)
    evening=date.fromisoformat(night['evening_date'])
    p.text((24,89),'Night of '+evening.strftime('%-d %B %Y'),14)
    p.sprig(443,96,.7)
    p.rule(113)
    p.text((24,128),'After dark',18,'bold')
    p.text((456,132),'Night edition · %d / 3' % (LAYOUTS.index(layout)+1),14,align='right')
    end=readable(p,(24,162),report_period(night,zone))
    return max(211,end+12)


def edition_footer(p, snapshot, layout):
    """Room for independent capture, cached and incomplete qualifications."""
    night=snapshot['night']
    state,_=status_for(snapshot)
    labels={'offline':'OFFLINE · station unavailable','paused':'Recording PAUSED',
            'not_live':'Not live microphone audio','capture_error':'Capture needs attention',
            'clock':'Station / Pi clock mismatch','degraded':'Station needs attention',
            'unknown':'Capture status unavailable'}
    lines=[]
    if state in labels:
        label=labels[state]
        if state!='paused' and ((snapshot.get('health') or {}).get('pause') or {}).get('active'):
            label+=' · PAUSED'
        lines.append(label)
    if state not in labels and ((snapshot.get('health') or {}).get('pause') or {}).get('active'):
        lines.append('Recording PAUSED')
    if night.get('cached'):
        lines.append('Night data unavailable · cached report')
    elif not night.get('available',True):
        lines.append('Night observations unavailable')
    if night.get('incomplete'):
        lines.append('Incomplete scan · + means at least')
    if not lines:
        lines=['Acoustic detections · Historical report']
    p.rule(728)
    for i,line in enumerate(lines): p.text((24,742+i*18),line,14)


def featured_owl(night):
    owls=night.get('owls') or []
    return max(owls,key=lambda row:(row.get('last',''),row['scientific_name'])) if owls else None


def owl_panel_content(night, zone):
    owl=featured_owl(night)
    if owl:
        total=count_label(owl['count'],night.get('incomplete'))
        blocks=[(short_name(owl),18), (owl['scientific_name'],14),
                ('Last heard at '+bird_time(owl['last'],night['as_of'],zone),14),
                (total+' '+('detection' if total=='1' else 'detections')+' in this report',14)]
        title='Owls tonight'
    else:
        message='Owl records unavailable' if not night.get('available',True) else (
            'No owl detections in the records received' if night.get('incomplete') else 'No owl detections in this report')
        title='Owl field guide'
        blocks=[('Owls after dark',18),(message,14)]
    x,width=210,246
    def height(): return sum(len(text_lines(value,width,size))*(size+4)+4 for value,size in blocks)
    if height()>136: x,width=24,432
    y=min(564,714-23-height())
    return owl,title,blocks,x,width,y


def owl_panel(p, snapshot, settings, zone):
    owl,title,blocks,x,width,y=owl_panel_content(snapshot['night'],zone)
    p.rule(y-11)
    if x!=24:
        if artwork_path(owl or GUIDE_OWL):
            art(p,owl or GUIDE_OWL,(24,y+10,165,141),settings.artwork_mode)
        else:
            p.sprig(100,y+63,.7)
            readable(p,(24,y+93),'Illustration not yet available',165)
        p.d.line((196,y+5,196,713),fill=BLACK)
    p.text((x,y),title,14,'bold')
    end=y+23
    for value,size in blocks:
        end=readable(p,(x,end),value,width,size)+4


def hourly_chart(p, night, box, *, baseline=False, owl_row=False, compact=False):
    """All bins remain drawn; thin labels, never type, when the night is long."""
    x,y,width,height=box; bottom=y+height
    bins=night.get('bins') or []
    if not bins:
        p.text((x+width/2,y+height/2),'No interval data',14,align='centre')
        return
    values=[r['count'] for r in bins if r.get('count') is not None]
    medians=[r['median'] for r in bins if baseline and r.get('median') is not None]
    highest=max(values+medians+[1])
    step=max(1,math.ceil(highest/4/10)*10) if highest>4 else 1
    ceiling=max(step*4,highest)
    if not compact:
        axis_width=max(font(14).getlength('%g' % (ceiling*i/4)) for i in (0,2,4))
        inset=max(0,math.ceil(24+9+axis_width-x))
        x+=inset; width-=inset
    p.d.line((x,y,x,bottom,x+width,bottom),fill=BLACK)
    if not compact:
        for i in (0,2,4):
            tick=bottom-height*i/4
            p.d.line((x-4,tick,x,tick),fill=BLACK)
            p.text((x-9,tick-5),'%g' % (ceiling*i/4),14,align='right')
    slot=width/len(bins); gap=max(3,slot*.28)
    interval_labels=['%g–%g' % (r['start_hour'],r['end_hour']) for r in bins]
    widest=max(font(14).getlength(v) for v in interval_labels)
    sparse=max(1,math.ceil((widest+12)/slot))
    # Numeric value labels are optional annotations; the full bars preserve data.
    count_width=max(font(14).getlength(count_label(r.get('count'),r.get('incomplete'))) for r in bins)
    value_stride=max(sparse,math.ceil((count_width+12)/slot))
    previous=None
    for index,row in enumerate(bins):
        centre=x+slot*(index+.5); value=row.get('count')
        if value is not None:
            top=bottom-height*value/ceiling
            if value>0:
                p.d.rectangle((centre-(slot-gap)/2,top,centre+(slot-gap)/2,bottom-1),fill=BLUE)
            if index%value_stride==0:
                label=count_label(value,row.get('incomplete'))
                half=math.ceil(font(14).getlength(label)/2)
                label_x=max(x+half,min(x+width-half,centre))
                p.text((label_x,top-20),label,14,align='centre')
        else:
            # Every unavailable interval gets a marker, even when its numeric
            # and axis labels are omitted. A short dash also fits narrow bins.
            p.d.line((centre-3,bottom-8,centre+3,bottom-8),fill=BLACK,width=2)
        median=row.get('median') if baseline else None
        if median is not None:
            point=(centre,bottom-height*median/ceiling)
            if previous is not None: dash_line(p,previous,point)
            p.d.ellipse((point[0]-3,point[1]-3,point[0]+3,point[1]+3),fill=BLACK)
            previous=point
        else: previous=None
        if index%sparse==0:
            # Centre labels in a group of bins so long ranges stay in the plot.
            label=interval_labels[index]
            half=math.ceil(font(14).getlength(label)/2)
            label_x=max(x+half,min(x+width-half,centre))
            p.text((label_x,bottom+10),label,14,align='centre')
        if owl_row and row.get('owl_count'): diamond(p,centre,bottom+40)


def rhythm(p, snapshot, settings, zone, top):
    night=snapshot['night']
    owl_y=owl_panel_content(night,zone)[-1]
    compact=owl_y<520
    very_compact=owl_y<470
    p.text((24,top),'The night’s rhythm',18,'bold')
    p.text((24,top+(24 if very_compact else 28 if compact else 34)),bat_total(night),32)
    p.text((170 if very_compact else 24,top+(35 if very_compact else 59 if compact else 76)),'bat detections',14)
    if very_compact:
        bat_art(p,(352,top,104,44),settings.artwork_mode)
    else:
        bat_art(p,(244,top-8,212,75 if compact else 102),settings.artwork_mode)
    baseline=bool(night.get('baseline_nights'))
    bottom=owl_y-123
    chart_top=top+70 if very_compact else max(top+95,min(top+131,bottom-32))
    hourly_chart(p,night,(64,chart_top,392,bottom-chart_top),baseline=baseline,owl_row=True)
    if night.get('bins'):
        p.text((24,bottom+35),'Owl',14)
        p.text((260,bottom+58),'Hours after sunset',14,align='centre')
        p.d.rectangle((24,bottom+88,34,bottom+98),fill=BLUE)
        p.text((43,bottom+86),'Tonight',14)
    if baseline and any(r.get('median') is not None for r in night.get('bins',[])):
        dash_line(p,(134,bottom+94),(158,bottom+94))
        p.text((169,bottom+86),'Previous %d nights · median' % night['baseline_nights'],14)
    owl_panel(p,snapshot,settings,zone)


def history(p, snapshot, settings, zone, top):
    night=snapshot['night']
    owl_y=owl_panel_content(night,zone)[-1]
    compact=owl_y<510
    bat_art(p,(332,top-8,124,52 if compact else 65),settings.artwork_mode)
    p.text((24,top),'Seven nights',18,'bold')
    if not compact: p.text((24,top+30),'An evening in context',24)
    hours=night.get('comparison_hours',0)
    p.text((24,top+(29 if compact else 67)),'First %g hours after sunset' % hours if hours else 'Completed hours after sunset',14)
    rows=(night.get('history') or [])[-7:]
    start=top+(60 if owl_y<465 else 75 if compact else 113)
    row_step=max(18,min(27,(owl_y-48-start)//7))
    if not rows:
        p.text((24,start+60),'Night history unavailable',18)
    else:
        highest=max([r['total'] for r in rows if r.get('comparable') and r.get('total') is not None]+[1])
        # Dedicated count column avoids squeezing totals against a long bar.
        axis,span=109,228
        p.text((405,start-21),'Count',14,align='right')
        p.text((456,start-21),'Owl',14,align='right')
        for i,row in enumerate(rows):
            y=start+i*row_step; current=row['date']==night['evening_date']
            label=date.fromisoformat(row['date']).strftime('%-d %b')
            p.text((24,y+3),label,14,'bold' if current else 'sans')
            total=row.get('total') if row.get('comparable') else None
            if total is not None and total>0:
                length=span*total/highest
                p.d.rectangle((axis,y,axis+length,y+min(18,row_step-6)),fill=BLUE if current else WHITE,outline=BLACK)
            p.text((405,y+3),count_label(total,row.get('incomplete')),14,align='right')
            if row.get('owl_count') is None or not row.get('comparable'):
                p.text((443,y+3),'—',14,align='centre')
            elif row['owl_count']>0: diamond(p,443,y+9)
        p.text((24,owl_y-36),'Bat detections · ◆ owl heard · — unavailable',14)
    owl_panel(p,snapshot,settings,zone)


def journal(p, snapshot, settings, zone, top):
    night=snapshot['night']; owl=featured_owl(night)
    if not owl:
        p.text((24,top),'Night field journal',16,'bold')
        p.text((24,top+30),'Bats after sunset',24)
        bat_art(p,(24,top+70,432,175),settings.artwork_mode)
        p.text((24,top+253),bat_total(night),32)
        p.text((205,top+265),'bat detections',18)
        if night.get('first_bat') and not night.get('incomplete'):
            readable(p,(24,top+302),'First recorded at '+bird_time(night['first_bat'],night['as_of'],zone))
        owl_panel(p,snapshot,settings,zone)
        return
    p.text((24,top),'Heard tonight',16,'bold')
    name_lines=text_lines(short_name(owl),432,24)
    end=write_lines(p,(24,top+28),name_lines,24)
    end=readable(p,(24,end+6),owl['scientific_name'])
    image_y=end+10
    total=count_label(owl['count'],night.get('incomplete'))
    text_y=image_y+12
    right=[('Last heard at',14),(bird_time(owl['last'],night['as_of'],zone),18),
           (total+' '+('detection' if total=='1' else 'detections'),18),('in this report',14)]
    if image_y>373:
        # Exceptionally long labels use a full-width observation block.
        text_y=readable(p,(24,image_y),'Last heard at '+bird_time(owl['last'],night['as_of'],zone))
        text_y=readable(p,(24,text_y+6),total+' detections in this report')
    else:
        if artwork_path(owl): art(p,owl,(24,image_y,250,max(30,505-image_y)),settings.artwork_mode)
        else: readable(p,(24,image_y+40),'Illustration not yet available',240)
        for value,size in right:
            text_y=readable(p,(300,text_y),value,156,size)+9
    section_y=max(520,text_y+10)
    p.rule(section_y)
    p.text((24,section_y+15),'Bats this evening',16,'bold')
    bat_art(p,(24,section_y+45,148,651-(section_y+45)),settings.artwork_mode)
    p.text((24,660),bat_total(night),28)
    p.text((24,699),'bat detections',14)
    chart_top=max(582,section_y+62)
    hourly_chart(p,night,(208,chart_top,248,670-chart_top),compact=True)
    p.text((456,705),'Hours after sunset',14,align='right')


def render_night(snapshot, settings, layout):
    if layout not in LAYOUTS: raise ValueError('Unknown night layout: '+str(layout))
    _load_art.cache_clear(); manifest.cache_clear()
    p=Page(); zone=ZoneInfo(settings.timezone)
    top=masthead(p,snapshot,settings,snapshot['night'],zone,layout)
    {'night-rhythm':rhythm,'night-history':history,'night-journal':journal}[layout](p,snapshot,settings,zone,top)
    edition_footer(p,snapshot,layout)
    return quantise(p.im,dither=False).convert('RGB')
