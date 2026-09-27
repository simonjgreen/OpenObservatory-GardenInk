import copy
import sys
import unittest
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gardenink.config import Settings
from gardenink.model import timestamp, iso
from gardenink import night

START = timestamp('2026-09-27T17:45:00Z')
END = timestamp('2026-09-27T21:45:00Z')


def bat(ident='bat', when=END-timedelta(minutes=5), **overrides):
    r = {'id': ident, 'event_start_utc': iso(when), 'source_kind': 'alsa',
         'is_live_source': True, 'taxonomic_group': 'bat', 'rank': None,
         'label': 'bat pass', 'score': .8, 'review': None, 'withdrawn': False,
         'flags': {}, 'detector': {'plugin_id': 'ultrasonic-pass-v1', 'model_version': '1'}}
    r.update(overrides)
    return r


def bird(ident='bird', when=END-timedelta(minutes=5), owl=False, **overrides):
    r = bat(ident, when)
    r.update(taxonomic_group='bird', rank='species',
             scientific_name='Strix aluco' if owl else 'Erithacus rubecula',
             common_name='Tawny Owl' if owl else 'Robin')
    r.update(overrides)
    return r


def report(**overrides):
    value = {'available': True, 'evening_date': '2026-09-27', 'since': iso(START),
             'as_of': iso(END), 'sunset': iso(START), 'sunrise': '2026-09-28T06:00:00Z',
             'trigger_ready': True, 'recent': {'bird_count': 5, 'baseline_bird_count': 80,
             'bat_count': 10, 'bat_bins': 3, 'owl_count': 0}, 'owls': [], 'incomplete': False}
    value.update(overrides)
    return value


class BatPolicyTests(unittest.TestCase):
    def test_generic_bat_pass_needs_no_species_rank(self):
        self.assertIsNotNone(night.normalise_bat(bat(), START, END, .5))

    def test_synthetic_rejected_withdrawn_and_invalid_scores_are_excluded(self):
        for change in ({'source_kind':'file'}, {'is_live_source':False}, {'withdrawn':True},
                       {'flags':{'withdrawn':True}}, {'review':{'status':'rejected'}},
                       {'review':{'status':'new-unknown-state'}}, {'score':True},
                       {'score':float('nan')}, {'score':.2}, {'taxonomic_group':'bird'}):
            with self.subTest(change=change):
                self.assertIsNone(night.normalise_bat(bat(**change), START, END, .5))

    def test_human_confirmation_preserves_low_score_bat(self):
        self.assertIsNotNone(night.normalise_bat(bat(score=.1, review={'status':'confirmed'}), START, END, .5))

    def test_correction_must_not_fall_back_to_original_claim(self):
        self.assertIsNone(night.normalise_bat(bat(review={'status':'corrected'}), START, END, .5))

    def test_utc_boundaries_are_start_inclusive_end_exclusive(self):
        self.assertIsNotNone(night.normalise_bat(bat(when=START), START, END, .5))
        self.assertIsNone(night.normalise_bat(bat(when=END), START, END, .5))


class NightReductionTests(unittest.TestCase):
    def test_owls_excluded_from_daytime_quiet_test_and_duplicate_ids_not_counted(self):
        records = [bird(str(i), START-timedelta(minutes=i+1)) for i in range(40)]
        records += [bird('owl', owl=True), bird('recent'), bird('recent')]
        bats = [bat(str(i), END-timedelta(minutes=2+(i%3)*5)) for i in range(10)]
        data = night.reduce_night(records, bats+[bats[0]], START, END, Settings())
        self.assertEqual(data['record_count'], 10)
        self.assertEqual(data['recent'], {'bird_count':1,'baseline_bird_count':40,
                                         'bat_count':10,'bat_bins':3,'owl_count':1})
        self.assertEqual(data['owls'][0]['count'], 1)

    def test_hour_bins_use_elapsed_utc_across_midnight_and_repeated_hour(self):
        start=timestamp('2026-10-24T23:30:00Z'); end=timestamp('2026-10-25T02:00:00Z')
        rows=[bat('a',timestamp('2026-10-25T00:00:00Z')),
              bat('b',timestamp('2026-10-25T01:00:00Z')),
              bat('c',timestamp('2026-10-25T01:45:00Z'))]
        data=night.reduce_night([],rows,start,end,Settings())
        self.assertEqual([b['count'] for b in data['bins']], [1,1,1])
        self.assertEqual([b['end_hour'] for b in data['bins']], [1,2,2.5])
        self.assertEqual(data['comparison_hours'],2)

    def test_human_corrected_owl_uses_effective_identity(self):
        r=bird(score=.1, review={'status':'corrected','corrected_scientific_name':'Strix aluco',
                                'corrected_common_name':'Tawny Owl'})
        data=night.reduce_night([r],[],START,END,Settings())
        self.assertEqual(data['recent']['bird_count'],0)
        self.assertEqual(data['owls'][0]['scientific_name'],'Strix aluco')


class SwitchingTests(unittest.TestCase):
    def setUp(self): self.cfg=Settings()

    def select(self, data=None, state=None, now=END, **snap):
        snapshot={'night':data or report(),'as_of':iso(now),'offline':False,'clock_skew':False,**snap}
        return night.select_edition(snapshot,self.cfg,state or {},now)

    def test_sunset_and_quiet_and_sustained_bats_are_all_required(self):
        layout,state=self.select()
        self.assertEqual(layout,'night-rhythm')
        self.assertEqual(state['evening_date'],'2026-09-27')
        for changes in ({'bird_count':11},{'bat_count':9},{'bat_bins':2}):
            data=report(); data['recent'].update(changes)
            self.assertEqual(self.select(data)[0],'journal')
        self.assertEqual(self.select(now=START-timedelta(seconds=1))[0],'journal')

    def test_owl_exception_still_requires_bird_quiet(self):
        data=report();data['recent'].update(bat_count=0,bat_bins=0,owl_count=1)
        data['owls']=[{'scientific_name':'Strix aluco'}]
        layout,state=self.select(data)
        self.assertEqual(layout,'night-journal')
        data['recent']['bird_count']=11
        self.assertEqual(self.select(data)[0],'journal')

    def test_already_quiet_evening_with_zero_baseline_can_enter(self):
        data=report();data['recent'].update(bird_count=2,baseline_bird_count=0)
        self.assertEqual(self.select(data)[0],'night-rhythm')

    def test_missing_coverage_offline_and_clock_skew_cannot_create_latch(self):
        self.assertEqual(self.select(report(trigger_ready=False))[0],'journal')
        self.assertEqual(self.select(offline=True)[0],'journal')
        self.assertEqual(self.select(clock_skew=True)[0],'journal')

    def test_latch_survives_quietness_restart_and_midnight(self):
        _,state=self.select()
        data=report(trigger_ready=False); data['recent'].update(bat_count=0,bat_bins=0,bird_count=100)
        layout,next_state=self.select(data,copy.deepcopy(state),timestamp('2026-09-28T00:15:00Z'))
        self.assertIn(layout,night.NIGHT_LAYOUTS)
        self.assertEqual(next_state['evening_date'],'2026-09-27')
        self.assertEqual(self.select(data,state,timestamp('2026-09-28T06:00:00Z'))[0],'journal')

    def test_repeated_manual_refresh_same_hour_keeps_page_and_state_input_immutable(self):
        _,state=self.select(); before=copy.deepcopy(state)
        layout,next_state=self.select(state=state,now=END+timedelta(minutes=3))
        self.assertEqual(layout,'night-rhythm')
        self.assertEqual(state,before)
        self.assertEqual(next_state['page'],state['page'])
        self.assertEqual(self.select(state=state,now=END+timedelta(hours=1))[0],'night-history')

    def test_corrupt_saved_page_is_discarded_and_backward_slot_does_not_advance(self):
        _, state = self.select()
        corrupt = dict(state, page=99)
        self.assertEqual(self.select(state=corrupt, offline=True)[0], 'journal')
        layout, held = self.select(state=state, now=END-timedelta(hours=1))
        self.assertEqual(layout, 'night-rhythm')
        self.assertEqual(held, state)

    def test_old_identity_or_previous_night_cannot_latch_new_report(self):
        _,state=self.select();state['identity']='another station'
        self.assertEqual(self.select(report(trigger_ready=False),state)[0],'journal')


class CoverageTests(unittest.TestCase):
    def test_merge_overlaps_clip_window_exclude_synthetic_low_rate_and_pauses(self):
        cov={'streams':[{'start_utc':iso(START),'end_utc':iso(END),'source_kind':'alsa',
                         'sample_rate':384000,'suspect':False,'discontinuity_count':0}],
             'pauses':[], 'gaps':0}
        cov['streams'].append(dict(cov['streams'][0]))
        self.assertEqual(night.capture_fraction(cov,START,END,192000),1)
        cov['pauses']=[{'start_utc':iso(START),'end_utc':iso(START+timedelta(hours=1))}]
        self.assertEqual(night.capture_fraction(cov,START,END,192000),.75)
        for r in cov['streams']:r['sample_rate']=48000
        self.assertEqual(night.capture_fraction(cov,START,END,192000),0)

    def test_lifetime_discontinuities_do_not_erase_gap_free_recent_coverage(self):
        cov={'streams':[{'start_utc':iso(START),'end_utc':iso(END),'source_kind':'alsa',
                         'sample_rate':384000,'suspect':False,'discontinuity_count':8}],
             'pauses':[], 'gaps':0, 'estimated_missing_frames':0}
        self.assertEqual(night.capture_fraction(cov,START,END,96000),1)
        cov.update(gaps=1, estimated_missing_frames=384000*3600)
        self.assertEqual(night.capture_fraction(cov,START,END,96000),.75)
        cov['estimated_missing_frames']=0
        self.assertEqual(night.capture_fraction(cov,START,END,96000),0)

    def test_absent_coverage_does_not_mean_empty_garden(self):
        self.assertEqual(night.capture_fraction({},START,END,48000),0)


if __name__=='__main__': unittest.main()
