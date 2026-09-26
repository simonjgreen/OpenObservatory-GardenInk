#!/usr/bin/env python3
"""Reproduce the packaged example images with the actual runtime renderer."""
import copy
from datetime import datetime,timedelta,timezone
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from gardenink.config import Settings
from gardenink.demo import demo_snapshot,fixture_records
from gardenink.model import build_snapshot,iso
from gardenink.render import render


def main():
    cfg=Settings();now=datetime(2026,9,25,15,0,tzinfo=timezone.utc)
    snap=demo_snapshot(cfg,now)
    out=ROOT/'previews';out.mkdir(exist_ok=True)
    render(snap,cfg).save(out/'hourly.png')
    render(snap,cfg,'gallery').save(out/'today_gallery.png')
    # A second example uses the previously missing three birds, not fictional
    # local detections silently passed off as a live API result.
    rows=fixture_records(now)
    proto=dict(rows[0])
    for i,(sci,name,minute) in enumerate((('Corvus frugilegus','Rook',2),
               ('Corvus monedula','Eurasian Jackdaw',4),('Aegithalos caudatus','Long-tailed Tit',7))):
        for j in range(9+i):
            rows.append({**proto,'id':'atlas-%d-%d'%(i,j),'event_start_utc':iso(now-timedelta(minutes=minute+j)),
                         'scientific_name':sci,'effective_scientific_name':sci,
                         'common_name':name,'effective_common_name':name})
    rook=build_snapshot(rows,now,cfg);rook.update(demo=True,health=snap['health'])
    render(rook,cfg).save(out/'rook_edition.png')
    quiet=build_snapshot([r for r in rows if r['event_start_utc'] < iso(now-timedelta(hours=1))],now,cfg)
    quiet.update(demo=True,health=snap['health'])
    render(quiet,cfg).save(out/'quiet_hour.png')
    offline=copy.deepcopy(snap);offline.update(demo=False,fixture=True,offline=True,cached=True)
    render(offline,cfg).save(out/'offline.png')
    partial=copy.deepcopy(snap);partial.update(demo=False,fixture=True)
    partial['today']['incomplete']=True
    render(partial,cfg).save(out/'partial_day_complete_hour.png')
    empty=build_snapshot([],now,cfg);empty.update(demo=True,health=snap['health'])
    render(empty,cfg).save(out/'empty_day.png')
    from PIL import Image,ImageDraw,ImageFont
    names=['hourly','rook_edition','quiet_hour','offline','partial_day_complete_hour','empty_day']
    contact=Image.new('RGB',(3*320,2*560),'white');draw=ImageDraw.Draw(contact)
    f=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',12)
    for i,name in enumerate(names):
        im=Image.open(out/(name+'.png')).resize((300,500))
        x=(i%3)*320;y=(i//3)*560
        contact.paste(im,(x+10,y+25))
        draw.text((x+10,y+534),name.replace('_',' '),font=f,fill='black')
    contact.save(out/'states_contact.png')
    print('Rendered',len(names)+1,'edition previews and the state contact sheet.')

if __name__=='__main__':main()
