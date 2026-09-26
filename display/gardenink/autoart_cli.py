"""Operator controls. Paid work is performed only by the explicitly enabled worker."""
from __future__ import annotations
import argparse
import getpass
import html
import json
import logging
import os
from pathlib import Path
import sys
import time
from .config import ROOT,load
from . import autoart as a
from .artfiles import identity


def confirm(word,message):
    if input(message+' Type '+word+': ').strip()!=word:
        raise ValueError('Cancelled; no changes made')


def review(store):
    cards=[]
    for job in store.rows():
        path=store.prepared(job)
        image=('<img src="%s" alt="%s">'%(html.escape(path.relative_to(store.root).as_posix(),quote=True),html.escape(job['scientific'],quote=True))) if path.is_file() else '<p>No prepared image.</p>'
        cards.append('<article><h2>%s</h2><p><i>%s</i> · %s</p>%s<p>%s</p></article>'%(
            html.escape(job['label']),html.escape(job['scientific']),html.escape(job['status']),image,html.escape(job['message'])))
    text='''<!doctype html><html><meta charset="utf-8"><title>Garden Ink — automatic artwork review</title>
<style>body{font-family:system-ui;max-width:1200px;margin:2em auto;padding:1em}section{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:1em}article{border:1px solid #aaa;padding:1em}img{width:100%;height:230px;object-fit:contain}h2{font-size:1.1em}</style>
<h1>Generated illustrations</h1><p>AI-generated decoration, not camera evidence. Inspect anatomy and species identity. Automatic publication is not human approval.</p><section>'''+''.join(cards)+'</section></html>'
    a.atomic(store.root/'review.html',text.encode())
    print('Local review:',store.root/'review.html')


def main(argv=None):
    p=argparse.ArgumentParser(description='Garden Ink optional on-device missing-art generation')
    sub=p.add_subparsers(dest='cmd',required=True)
    en=sub.add_parser('enable',help='Opt into paid generation and save a key with hidden input')
    en.add_argument('--daily-limit',type=int,default=None)
    en.add_argument('--total-limit',type=int,default=None)
    en.add_argument('--review-required',action='store_true')
    en.add_argument('--replace-key',action='store_true')
    for name in ('disable','status','review','scan','resume'):sub.add_parser(name)
    worker=sub.add_parser('worker');worker.add_argument('--once',action='store_true')
    for name in ('approve','reject','recover','retry'):
        q=sub.add_parser(name);q.add_argument('species')
        if name=='retry':q.add_argument('--note',default='')
    args=p.parse_args(argv)
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    if args.cmd=='worker':a.run_worker(args.once);return 0
    cfg=a.settings()
    if args.cmd=='enable':
        if args.daily_limit is not None:cfg['max_requests_per_24h']=args.daily_limit
        if args.total_limit is not None:cfg['max_requests_total']=args.total_limit
        cfg['auto_publish']=not args.review_required
        # Validate proposed values without overwriting a valid configuration first.
        if type(cfg['max_requests_per_24h']) is not int or not 1<=cfg['max_requests_per_24h']<=20:
            raise ValueError('daily-limit must be 1..20')
        if type(cfg['max_requests_total']) is not int or not 1<=cfg['max_requests_total']<=1000:
            raise ValueError('total-limit must be 1..1000')
        print('Enable PAID OpenAI image edits for missing, qualifying species only.')
        print('Sends scientific species identity, fixed style brief and original robin PNG.')
        print('Does NOT send recordings, coordinates, station URL, counts or detection times.')
        print('Model:',cfg['model'],'| high quality | 1536x1024 | timeout:',cfg['timeout_seconds'])
        print('Request caps:',cfg['max_requests_per_24h'],'per rolling 24h;',cfg['max_requests_total'],'total, including previous attempts.')
        print('These are request caps, NOT hard currency caps. API billing is separate.')
        print('Automatic publication:',cfg['auto_publish'],'(image anatomy is NOT automatically verified).')
        confirm('ENABLE','Accept these settings and paid requests?')
        if not a.secret_path().exists() or args.replace_key:
            key=getpass.getpass('OpenAI API key (hidden; saved only on this Pi): ').strip()
            if not key or len(key)>8192 or not key.isascii() or any(c.isspace() for c in key):
                raise ValueError('Invalid key format; no key saved')
            parent=a.secret_path().parent
            parent.mkdir(mode=0o700,parents=True,exist_ok=True);parent.chmod(0o700)
            a.atomic(a.secret_path(),key.encode())
        a.read_key()
        cfg['enabled']=True;a.save_settings(cfg)
        a.Store().pause('')
        print('Enabled. Install worker: ./autoart-service.sh install')
        print('Queue current missing birds without a screen refresh: ./autoart.sh scan')
        return 0
    if args.cmd=='disable':
        cfg['enabled']=False;a.save_settings(cfg)
        print('Disabled. No new jobs will be submitted. Already in-flight requests may finish.')
        return 0
    store=a.Store()
    if args.cmd=='status':
        print(json.dumps({'settings':cfg,'budget':store.budget(),'jobs':store.rows()},indent=2));return 0
    if args.cmd=='review':review(store);return 0
    if args.cmd=='scan':
        if not cfg['enabled']:raise ValueError('Automatic artwork is disabled; use enable first')
        from .client import Client
        display=load(ROOT/'config.json').validate()
        snapshot=Client(display,display.token(ROOT/'config.json')).fetch()
        print('New jobs queued:',a.enqueue_snapshot(snapshot,display),'; no physical refresh performed.')
        return 0
    if args.cmd=='resume':
        confirm('RESUME','Resume the queue after resolving provider access/quota/rate issues?')
        store.pause('')
        print('Queue resumed. Failed/uncertain species still require an explicit retry.')
        return 0
    # Local operator edits require the worker stopped; never race publication/retry.
    try:
        with a.worker_lock(store):
            slug,_=identity(args.species)
            job=store.job(slug)
            if job['status']=='requesting':
                # A stopped worker may have been killed during an HTTP request.
                store.finish(job,'uncertain','Interrupted request; retry may charge again')
                job=store.job(slug)
            if args.cmd=='approve':
                data=store.prepared(job).read_bytes()
                a.normalise(data)  # validation only, preserve original candidate bytes
                confirm('APPROVE','Visually checked this species and its anatomy?')
                a.atomic(store.root/'images'/(slug+'.png'),data)
                store.finish(job,'ready','Human approved locally')
                print('Approved; available to next scheduled display edition.')
            elif args.cmd=='reject':
                confirm('REJECT','Remove this auto-generated illustration from future editions?')
                store.finish(job,'rejected','Rejected by operator; no automatic regeneration')
                (store.root/'images'/(slug+'.png')).unlink(missing_ok=True)
                print('Rejected. Custom/bundled art is untouched. Existing panel image waits for next hourly update.')
            elif args.cmd=='recover':
                if not store.raw(job).is_file():raise ValueError('No local raw response to recover; cannot retrieve a lost server result')
                print('Recovered:',a.publish(store,job,cfg),'; no API request made.')
            elif args.cmd=='retry':
                if not cfg['enabled']:raise ValueError('Automatic artwork is disabled')
                if len(args.note)>1500:raise ValueError('Keep correction note below 1500 characters')
                confirm('RETRY','One NEW paid request when budget permits; an uncertain previous request may already have been charged. Proceed?')
                source=load(ROOT/'config.json').validate().identity()
                with store.db() as db:
                    db.execute("UPDATE jobs SET status='queued',note=?,message='',last_seen=?,source_identity=? WHERE slug=?",
                               (args.note or job['note'],time.time(),source,slug))
                (store.root/'images'/(slug+'.png')).unlink(missing_ok=True)
                print('Queued for a new attempt; raw history and request counters retained. Start the worker again.')
        return 0
    except RuntimeError as exc:
        if 'worker' in str(exc):raise RuntimeError('Stop ./autoart-service.sh before approval/rejection/recovery/retry') from None
        raise


def entry():
    try:return main()
    except (OSError,ValueError,RuntimeError) as exc:
        print('ERROR:',exc,file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(entry())
