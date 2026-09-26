import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from gardenink import __version__
from gardenink.config import Settings,load
from gardenink.model import window_bounds,build_snapshot,iso,timestamp,status_for,WindowAccumulator
from gardenink.demo import fixture_records,demo_snapshot
from gardenink.render import render,selections,artwork_path,time_range,manifest
from gardenink.app import refresh_delay,check_report,main
from gardenink.storage import cached_or_empty,atomic_json
from gardenink.palette import COLOURS,pack
from gardenink.client import Client,APIError
from test_gardenink import APITests,NOW


def row(at,ident='one',sci='Erithacus rubecula',name='Robin',**kwargs):
    value=fixture_records(NOW)[0].copy()
    value.update({'id':ident,'event_start_utc':iso(at),'scientific_name':sci,
                  'effective_scientific_name':sci,'common_name':name,'effective_common_name':name})
    value.update(kwargs)
    return value


class WindowTests(unittest.TestCase):
    def setUp(self):self.cfg=Settings()
    def test_today_is_local_midnight_not_24h(self):
        day,hour=window_bounds(timestamp('2026-09-25T14:00:00Z'),'Europe/London')
        self.assertEqual(iso(day),'2026-09-24T23:00:00Z')
        self.assertEqual(iso(hour),'2026-09-25T13:00:00Z')
    def test_previous_day_in_trailing_hour_is_not_today(self):
        now=timestamp('2026-09-24T23:15:00Z') # 00:15 local
        records=[row(now-timedelta(minutes=10),'today'),row(now-timedelta(minutes=45),'yesterday')]
        s=build_snapshot(records,now,self.cfg)
        self.assertEqual(s['today']['record_count'],1)
        self.assertEqual(s['last_hour']['record_count'],2)
    def test_today_does_not_include_yesterday(self):
        day,_=window_bounds(NOW,self.cfg.timezone)
        records=[row(day,'start'),row(day-timedelta(microseconds=1),'before'),row(NOW,'end')]
        s=build_snapshot(records,NOW,self.cfg)
        self.assertEqual(s['today']['record_count'],1)
        self.assertEqual(s['last_hour']['record_count'],0)
    def test_hour_start_included_end_excluded(self):
        hour=NOW-timedelta(hours=1)
        records=[row(hour,'start'),row(hour-timedelta(microseconds=1),'before'),row(NOW,'end')]
        self.assertEqual(build_snapshot(records,NOW,self.cfg)['last_hour']['record_count'],1)
    def test_spring_dst_midnight_and_elapsed_hour(self):
        now=timestamp('2026-03-29T02:30:00Z')
        day,hour=window_bounds(now,self.cfg.timezone)
        self.assertEqual(iso(day),'2026-03-29T00:00:00Z')
        self.assertEqual((now-hour).total_seconds(),3600)
        self.assertEqual(now.astimezone(ZoneInfo(self.cfg.timezone)).hour,3)
    def test_autumn_dst_day_can_be_longer_than_clock(self):
        now=timestamp('2026-10-25T02:30:00Z')
        day,hour=window_bounds(now,self.cfg.timezone)
        self.assertEqual(iso(day),'2026-10-24T23:00:00Z')
        self.assertEqual((now-day).total_seconds(),3.5*3600)
        self.assertEqual((now-hour).total_seconds(),3600)
    def test_autumn_repeated_hour_label_disambiguates_offsets(self):
        w={'since':'2026-10-25T00:30:00Z','as_of':'2026-10-25T01:30:00Z'}
        self.assertEqual(time_range(w,ZoneInfo('Europe/London')),'01:30 BST–01:30 GMT')
    def test_duplicate_records_not_double_counted(self):
        r=row(NOW-timedelta(minutes=1))
        s=build_snapshot([r,r],NOW,self.cfg)
        self.assertEqual(s['today']['record_count'],1)
        self.assertEqual(s['last_hour']['record_count'],1)
    def test_scores_do_not_make_window_partial(self):
        records=[row(NOW-timedelta(minutes=i+1),str(i),score=.2 if i%2 else .9) for i in range(10)]
        s=build_snapshot(records,NOW,self.cfg)
        self.assertFalse(s['today']['incomplete']);self.assertEqual(s['today']['record_count'],5)
        self.assertEqual(s['today']['excluded']['below_threshold'],5)
    def test_reviewed_low_score_survives_both_windows(self):
        r=row(NOW-timedelta(minutes=1),score=.1,review={'status':'confirmed'})
        s=build_snapshot([r],NOW,self.cfg)
        self.assertEqual(s['today']['record_count'],1);self.assertEqual(s['last_hour']['record_count'],1)
    def test_numeric_time_order_with_mixed_fractional_precision(self):
        a=row(NOW-timedelta(seconds=2),'a')
        b=row(NOW-timedelta(seconds=2)+timedelta(microseconds=300),'b')
        s=build_snapshot([b,a],NOW,self.cfg)
        self.assertEqual(s['today']['species'][0]['last'],b['event_start_utc'])
    def test_malformed_cache_from_v1_is_not_reused(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'cache.json';s=demo_snapshot(self.cfg);s['demo']=False;s['schema_version']=1
            atomic_json(p,s);self.assertFalse(cached_or_empty(p,self.cfg,'offline')['cached'])
    def test_cached_windows_preserved_including_yesterday_date(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'cache.json'
            s=demo_snapshot(self.cfg);s['demo']=False;atomic_json(p,s)
            old=cached_or_empty(p,self.cfg,'offline')
            self.assertEqual(s['today']['since'],old['today']['since'])
            self.assertEqual(s['last_hour']['as_of'],old['last_hour']['as_of'])
            self.assertTrue(old['offline']);self.assertTrue(old['cached'])
    def test_timezone_change_invalidates_cached_today(self):
        a=self.cfg.identity();self.cfg.timezone='UTC';self.assertNotEqual(a,self.cfg.identity())


class HourlyAPITests(APITests):
    def test_separate_day_and_hour_completeness(self):
        self.cfg.page_size=3;self.cfg.max_pages=1
        self.server.rows=[row(NOW-timedelta(minutes=m),str(m)) for m in (1,5,61,180,300)]
        s=Client(self.cfg).fetch()
        self.assertTrue(s['today']['incomplete'])
        self.assertFalse(s['last_hour']['incomplete'])
        self.assertEqual(s['last_hour']['record_count'],2)
    def test_two_thousand_record_ceiling_removed(self):
        self.cfg.page_size=500;self.cfg.max_pages=64
        self.server.rows=[row(NOW-timedelta(seconds=10+i*4),'r'+str(i),score=.2 if i%3==0 else .9)
                          for i in range(3100)]
        s=Client(self.cfg).fetch()
        self.assertFalse(s['today']['incomplete'])
        self.assertEqual(s['today']['raw_rows'],3100)
        self.assertEqual(s['today']['record_count'],2066)
        self.assertGreater(s['scan']['pages'],4)
    def test_api_query_uses_midnight_not_legacy_lookback(self):
        Client(self.cfg).fetch()
        _,params,_=self.server.requests[1]
        self.assertEqual(params['since'],['2026-09-24T23:00:00Z'])
    def test_api_query_before_midnight_for_early_hour(self):
        self.server.now=timestamp('2026-09-24T23:15:00Z')
        self.server.rows=[row(self.server.now-timedelta(minutes=40),'previous-day')]
        s=Client(self.cfg).fetch()
        self.assertEqual(s['today']['record_count'],0)
        self.assertEqual(s['last_hour']['record_count'],1)
    def test_each_fetch_rechecks_reviews(self):
        self.server.rows=[row(NOW-timedelta(minutes=5))]
        client=Client(self.cfg)
        self.assertEqual(client.fetch()['today']['record_count'],1)
        self.server.rows[0]['review']={'status':'rejected'}
        self.assertEqual(client.fetch()['today']['record_count'],0)


class ScheduleTests(unittest.TestCase):
    def setUp(self):self.cfg=Settings()
    def test_defaults_hourly(self):
        self.assertEqual(self.cfg.refresh_seconds,3600)
        self.assertEqual(self.cfg.max_pages,64)
    def test_cold_start_immediate(self):self.assertEqual(refresh_delay({},self.cfg,1000),0)
    def test_old_first_upgrade_guard_not_hour(self):
        self.assertEqual(refresh_delay({'attempted_at':1000},self.cfg,1050),130)
        self.assertEqual(refresh_delay({'attempted_at':1000},self.cfg,1200),0)
    def test_following_frame_hourly(self):
        meta={'attempted_at':1000,'attempt_version':__version__}
        self.assertEqual(refresh_delay(meta,self.cfg,1100),3500)
        self.assertEqual(refresh_delay(meta,self.cfg,4600),0)
    def test_failed_attempt_also_obeys_hour(self):
        meta={'attempted_at':1000,'attempt_version':__version__,'success_at':0}
        self.assertEqual(refresh_delay(meta,self.cfg,1200),3400)
    def test_backwards_clock_does_not_allow_rapid_repeat(self):
        self.assertEqual(refresh_delay({'attempted_at':1000,'attempt_version':__version__},self.cfg,900),3600)
    def test_once_waits_before_fetch_not_after(self):
        events=[]
        class Event:
            def is_set(self):return False
            def wait(self,seconds):events.append(('wait',seconds));return False
            def set(self):pass
        def fetch():events.append(('fetch',None));return demo_snapshot(self.cfg,NOW)
        def display(*args):events.append(('display',None))
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ,{'GARDEN_INK_STATE_DIR':td}), \
             patch('gardenink.app.load',return_value=Settings(base_url='http://station:8080')), \
             patch('gardenink.app.threading.Event',return_value=Event()), \
             patch('gardenink.app.signal.signal'), patch('gardenink.app.lock_display',return_value=None), \
             patch('gardenink.app.read_meta',return_value={'attempted_at':1000,'attempt_version':__version__}), \
             patch('gardenink.app.time.time',return_value=1100), \
             patch('gardenink.app.Client.fetch',side_effect=fetch), \
             patch('gardenink.hardware.display',side_effect=display):
            self.assertEqual(main(['--once']),0)
        self.assertEqual([e[0] for e in events],['wait','fetch','display'])
        self.assertEqual(events[0][1],3500)


class NewRenderTests(unittest.TestCase):
    def setUp(self):self.cfg=Settings();self.snap=demo_snapshot(self.cfg,NOW)
    def test_all_47_visible_species_have_images(self):
        cat=json.loads((ROOT/'assets/species_catalog.json').read_text())
        self.assertEqual(len(cat),47)
        for bird in cat:self.assertTrue(artwork_path(bird).is_file(),bird)
    def test_jackdaw_alias_maps_to_same_image(self):
        self.assertEqual(artwork_path({'scientific_name':'Corvus monedula'}),
                         artwork_path({'scientific_name':'Coloeus monedula'}))
    def test_feature_always_from_last_hour(self):
        feature,daily=selections(self.snap)
        self.assertEqual(feature['scientific_name'],'Turdus merula')
        self.assertGreaterEqual(timestamp(feature['last']),timestamp(self.snap['last_hour']['since']))
        self.assertNotIn(feature['scientific_name'],[b['scientific_name'] for b in daily])
    def test_daily_ranked_by_count_not_same_as_hour(self):
        _,daily=selections(self.snap)
        self.assertEqual([b['count'] for b in daily],sorted([b['count'] for b in daily],reverse=True))
    def test_quiet_hour_never_relabels_earlier_bird(self):
        records=[row(NOW-timedelta(hours=3),'old')]
        s=build_snapshot(records,NOW,self.cfg)
        self.assertIsNone(selections(s)[0]);self.assertEqual(len(selections(s)[1]),1)
        self.assertEqual(render(s,self.cfg).size,(480,800))
    def test_midnight_empty_today_with_previous_hour(self):
        now=timestamp('2026-09-24T23:05:00Z')
        s=build_snapshot([row(now-timedelta(minutes=30),'old')],now,self.cfg)
        self.assertEqual(s['today']['record_count'],0)
        self.assertIsNotNone(selections(s)[0])
        self.assertEqual(render(s,self.cfg).size,(480,800))
    def test_all_species_can_be_featured_with_safe_dimensions(self):
        cat=json.loads((ROOT/'assets/species_catalog.json').read_text())
        for bird in cat:
            s=build_snapshot([row(NOW-timedelta(minutes=1),'x',bird['scientific_name'],bird['display_name'])],NOW,self.cfg)
            im=render(s,self.cfg)
            self.assertEqual(im.size,(480,800))
            self.assertTrue(set(im.getdata())<=set(COLOURS))
    def test_unknown_species_name_kept_no_fake_robin(self):
        s=build_snapshot([row(NOW-timedelta(minutes=1),'x','Unknown species','Unillustrated bird')],NOW,self.cfg)
        self.assertIsNone(artwork_path(s['last_hour']['species'][0]))
        self.assertEqual(render(s,self.cfg).size,(480,800))
    def test_all_status_states_render_native_palette(self):
        for state in ('ok','paused','offline','not_live','degraded','empty'):
            s=copy.deepcopy(self.snap);s['demo']=False
            if state=='paused':s['health']['pause']['active']=True
            if state=='offline':s.update(offline=True,cached=True)
            if state=='not_live':s['health']['capture']['is_live_hardware']=False
            if state=='degraded':s['health']['status']='critical'
            if state=='empty':s=build_snapshot([],NOW,self.cfg)
            self.assertTrue(set(render(s,self.cfg).getdata())<=set(COLOURS))
    def test_check_exposes_both_windows_and_missing_art(self):
        report=check_report(self.snap,self.cfg)
        self.assertIn('today',report);self.assertIn('last_hour',report)
        self.assertEqual(report['artwork_missing'],[])


class UpgradeTests(unittest.TestCase):
    def test_upgrade_keeps_site_and_sets_only_hourly_policy(self):
        sys.path.insert(0,str(ROOT/'tools'))
        from upgrade_installation import upgraded_settings
        values={'base_url':'http://test-station:8080','rotation':270,'title':'Our plot',
                'min_score':.83,'timezone':'Europe/London','max_pages':4,
                'refresh_seconds':300,'api_token_file':'private-token.txt'}
        cfg=upgraded_settings(values)
        self.assertEqual(cfg.base_url,values['base_url']);self.assertEqual(cfg.rotation,270)
        self.assertEqual(cfg.api_token_file,'private-token.txt');self.assertEqual(cfg.min_score,.83)
        self.assertEqual(cfg.max_pages,64);self.assertEqual(cfg.refresh_seconds,3600)
        self.assertEqual(cfg.title,'Our plot')
    def test_full_upgrade_preserves_token_custom_art_state_and_backup(self):
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/'garden_ink';target.mkdir()
            (target/'gardenink').mkdir();(target/'gardenink/hardware.py').write_text('# old hardware\n')
            (target/'config.json').write_text(json.dumps({'base_url':'http://test:8080','rotation':270}))
            (target/'token.txt').write_text('fake-test-token');(target/'token.txt').chmod(0o600)
            (target/'state').mkdir();(target/'state/display.json').write_text('{"attempted_at":1000}')
            (target/'assets/custom').mkdir(parents=True);(target/'assets/custom/own.png').write_bytes(b'custom')
            cmd=[sys.executable,str(ROOT/'tools/upgrade_installation.py'),str(ROOT),str(target)]
            p=subprocess.run(cmd,text=True,capture_output=True)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual((target/'token.txt').read_text(),'fake-test-token')
            self.assertEqual((target/'assets/custom/own.png').read_bytes(),b'custom')
            self.assertEqual(json.loads((target/'state/display.json').read_text())['attempted_at'],1000)
            cfg=json.loads((target/'config.json').read_text())
            self.assertEqual(cfg['rotation'],270);self.assertEqual(cfg['refresh_seconds'],3600)
            backups=list(Path(td).glob('garden_ink.backup-*'));self.assertEqual(len(backups),1)
            self.assertEqual(backups[0].stat().st_mode&0o777,0o700)
            self.assertEqual((backups[0]/'token.txt').read_text(),'fake-test-token')
            self.assertNotIn('fake-test-token',p.stdout+p.stderr)

if __name__=='__main__':unittest.main()
