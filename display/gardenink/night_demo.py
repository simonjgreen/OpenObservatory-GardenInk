"""Fixed, explicitly labelled night fixtures; never a live-data fallback."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .demo import demo_snapshot
from .model import iso


def demo_night_snapshot(settings):
    zone = ZoneInfo(settings.timezone)
    sunset = datetime(2026, 9, 27, 18, 45, tzinfo=zone)
    end = datetime(2026, 9, 27, 22, 45, tzinfo=zone)
    owl_first = datetime(2026, 9, 27, 21, 4, tzinfo=zone)
    owl_last = datetime(2026, 9, 27, 21, 18, tzinfo=zone)
    snapshot = demo_snapshot(settings, end)
    snapshot['night'] = {
        'since': iso(sunset), 'as_of': iso(end), 'sunset': iso(sunset),
        'sunrise': iso(datetime(2026, 9, 28, 6, 55, tzinfo=zone)),
        'evening_date': '2026-09-27', 'record_count': 184,
        'incomplete': False, 'available': True,
        'owls': [{'scientific_name': 'Strix aluco', 'name': 'Tawny owl',
                  'count': 3, 'first': iso(owl_first), 'last': iso(owl_last)}],
        'bins': [{'start_hour': i, 'end_hour': i + 1, 'count': count,
                  'incomplete': False, 'owl_count': 3 if i == 2 else 0,
                  'median': median}
                 for i, (count, median) in enumerate(zip((34, 72, 51, 27), (27, 50, 36, 27)))],
        'history': [{'date': '2026-09-%02d' % (21 + i), 'total': total,
                     'owl_count': 3 if i in (2, 4, 6) else 0,
                     'incomplete': False, 'comparable': True}
                    for i, total in enumerate((119, 134, 98, 146, 158, 126, 184))],
        'comparison_hours': 4, 'baseline_nights': 7,
        'first_bat': iso(sunset + timedelta(minutes=24)),
    }
    return snapshot
