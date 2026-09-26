import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from gardenink.config import Settings,normalise_url
from gardenink.model import normalise_record, summarise, timestamp,iso,status_for,utcnow
from gardenink.client import Client,APIError
from gardenink.demo import fixture_records,demo_snapshot
from gardenink.palette import pack,quantise,COLOURS,CODES
from gardenink.render import render,artwork_path
from gardenink.storage import atomic_json,cached_or_empty
from gardenink.hardware import EPD,INIT_SEQUENCE,DisplayError
from PIL import Image

NOW=datetime(2026,9,25,12,0,tzinfo=timezone.utc)

class ModelTests(unittest.TestCase):
    def setUp(self):
        self.row=fixture_records(NOW)[0]
        self.start=NOW-timedelta(hours=6)
    def norm(self,row=None):return normalise_record(row or self.row,self.start,NOW,.75)
    def test_actual_contract_shape(self):self.assertEqual(self.norm()[0]['scientific_name'],'Erithacus rubecula')
    def test_uncalibrated_score_threshold(self):
        self.row['score']=.74999;self.assertEqual(self.norm()[1],'below_threshold')
    def test_exact_threshold(self):self.row['score']=.75;self.assertIsNotNone(self.norm()[0])
    def test_all_non_microphone_kinds_rejected(self):
        for kind in ('synthetic','replay',None,'usb','file'):
            r={**self.row,'source_kind':kind};self.assertEqual(self.norm(r)[1],'not_microphone')
    def test_live_flag_fail_closed(self):
        for flag in (False,None,'true',1):
            r={**self.row,'is_live_source':flag};self.assertIsNone(self.norm(r)[0])
    def test_rejected_hidden(self):self.row['review']={'status':'rejected'};self.assertEqual(self.norm()[1],'rejected')
    def test_withdrawn_hidden(self):self.row['withdrawn']=True;self.assertEqual(self.norm()[1],'withdrawn')
    def test_flags_withdrawn_hidden(self):self.row['flags']={'withdrawn':True};self.assertEqual(self.norm()[1],'withdrawn')
    def test_confirmed_low_score_kept(self):
        self.row.update({'score':.1,'review':{'status':'confirmed'}});self.assertTrue(self.norm()[0]['reviewed'])
    def test_corrected_uses_effective_name_and_art(self):
        self.row.update({'score':.1,'review':{'status':'corrected'},
                         'effective_common_name':'Blue Tit','effective_scientific_name':'Cyanistes caeruleus'})
        rec=self.norm()[0]
        self.assertEqual(rec['name'],'Blue Tit')
        self.assertEqual(artwork_path(rec).name,'cyanistes_caeruleus.png')
    def test_missing_correction_does_not_show_original(self):
        self.row.update({'review':{'status':'corrected'},'effective_common_name':None,'effective_scientific_name':None})
        self.assertIsNone(self.norm()[0])
    def test_held_not_a_confirmation(self):
        self.row.update({'score':.1,'review':{'status':'held'}});self.assertIsNone(self.norm()[0])
    def test_bat_not_bird(self):self.row['taxonomic_group']='bat';self.assertIsNone(self.norm()[0])
    def test_genus_not_a_species(self):self.row['rank']='genus';self.assertIsNone(self.norm()[0])
    def test_future_timestamp_excluded(self):
        self.row['event_start_utc']=iso(NOW+timedelta(seconds=1));self.assertIsNone(self.norm()[0])
    def test_old_timestamp_excluded(self):
        self.row['event_start_utc']=iso(self.start-timedelta(seconds=1));self.assertIsNone(self.norm()[0])
    def test_naive_timestamp_rejected(self):self.assertRaises(ValueError,timestamp,'2026-09-25T12:00:00')
    def test_offset_normalised_to_utc(self):
        self.assertEqual(timestamp('2026-09-25T13:00:00+01:00'),NOW)
    def test_bad_scores(self):
        for value in (None,'0.9',True,float('nan'),float('inf'),2,-1):
            self.row['score']=value;self.assertIsNone(self.norm()[0])
    def test_distinct_and_deduplicated(self):
        rows=fixture_records(NOW)
        snap=summarise(rows+rows,self.start,NOW,.75)
        self.assertEqual(snap['species_count'],9)
        self.assertEqual(snap['record_count'],103)
        self.assertEqual(sum(snap['bins']),103)
        self.assertEqual(snap['species'][0]['scientific_name'],'Turdus merula')
    def test_partial_counts_kept_partial(self):
        snap=summarise([self.row],self.start,NOW,.75,True,'page budget')
        self.assertTrue(snap['incomplete'])
        self.assertEqual(snap['record_count'],1)

class HealthAndStorageTests(unittest.TestCase):
    def setUp(self):
        self.cfg=Settings(base_url='http://station:8080')
        self.snap=demo_snapshot(self.cfg,utcnow());self.snap['demo']=False
        self.snap['cache_identity']=self.cfg.identity()
    def test_capture_ok_is_snapshot_not_live_promise(self):self.assertEqual(status_for(self.snap)[0],'ok')
    def test_pause_overrides_healthy(self):self.snap['health']['pause']['active']=True;self.assertEqual(status_for(self.snap)[0],'paused')
    def test_synthetic_health_never_ok(self):self.snap['health']['capture']['is_live_hardware']=False;self.assertEqual(status_for(self.snap)[0],'not_live')
    def test_capture_stopped_never_ok(self):self.snap['health']['capture']['state']='error';self.assertEqual(status_for(self.snap)[0],'capture_error')
    def test_missing_health_unknown(self):self.snap['health']={};self.assertEqual(status_for(self.snap)[0],'unknown')
    def test_clock_disagreement(self):self.snap['clock_skew']=True;self.assertEqual(status_for(self.snap)[0],'clock')
    def test_offline_cache_is_labelled_and_timestamp_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'cache.json';atomic_json(p,self.snap)
            saved=cached_or_empty(p,self.cfg,'network down')
            self.assertTrue(saved['cached']);self.assertTrue(saved['offline'])
            self.assertEqual(saved['as_of'],self.snap['as_of'])
    def test_different_station_never_reuses_cache(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'cache.json';atomic_json(p,self.snap)
            self.cfg.base_url='http://different:8080'
            saved=cached_or_empty(p,self.cfg,'down')
            self.assertFalse(saved['cached']);self.assertEqual(saved['species'],[])
    def test_old_cache_expires(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'cache.json'
            self.snap['fetched_at']=iso(utcnow()-timedelta(days=2));atomic_json(p,self.snap)
            self.assertFalse(cached_or_empty(p,self.cfg,'down')['cached'])
    def test_demo_never_used_as_live_cache(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'cache.json';self.snap['demo']=True;atomic_json(p,self.snap)
            self.assertFalse(cached_or_empty(p,self.cfg,'down')['cached'])

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        parsed=urlparse(self.path);params=parse_qs(parsed.query)
        self.server.requests.append((parsed.path,params,self.headers.get('Authorization')))
        code=200
        if parsed.path=='/api/v1/health':
            payload={'checked_at':iso(self.server.now),'status':self.server.health_status,
                     'capture':{'state':'capturing','is_live_hardware':True},'pause':{'active':False}}
            if self.server.health_status=='critical':code=503
        elif parsed.path=='/api/v1/detections':
            if self.server.token and self.headers.get('Authorization')!='Bearer '+self.server.token:
                code=401;payload={'detail':'authentication required'}
            else:
                start=timestamp(params['since'][0]);end=timestamp(params['until'][0]);limit=int(params['limit'][0])
                records=[r for r in self.server.rows if start<=timestamp(r['event_start_utc'])<end]
                records.sort(key=lambda r:r['event_start_utc'],reverse=True)
                page=records[:limit]
                payload={'detections':page,'truncated':len(page)>=limit}
        else:code=404;payload={}
        data=json.dumps(payload).encode()
        self.send_response(code);self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)

class APITests(unittest.TestCase):
    def setUp(self):
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.server.now=NOW;self.server.rows=fixture_records(self.server.now)
        self.clock_patch=patch('gardenink.client.utcnow',return_value=NOW);self.clock_patch.start()
        self.server.requests=[];self.server.token='';self.server.health_status='ok'
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.cfg=Settings(base_url='http://127.0.0.1:%d'%self.server.server_port,page_size=30,max_pages=10)
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.clock_patch.stop()
    def test_end_to_end_actual_endpoint_contract(self):
        result=Client(self.cfg).fetch()
        self.assertEqual(result['record_count'],103);self.assertFalse(result['incomplete'])
        for path,params,auth in self.server.requests[1:]:
            self.assertEqual(path,'/api/v1/detections')
            self.assertEqual(params['group'],['bird']);self.assertEqual(params['include_synthetic'],['false'])
            self.assertEqual(params['min_score'],['0'])
    def test_page_cap_is_disclosed(self):
        self.cfg.max_pages=1
        result=Client(self.cfg).fetch();self.assertTrue(result['incomplete']);self.assertEqual(result['record_count'],30)
    def test_timestamp_tie_does_not_loop_or_claim_complete(self):
        self.server.rows=[{**self.server.rows[0],'id':'tie-%d'%i} for i in range(100)]
        result=Client(self.cfg).fetch()
        self.assertTrue(result['incomplete']);self.assertEqual(result['record_count'],30)
        self.assertIn('Timestamp tie',result['incomplete_reason'])
        self.assertEqual(len(self.server.requests),3)
    def test_critical_503_health_still_parsed(self):
        self.server.health_status='critical'
        result=Client(self.cfg).fetch()
        self.assertEqual(result['health']['status'],'critical')
        self.assertEqual(status_for(result)[0],'degraded')
    def test_bearer_auth(self):
        self.server.token='test-not-a-real-secret'
        result=Client(self.cfg,self.server.token).fetch();self.assertEqual(result['record_count'],103)
    def test_auth_rejection_actionable(self):
        self.server.token='test-not-a-real-secret'
        with self.assertRaisesRegex(APIError,'Authentication refused'):Client(self.cfg).fetch()

class RenderAndDriverTests(unittest.TestCase):
    def setUp(self):self.cfg=Settings();self.snap=demo_snapshot(self.cfg,NOW)
    def test_both_layouts_are_exact_panel_palette(self):
        for layout in ('journal','gallery'):
            im=render(self.snap,self.cfg,layout)
            self.assertEqual(im.size,(480,800));self.assertTrue(set(im.getdata())<=set(COLOURS))
    def test_empty_and_offline_render(self):
        for state in ('offline','empty','paused'):
            s=copy.deepcopy(self.snap);s.update({'demo':False,'species':[],'record_count':0,'species_count':0})
            for window in ('today','last_hour'):
                s[window].update({'species':[],'record_count':0,'species_count':0})
            if state=='offline':s['offline']=True
            if state=='paused':s['health']['pause']['active']=True
            self.assertEqual(render(s,self.cfg).size,(480,800))
    def test_unknown_species_is_not_a_fake_robin(self):
        bird={'scientific_name':'Imaginary species','name':'No real animal'}
        self.assertIsNone(artwork_path(bird))
        self.snap['species'][0].update(bird)
        self.assertEqual(render(self.snap,self.cfg).size,(480,800))
    def test_all_six_panel_codes_and_size(self):
        for c,code in zip(COLOURS,CODES):
            data=pack(Image.new('RGB',(480,800),c))
            self.assertEqual(len(data),192000);self.assertEqual(set(data),{(code<<4)|code})
    def test_reserved_code_four_never_used(self):
        data=pack(render(self.snap,self.cfg))
        self.assertNotIn(4,{n for b in data for n in (b>>4,b&15)})
    def test_rotation_is_physical_not_mirror(self):
        im=Image.new('RGB',(480,800),'white');im.putpixel((0,0),COLOURS[3])
        a=pack(im,90);b=pack(im,270)
        self.assertNotEqual(a,b)
        self.assertEqual(a[-400],0x31)
        self.assertEqual(b[399],0x13)
    def test_bad_geometry_refused(self):self.assertRaises(ValueError,pack,Image.new('RGB',(800,480)))
    def test_initialisation_matches_reviewed_vendor_sequence(self):
        class IO:
            def __init__(self):self.calls=[]
            def reset(self,n):self.calls.append(('reset',n))
            def command(self,n):self.calls.append(('cmd',n))
            def data(self,x):self.calls.append(('data',tuple(x)))
            def ready(self):return True
        io=IO();epd=EPD(self.cfg,io)
        with patch('gardenink.hardware.time.sleep'):epd.initialise()
        cmds=[v for k,v in io.calls if k=='cmd']
        self.assertEqual(cmds,[c for c,d in INIT_SEQUENCE]+[0x04])
        self.assertIn(('data',(3,32,1,224)),io.calls)
    def test_busy_timeout_is_bounded(self):
        class IO:
            def ready(self):return False
        epd=EPD(self.cfg,IO())
        with patch('gardenink.hardware.time.sleep'),patch('gardenink.hardware.time.monotonic',side_effect=[0,121]):
            with self.assertRaisesRegex(DisplayError,'BUSY timed out'):epd.wait_idle()
    def test_preview_cli_no_gpio_dependency(self):
        with tempfile.TemporaryDirectory() as td:
            env={**os.environ,'GARDEN_INK_STATE_DIR':td}
            result=subprocess.run([sys.executable,str(ROOT/'dashboard.py'),'--demo','--preview'],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue((Path(td)/'latest.png').exists())

class ConfigTests(unittest.TestCase):
    def test_base_url_forms(self):
        self.assertEqual(normalise_url('http://host:8080/api/v1/'),'http://host:8080')
        self.assertEqual(normalise_url('http://host/prefix/'),'http://host/prefix')
    def test_no_credentials_in_url(self):self.assertRaises(ValueError,normalise_url,'https://user:secret@host')
    def test_no_accidental_fast_refresh(self):
        s=Settings(refresh_seconds=30)
        self.assertRaises(ValueError,s.validate,False)
    def test_bad_timezone(self):
        s=Settings(timezone='Not/AZone');self.assertRaises(Exception,s.validate,False)
    def test_no_font_binaries_in_package(self):
        forbidden={'.ttf','.otf','.woff','.woff2','.ttc'}
        self.assertFalse([p for p in ROOT.rglob('*') if p.suffix.lower() in forbidden])

if __name__=='__main__':unittest.main()
