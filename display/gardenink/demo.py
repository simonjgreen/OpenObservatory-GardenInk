"""Invented fixtures. NEVER used as a fallback for a failed live request."""
from datetime import timedelta
from .model import iso, summarise, utcnow, build_snapshot

BIRDS=[
    ('Erithacus rubecula','European Robin',18,17),
    ('Cyanistes caeruleus','Eurasian Blue Tit',14,12),
    ('Turdus merula','Eurasian Blackbird',3,8),
    ('Parus major','Great Tit',39,23),
    ('Fringilla coelebs','Common Chaffinch',65,6),
    ('Columba palumbus','Common Woodpigeon',84,19),
    ('Carduelis carduelis','European Goldfinch',107,5),
    ('Prunella modularis','Dunnock',132,9),
    ('Troglodytes troglodytes','Eurasian Wren',164,4),
]

def fixture_records(now):
    result=[]
    for j,(sci,name,mins,count) in enumerate(BIRDS):
        for i in range(count):
            result.append({'id':'demo-%d-%d'%(j,i),'taxonomic_group':'bird','rank':'species',
                           'source_kind':'alsa','is_live_source':True,'withdrawn':False,
                           'flags':{'withdrawn':False},'review':None,
                           'event_start_utc':iso(now-timedelta(minutes=mins+i*3)),
                           'common_name':name,'scientific_name':sci,
                           'effective_common_name':name,'effective_scientific_name':sci,
                           'score':0.91})
    return result


def demo_snapshot(settings,now=None):
    now=now or utcnow()
    result=build_snapshot(fixture_records(now),now,settings)
    result.update({'demo':True,'offline':False,'cached':False,'fetched_at':iso(now),
                   'health':{'status':'ok','checked_at':iso(now),'pause':{'active':False},
                             'capture':{'state':'capturing','is_live_hardware':True}}})
    return result
