"""Approximate sunset/sunrise windows, with UTC arithmetic and civil dates.

Independent implementation of NOAA's General Solar Position Calculations:
https://gml.noaa.gov/grad/solcalc/solareqns.PDF
The fractional-year approximation is suitable for scheduling to a few minutes,
not precise astronomical observations. The 90.833-degree zenith accounts for
the solar disc and standard refraction; this is sunset, not civil twilight.
There are no network requests, dependencies or machine-local timezone defaults.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import math
from zoneinfo import ZoneInfo


UTC = timezone.utc


def _coordinates(latitude: float, longitude: float) -> None:
    for name, value, limit in [('latitude', latitude, 90), ('longitude', longitude, 180)]:
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or not -limit <= value <= limit):
            raise ValueError(f'{name} must be a finite number between {-limit} and {limit}')


def solar_day(day: date, latitude: float, longitude: float) -> dict[str, datetime | None]:
    """Crossings around the longitude's solar noon for ``day``, as UTC times.

    Longitude is positive east. A crossing can lie on an adjacent UTC date;
    elapsed minutes must never be reduced modulo 24 hours. Without a timezone,
    this function cannot assign political civil dates (e.g. Kiritimati).
    ``night_window`` does that separately. No horizon crossing returns None.
    """
    if not isinstance(day, date) or isinstance(day, datetime):
        raise ValueError('day must be a date, not a datetime')
    _coordinates(latitude, longitude)
    days_in_year = date(day.year, 12, 31).timetuple().tm_yday
    gamma = math.tau * (day.timetuple().tm_yday - 1) / days_in_year
    equation_minutes = 229.18 * (
        0.000075 + 0.001868 * math.cos(gamma) - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma) - 0.040849 * math.sin(2 * gamma)
    )
    declination = (
        0.006918 - 0.399912 * math.cos(gamma) + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma) + 0.000907 * math.sin(2 * gamma)
        - 0.002697 * math.cos(3 * gamma) + 0.00148 * math.sin(3 * gamma)
    )
    latitude_radians = math.radians(latitude)
    denominator = math.cos(latitude_radians) * math.cos(declination)
    if abs(denominator) < 1e-12:
        return {'sunrise': None, 'sunset': None}
    cosine_hour_angle = (
        math.cos(math.radians(90.833)) - math.sin(latitude_radians) * math.sin(declination)
    ) / denominator
    if not -1 < cosine_hour_angle < 1:
        # A tangent at exactly +/-1 is not a rising/setting crossing either.
        return {'sunrise': None, 'sunset': None}
    half_day_minutes = 4 * math.degrees(math.acos(cosine_hour_angle))
    noon_minutes = 720 - 4 * longitude - equation_minutes
    midnight = datetime(day.year, day.month, day.day, tzinfo=UTC)
    return {
        'sunrise': midnight + timedelta(minutes=noon_minutes - half_day_minutes),
        'sunset': midnight + timedelta(minutes=noon_minutes + half_day_minutes),
    }


def night_window(now: datetime, zone_name: str, latitude: float, longitude: float) -> dict | None:
    """Return the previous or upcoming evening's sunset and following sunrise.

    Before today's local sunrise, select yesterday's evening; from sunrise
    onward select today's evening, even while its sunset is still in the future.
    Callers must separately gate entry on ``sunset <= now < sunrise``.
    Missing crossings or an ambiguous civil-date mapping return None.
    """
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('now must be a timezone-aware datetime')
    _coordinates(latitude, longitude)
    zone = ZoneInfo(zone_name)
    local_day = now.astimezone(zone).date()
    now_utc = now.astimezone(UTC)
    days = {}

    def crossing(civil_day: date, name: str) -> datetime | None:
        matches = []
        # Longitude and civil UTC offsets need not have the same sign. Even
        # UTC+14 at western longitudes is handled by checking nearby solar days.
        for shift in range(-2, 3):
            candidate_day = civil_day + timedelta(days=shift)
            if candidate_day not in days:
                days[candidate_day] = solar_day(candidate_day, latitude, longitude)
            event = days[candidate_day][name]
            if event is not None and event.astimezone(zone).date() == civil_day:
                matches.append(event)
        return matches[0] if len(matches) == 1 else None

    today_sunrise = crossing(local_day, 'sunrise')
    if today_sunrise is None:
        return None
    evening_day = local_day - timedelta(days=1) if now_utc < today_sunrise else local_day
    sunset = crossing(evening_day, 'sunset')
    sunrise = crossing(evening_day + timedelta(days=1), 'sunrise')
    if sunset is None or sunrise is None or sunrise <= sunset:
        return None
    return {'evening_date': evening_day.isoformat(), 'sunset': sunset, 'sunrise': sunrise}
