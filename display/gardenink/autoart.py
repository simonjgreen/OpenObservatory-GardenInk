"""Durable, opt-in missing-art queue. Does not import or drive display hardware."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import fcntl
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import signal
import sqlite3
import stat
import tempfile
import threading
import time
from .config import ROOT
from .artfiles import art_state, identity, find_art
from .model import timestamp, status_for
from .image_request import api_edit, normalise, ApiFailure, request_fingerprint

LOG=logging.getLogger('gardenink.autoart')
DEFAULTS={'enabled':False, 'model':'gpt-image-2-2026-04-21',
          'max_requests_per_24h':2, 'max_requests_total':20, 'workers':2,
          'min_detections':3, 'timeout_seconds':1200, 'auto_publish':True}


def settings_path(): return ROOT/'autoart.json'
def secret_path(): return ROOT/'.secrets'/'openai-api-key'


def settings():
    path=settings_path()
    supplied=json.loads(path.read_text()) if path.exists() else {}
    if not isinstance(supplied,dict): raise ValueError('autoart.json must be an object')
    if set(supplied)-set(DEFAULTS): raise ValueError('Unknown autoart setting')
    cfg={**DEFAULTS,**supplied}
    for k in ('enabled','auto_publish'):
        if not isinstance(cfg[k],bool): raise ValueError(k+' must be boolean')
    for k,lo,hi in [('max_requests_per_24h',1,20),('max_requests_total',1,1000),
                    ('workers',1,2),('min_detections',1,100),('timeout_seconds',60,1200)]:
        if type(cfg[k]) is not int or not lo<=cfg[k]<=hi: raise ValueError('Invalid '+k)
    if cfg['model'] not in ('gpt-image-2-2026-04-21','gpt-image-2'):
        raise ValueError('Keep the established GPT Image 2 model for collection consistency')
    return cfg


def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd,name=tempfile.mkstemp(prefix='.'+path.name,dir=str(path.parent))
    try:
        with os.fdopen(fd,'wb') as f:
            os.fchmod(f.fileno(),0o600);f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)


def save_settings(cfg):
    atomic(settings_path(),(json.dumps(cfg,indent=2)+'\n').encode())


def read_key():
    path=secret_path()
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)&0o077:
        raise ValueError('OpenAI key file must be owned by this user with mode 600')
    key=path.read_text().strip()
    if not key or len(key)>8192 or not key.isascii() or any(c.isspace() for c in key):
        raise ValueError('Invalid OpenAI key file; rerun ./autoart.sh enable')
    return key


class Store:
    def __init__(self,path=None):
        self.root=path or art_state()
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.path=self.root/'jobs.sqlite3'
        with self.db() as db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS jobs (
                slug TEXT PRIMARY KEY, scientific TEXT NOT NULL, label TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued', priority INTEGER NOT NULL,
                last_seen REAL NOT NULL, source_identity TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '', active_attempt INTEGER,
                message TEXT NOT NULL DEFAULT '', fingerprint TEXT);
              CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT NOT NULL,
                started REAL NOT NULL, status TEXT NOT NULL, request_id TEXT NOT NULL DEFAULT '',
                fingerprint TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            ''')
        self.path.chmod(0o600)

    @contextmanager
    def db(self):
        db=sqlite3.connect(str(self.path),timeout=3)
        db.row_factory=sqlite3.Row
        try:
            with db: yield db
        except sqlite3.Error as exc:
            raise RuntimeError('Artwork database unavailable (%s)'%type(exc).__name__) from None
        finally: db.close()

    def queue(self,scientific,label,priority,seen,source_identity):
        slug,canonical=identity(scientific)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            existing=db.execute('SELECT status FROM jobs WHERE slug=?',(slug,)).fetchone()
            if existing:
                # Refresh eligibility, but NEVER change a terminal/requesting status.
                db.execute('UPDATE jobs SET last_seen=?,source_identity=?,priority=? WHERE slug=?',
                           (seen,source_identity,priority,slug))
                return False
            if db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]>=128: return False
            db.execute('INSERT INTO jobs(slug,scientific,label,priority,last_seen,source_identity) VALUES(?,?,?,?,?,?)',
                       (slug,canonical,label[:100],priority,seen,source_identity))
            return True

    def rows(self):
        with self.db() as db: return [dict(r) for r in db.execute('SELECT * FROM jobs ORDER BY priority,last_seen DESC')]

    def job(self,slug):
        with self.db() as db:
            row=db.execute('SELECT * FROM jobs WHERE slug=?',(slug,)).fetchone()
            if row is None: raise ValueError('No queued/generated record for that species')
            return dict(row)

    def budget(self,now=None):
        now=time.time() if now is None else now
        with self.db() as db:
            total=db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]
            recent=db.execute('SELECT COUNT(*) FROM attempts WHERE started>?',(now-86400,)).fetchone()[0]
            pause=db.execute("SELECT value FROM meta WHERE key='paused'").fetchone()
            return {'attempts_total':total,'attempts_last_24h':recent,'paused':pause[0] if pause else ''}

    def pause(self,reason):
        with self.db() as db: db.execute("INSERT OR REPLACE INTO meta VALUES('paused',?)",(reason,))

    def claim(self,cfg,source_identity,now=None):
        if not cfg['enabled']: return None
        now=time.time() if now is None else now
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            pause=db.execute("SELECT value FROM meta WHERE key='paused'").fetchone()
            if pause and pause[0]: return None
            total=db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]
            recent=db.execute('SELECT COUNT(*) FROM attempts WHERE started>?',(now-86400,)).fetchone()[0]
            if total>=cfg['max_requests_total'] or recent>=cfg['max_requests_per_24h']: return None
            last=db.execute('SELECT MAX(started) FROM attempts').fetchone()[0]
            # Also spaces starts across workers/restarts; not just concurrent count.
            if last is not None and now-last<15: return None
            rows=db.execute("SELECT * FROM jobs WHERE status='queued' AND source_identity=? AND last_seen>=? AND last_seen<=? ORDER BY priority,last_seen DESC",(source_identity,now-86400,now+300)).fetchall()
            for row in rows:
                item=dict(row)
                if find_art({'scientific_name':item['scientific']}):
                    db.execute("UPDATE jobs SET status='skipped',message='Artwork now exists locally' WHERE slug=?",(item['slug'],))
                    continue
                fp=request_fingerprint(item['scientific'],item['note'],cfg)
                attempt=db.execute("INSERT INTO attempts(slug,started,status,fingerprint) VALUES(?,?,'requesting',?)",(item['slug'],now,fp)).lastrowid
                db.execute("UPDATE jobs SET status='requesting',active_attempt=?,fingerprint=?,message='' WHERE slug=?",(attempt,fp,item['slug']))
                return {**item,'status':'requesting','active_attempt':attempt,'fingerprint':fp}
        return None

    def finish(self,job,status,message='',request_id=''):
        with self.db() as db:
            db.execute('UPDATE jobs SET status=?,message=? WHERE slug=? AND active_attempt=?',
                       (status,message[:500],job['slug'],job['active_attempt']))
            db.execute("UPDATE attempts SET status=?,request_id=CASE WHEN ?='' THEN request_id ELSE ? END WHERE id=?",
                       (status,request_id[:160],request_id[:160],job['active_attempt']))

    def interrupted(self):
        with self.db() as db:
            db.execute("UPDATE jobs SET status='uncertain',message='Worker interrupted; no automatic POST retry' WHERE status='requesting'")
            db.execute("UPDATE attempts SET status='uncertain' WHERE status='requesting'")

    def raw(self,job):
        return self.root/'raw'/('%s.%s.png'%(job['slug'],job['active_attempt']))

    def prepared(self,job):
        return self.root/'candidates'/('%s.%s.png'%(job['slug'],job['active_attempt']))


def enqueue_snapshot(snap,display_cfg):
    cfg=settings()
    if not cfg['enabled'] or snap.get('demo') or snap.get('fixture') or snap.get('offline') or snap.get('cached'):
        return 0
    if status_for(snap)[0] not in ('ok','degraded'): return 0
    captured=(snap.get('health') or {}).get('capture') or {}
    if captured.get('is_live_hardware') is not True: return 0
    age=time.time()-timestamp(snap['as_of']).timestamp()
    if not -300<=age<=3600: return 0
    from .render import selections
    feature,daily=selections(snap)
    visible=[b for b in [feature]+daily if b]
    ranked=visible+snap['last_hour']['species']+snap['today']['species']
    store=Store();added=0;seen=set()
    source=display_cfg.identity()
    for index,bird in enumerate(ranked):
        try: slug,scientific=identity(bird['scientific_name'])
        except (KeyError,ValueError): continue
        if slug in seen: continue
        seen.add(slug)
        # The queue only sees already filtered, real-microphone identifications.
        # A second modest repetition gate limits one-off false-positive spending.
        count=max([int(b.get('count',0)) for w in ('today','last_hour') for b in snap[w]['species']
                   if b['scientific_name'].casefold()==bird['scientific_name'].casefold()] or [0])
        if count<cfg['min_detections'] and not bird.get('reviewed'): continue
        if find_art(bird) is not None: continue
        when=timestamp(bird['last']).timestamp()
        if not math.isfinite(when): continue
        added+=int(store.queue(bird['scientific_name'],bird.get('name',scientific),index,when,source))
    return added


def publish(store,job,cfg,raw=None):
    raw=store.raw(job).read_bytes() if raw is None else raw
    prepared,warning=normalise(raw)
    atomic(store.prepared(job),prepared)
    # Suspect boundaries go to review even in automatic mode, without a new call.
    ready=cfg['auto_publish'] and not warning
    if ready:
        atomic(store.root/'images'/(job['slug']+'.png'),prepared)
    store.finish(job,'ready' if ready else 'review',warning)
    return 'ready' if ready else 'review'


def process(store,job,cfg,key,request=api_edit):
    LOG.info('Generating missing illustration: %s (attempt %s)',job['scientific'],job['active_attempt'])
    try:
        raw,metadata=request(job['scientific'],job['note'],cfg,key)
        atomic(store.raw(job),raw)
        atomic(store.root/'raw'/('%s.%s.json'%(job['slug'],job['active_attempt'])),json.dumps({
            **metadata,'model':cfg['model'],'fingerprint':job['fingerprint'],
            'scientific_name':job['scientific'],'auto_generated':True,
            'human_reviewed':False},ensure_ascii=False).encode())
        state=publish(store,job,cfg,raw)
        # Preserve provider request ID after local publication updates the row.
        store.finish(job,state,store.job(job['slug'])['message'],metadata.get('request_id',''))
        LOG.info('Illustration %s: %s; display will use its next scheduled edition',job['scientific'],state)
    except ApiFailure as exc:
        store.finish(job,'uncertain' if exc.uncertain else 'failed',str(exc),exc.request_id)
        if exc.status in (400,401,403,404,429):
            store.pause('Provider HTTP %s; resolve access/quota/rate issue, then explicitly resume'%exc.status)
        LOG.warning('%s: %s',job['scientific'],exc)
    except Exception as exc:
        # Successful raw bytes, if saved, can be prepared again without paying.
        state='needs_preparation' if store.raw(job).exists() else 'uncertain'
        store.finish(job,state,'Local processing interrupted (%s); no automatic new request'%type(exc).__name__)
        LOG.warning('%s: %s (%s)',job['scientific'],state,type(exc).__name__)


@contextmanager
def worker_lock(store):
    with (store.root/'worker.lock').open('a') as f:
        try: fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise RuntimeError('Another artwork worker is running') from None
        yield


def run_worker(once=False):
    from .config import load
    stop=threading.Event()
    def stopping(*args):
        LOG.info('Stopping new artwork requests; allowing in-flight requests to finish')
        stop.set()
    signal.signal(signal.SIGTERM,stopping);signal.signal(signal.SIGINT,stopping)
    store=Store()
    with worker_lock(store):
        store.interrupted()
        # A worker crash after response receipt can be recovered locally, not re-billed.
        for item in store.rows():
            if item['status'] in ('uncertain','needs_preparation') and store.raw(item).is_file():
                try: publish(store,item,settings())
                except (OSError,ValueError): LOG.warning('Saved raw image needs manual recovery: %s',item['scientific'])
        with ThreadPoolExecutor(max_workers=2,thread_name_prefix='bird-art') as pool:
            pending=set()
            while not stop.is_set():
                for future in list(pending):
                    if future.done(): future.result();pending.remove(future)
                try:
                    cfg=settings()
                    if cfg['enabled'] and len(pending)<cfg['workers']:
                        key=read_key()  # never reserve a paid slot without a configured key
                        source=load(ROOT/'config.json').validate().identity()
                        job=store.claim(cfg,source)
                        if job:
                            pending.add(pool.submit(process,store,job,cfg,key))
                            if once: break
                except (OSError,ValueError,RuntimeError) as exc:
                    LOG.warning('Artwork worker idle: %s',str(exc))
                if once: break
                stop.wait(15)
            # Executor waits; shutdown does not cancel a possibly billed HTTP request.
            for future in pending: future.result()
