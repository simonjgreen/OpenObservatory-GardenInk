#!/usr/bin/env python3
"""Render every page and representative states, offline, at native resolution."""
from copy import deepcopy
from pathlib import Path
import argparse
import json
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'display'))
from PIL import Image, ImageDraw
from gardenink.config import Settings
from gardenink.demo import demo_snapshot
from gardenink.night_demo import demo_night_snapshot
from gardenink.model import timestamp
from gardenink.render import Page, render, font


def cases():
    cfg=Settings()
    day=demo_snapshot(cfg,timestamp('2026-09-27T11:01:00Z'))
    night=demo_night_snapshot(cfg)
    out=[]
    def add(key,label,layout,snap):
        snap=deepcopy(snap);snap['fixture']=True
        out.append((key,label,layout,snap))
    add('01-journal','Hourly journal · agreed reference','journal',day)
    add('02-gallery','Today gallery','gallery',day)
    for i,page in enumerate(('rhythm','history','journal'),3):
        add('%02d-night-%s'%(i,page),'After dark · '+page,'night-'+page,night)
    no_owl=deepcopy(night);no_owl['night']['owls']=[]
    for row in no_owl['night']['bins']: row['owl_count']=0
    no_owl['night']['history'][-1]['owl_count']=0
    for i,page in enumerate(('rhythm','history','journal'),6):
        add('%02d-no-owl-%s'%(i,page),'No owl heard · '+page,'night-'+page,no_owl)
    quiet=deepcopy(day)
    quiet['last_hour'].update(species=[],record_count=0,species_count=0)
    add('09-quiet-hour','Quiet hour · earlier records retained','journal',quiet)
    empty=deepcopy(quiet);empty['today'].update(species=[],record_count=0,species_count=0)
    add('10-empty-journal','No bird records today · journal','journal',empty)
    add('11-empty-gallery','No bird records today · gallery','gallery',empty)
    missing=deepcopy(day)
    missing['last_hour']['species'][0].update(scientific_name='Unknownus example',name='Unillustrated bird')
    add('12-missing-art','Illustration unavailable','journal',missing)
    offline=deepcopy(empty);offline.update(offline=True,cached=False,demo=False)
    add('13-offline-journal','Station unavailable · journal','journal',offline)
    add('14-offline-gallery','Station unavailable · gallery','gallery',offline)
    cached=deepcopy(day);cached.update(offline=True,cached=True,demo=False)
    cached['health']['pause']['active']=True
    cached['today']['incomplete']=True
    add('15-cached-journal','Cached + paused + incomplete · journal','journal',cached)
    add('16-cached-gallery','Cached + paused + incomplete · gallery','gallery',cached)
    unavailable=deepcopy(night)
    unavailable['night'].update(available=False,owls=[],bins=[],history=[],record_count=0,baseline_nights=0,first_bat=None)
    for i,page in enumerate(('rhythm','history','journal'),17):
        add('%02d-night-unavailable-%s'%(i,page),'Night data unavailable · '+page,'night-'+page,unavailable)
    nc=deepcopy(night);nc.update(demo=False,offline=True,cached=True)
    nc['health']['pause']['active']=True
    nc['night'].update(cached=True,available=False,incomplete=True)
    nc['night']['bins'][1]['incomplete']=True
    add('20-night-cached','Cached + paused + incomplete night','night-rhythm',nc)
    midnight=demo_snapshot(cfg,timestamp('2026-09-26T23:05:00Z'))
    add('21-midnight','Report crossing midnight','gallery',midnight)
    dst=deepcopy(night);dst['night'].update(since='2026-10-24T17:45:00Z',as_of='2026-10-25T09:45:00Z',evening_date='2026-10-24',record_count=280,baseline_nights=0)
    dst['night']['owls'][0]['last']='2026-10-25T00:42:00Z'
    dst['night']['bins']=[dict(start_hour=i,end_hour=i+1,count=10+i,median=None,owl_count=0) for i in range(16)]
    add('22-dst','Stress test · DST + 16 hourly bins','night-rhythm',dst)
    long=deepcopy(day)
    long['today']['species'][0].update(name='A very long local name for a bird identified in this garden awaiting review by the local station operator before the identification can be confirmed',scientific_name='Unknownus longname')
    add('23-long-gallery','Long accepted label · taller cards','gallery',long)
    ln=deepcopy(night)
    ln['night']['owls'][0].update(name='A very long local name for this owl in the garden',scientific_name='Unknownus verylongspeciesname')
    add('24-long-owl','Long owl name · missing illustration','night-journal',ln)
    return out


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('local/previews/readability-all-pages'))
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    cfg=Settings();manifest=[];failures=[]
    for key,label,layout,snap in cases():
        runs=[];original=Page.text
        def record(page,xy,value,size=16,style='sans',colour=(0,0,0),**kw):
            w,h=original(page,xy,value,size,style,colour,**kw)
            x,y=xy
            if kw.get('align')=='centre': x-=w//2
            if kw.get('align')=='right': x-=w
            runs.append(((x,y,x+w,y+h),str(value),size,style,kw.get('width')))
            return w,h
        with patch.object(Page,'text',record): image=render(snap,cfg,layout)
        image.save(args.output/(key+'.png'))
        for box,value,size,style,width in runs:
            if size<14 or style=='italic' or box[0]<23 or box[2]>457 or box[3]>793:
                failures.append((key,'text bounds/style',value,box,size))
            if width is not None and font(size,style).getlength(value)>width:
                failures.append((key,'silent fitting',value))
        for i,(a,av,*_) in enumerate(runs):
            for b,bv,*_ in runs[i+1:]:
                if a[0]<b[2] and a[2]>b[0] and a[1]<b[3] and a[3]>b[1]:
                    failures.append((key,'text overlap',av,bv))
        manifest.append(dict(file=key+'.png',label=label,layout=layout))
    # Pair native-sized frames; do not resample panel output.
    for i in range(0,len(manifest),2):
        sheet=Image.new('RGB',(992,848),'#e6e4df');d=ImageDraw.Draw(sheet)
        for j,row in enumerate(manifest[i:i+2]):
            x=8+j*488
            d.text((x,8),row['label'],font=font(14),fill='black')
            with Image.open(args.output/row['file']) as frame: sheet.paste(frame,(x,32))
        sheet.save(args.output/('sheet-%02d.png'%(i//2+1)))
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (args.output/'checks.json').write_text(json.dumps({'pages':len(manifest),'failures':failures},indent=2)+'\n')
    print(json.dumps({'pages':len(manifest),'failures':failures},indent=2))
    if failures: raise SystemExit(1)


if __name__=='__main__': main()
