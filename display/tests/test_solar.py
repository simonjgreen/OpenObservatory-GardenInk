"""Offline checks against published values and civil-date night boundaries."""

from datetime import date, datetime, timedelta, timezone
import unittest
from zoneinfo import ZoneInfo

from gardenink import solar


UTC = timezone.utc


class SolarDayTests(unittest.TestCase):
    def test_sunrise_and_sunset_match_published_usno_values(self):
        # US Naval Observatory, Seattle 47.63 N, 122.33 W, 2026 table:
        # https://aa.usno.navy.mil/calculated/rstt/year?ID=AA&label=Seattle,+WA&lat=47.63&lon=-122.33&submit=Get+Data&task=0&tz=8&tz_sign=-1&year=2026
        # Printed times use UTC-8 all year; these fixtures add eight hours.
        # Four minutes allows the simpler NOAA fractional-year approximation.
        cases = [
            (date(2026, 1, 21), '2026-01-21T15:48:00+00:00', '2026-01-22T00:54:00+00:00'),
            (date(2026, 6, 21), '2026-06-21T12:11:00+00:00', '2026-06-22T04:11:00+00:00'),
            (date(2026, 9, 27), '2026-09-27T14:03:00+00:00', '2026-09-28T01:56:00+00:00'),
        ]
        for day, sunrise, sunset in cases:
            with self.subTest(day=day):
                actual = solar.solar_day(day, 47.63, -122.33)
                for name, expected in [('sunrise', sunrise), ('sunset', sunset)]:
                    self.assertEqual(actual[name].tzinfo, UTC)
                    self.assertLess(abs((actual[name] - datetime.fromisoformat(expected)).total_seconds()), 240)

    def test_eastern_sunrise_keeps_previous_utc_date(self):
        events = solar.solar_day(date(2026, 9, 27), -36.85, 174.76)
        self.assertEqual(events['sunrise'].date(), date(2026, 9, 26))
        self.assertEqual(events['sunset'].date(), date(2026, 9, 27))
        self.assertLess(events['sunrise'], events['sunset'])

    def test_polar_day_and_night_have_no_crossings(self):
        for latitude in [89, 90, -89, -90]:
            for day in [date(2026, 6, 21), date(2026, 12, 21)]:
                with self.subTest(latitude=latitude, day=day):
                    self.assertEqual(solar.solar_day(day, latitude, 0), {'sunrise': None, 'sunset': None})

    def test_coordinate_validation_rejects_boolean_nonfinite_and_out_of_range(self):
        cases = [(True, 0), (0, False), (float('nan'), 0), (0, float('inf')),
                 (91, 0), (-91, 0), (0, 181), (0, -181), ('51', 0), (None, 0)]
        for latitude, longitude in cases:
            with self.subTest(latitude=latitude, longitude=longitude):
                with self.assertRaises(ValueError):
                    solar.solar_day(date(2026, 9, 27), latitude, longitude)

    def test_solar_day_rejects_datetime_in_place_of_date(self):
        with self.assertRaises(ValueError):
            solar.solar_day(datetime(2026, 9, 27, tzinfo=UTC), 51.48, 0)


class NightWindowTests(unittest.TestCase):
    def test_before_sunrise_uses_previous_evening_and_after_uses_today(self):
        for now, evening in [('2026-09-28T03:00:00+01:00', '2026-09-27'),
                             ('2026-09-28T12:00:00+01:00', '2026-09-28')]:
            with self.subTest(now=now):
                window = solar.night_window(datetime.fromisoformat(now), 'Europe/London', 51.48, 0)
                self.assertEqual(window['evening_date'], evening)
                zone = ZoneInfo('Europe/London')
                self.assertEqual(window['sunset'].astimezone(zone).date().isoformat(), evening)
                self.assertEqual(window['sunrise'].astimezone(zone).date(), date.fromisoformat(evening) + timedelta(days=1))
                self.assertLess(window['sunset'], window['sunrise'])

    def test_exact_sunrise_selects_upcoming_evening(self):
        window = solar.night_window(datetime(2026, 9, 28, 2, tzinfo=UTC), 'Europe/London', 51.48, 0)
        before = solar.night_window(window['sunrise'] - timedelta(microseconds=1), 'Europe/London', 51.48, 0)
        at = solar.night_window(window['sunrise'], 'Europe/London', 51.48, 0)
        self.assertEqual(before['evening_date'], '2026-09-27')
        self.assertEqual(at['evening_date'], '2026-09-28')

    def test_dst_changes_do_not_move_following_sunrise_by_an_hour(self):
        for now, evening, sunrise_hour in [
                (datetime(2026, 3, 29, 2, tzinfo=UTC), '2026-03-28', 5),
                (datetime(2026, 10, 25, 2, tzinfo=UTC), '2026-10-24', 6)]:
            with self.subTest(now=now):
                window = solar.night_window(now, 'Europe/London', 51.48, 0)
                self.assertEqual(window['evening_date'], evening)
                self.assertEqual(window['sunrise'].date(), now.date())
                self.assertEqual(window['sunrise'].hour, sunrise_hour)
                self.assertEqual(window['sunrise'].tzinfo, UTC)
                self.assertLess(window['sunset'], now)
                self.assertLess(now, window['sunrise'])

    def test_local_dates_across_dateline_and_year_boundary(self):
        cases = [('Pacific/Kiritimati', 1.87, -157.43),
                 ('Pacific/Apia', -13.83, -171.75),
                 ('Pacific/Auckland', -36.85, 174.76),
                 ('Pacific/Honolulu', 21.31, -157.86)]
        for zone_name, latitude, longitude in cases:
            zone = ZoneInfo(zone_name)
            for hour, evening in [(2, '2026-12-31'), (12, '2027-01-01'), (22, '2027-01-01')]:
                with self.subTest(zone=zone_name, hour=hour):
                    now = datetime(2027, 1, 1, hour, tzinfo=zone)
                    window = solar.night_window(now, zone_name, latitude, longitude)
                    self.assertEqual(window['evening_date'], evening)
                    self.assertEqual(window['sunset'].astimezone(zone).date().isoformat(), evening)
                    self.assertEqual(window['sunrise'].astimezone(zone).date(), date.fromisoformat(evening) + timedelta(days=1))
                    self.assertLess(window['sunset'], window['sunrise'])
                    if hour in (2, 22):
                        self.assertLess(window['sunset'], now)
                        self.assertLess(now, window['sunrise'])

    def test_missing_crossings_cannot_form_a_night_window(self):
        for month in [6, 12]:
            self.assertIsNone(solar.night_window(datetime(2026, month, 21, tzinfo=UTC), 'Arctic/Longyearbyen', 78.22, 15.63))

    def test_naive_now_is_rejected(self):
        with self.assertRaises(ValueError):
            solar.night_window(datetime(2026, 9, 27), 'Europe/London', 51.48, 0)


if __name__ == '__main__':
    unittest.main()
