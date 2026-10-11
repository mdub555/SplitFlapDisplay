"""Tests for the Calendar, Word of the Day and On This Day apps, with their
feeds faked: the iCal parsing and today's events, the Merriam-Webster feed's
shapes, and picking the day's history events.

Run from frontend/:   python -m unittest tests.test_info_apps
"""
import os
import sys
import unittest
from datetime import date, datetime, timedelta
from unittest import mock

import pytz
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apps.base import Grid  # noqa: E402
from apps.builtin import calendar_app, on_this_day, word_of_the_day  # noqa: E402
from apps.builtin._shared import plain_text  # noqa: E402

TZ = pytz.timezone('US/Eastern')


def _response(content=b'', data=None):
    res = mock.Mock(content=content)
    res.json = lambda: data
    res.raise_for_status = lambda: None
    return res


def _lines(grid, page):
    return [page[i:i + grid.cols] for i in range(0, grid.size, grid.cols)]


class PlainTextTest(unittest.TestCase):
    def test_accents_quotes_and_dashes(self):
        self.assertEqual(plain_text('Café’s  “über” — a; b…'), 'CAFES "UBER" - A, B...')


class CalendarTest(unittest.TestCase):
    NOW = TZ.localize(datetime(2026, 10, 11, 9, 0))

    def ev(self, h, m, minutes=30, title='X', day=0):
        start = self.NOW.replace(hour=h, minute=m) + timedelta(days=day)
        return (start, start + timedelta(minutes=minutes), False, title)

    def test_todays_events_are_the_rest_of_today_all_day_first(self):
        whole = (date(2026, 10, 11), date(2026, 10, 12), True, 'BIRTHDAY')
        events = [self.ev(14, 0, title='LATER'), self.ev(8, 0, title='OVER'),
                  self.ev(8, 45, title='UNDER WAY'), self.ev(10, 0, title='TOMORROW', day=1), whole]
        titles = [e[3] for e in calendar_app.todays_events(events, self.NOW)]
        self.assertEqual(titles, ['BIRTHDAY', 'UNDER WAY', 'LATER'])
        titles = [e[3] for e in calendar_app.todays_events(events, self.NOW, all_day=False)]
        self.assertEqual(titles, ['UNDER WAY', 'LATER'])

    def test_rows_line_up_the_times(self):
        events = [(date(2026, 10, 11), None, True, 'BIRTHDAY'), self.ev(8, 45, title='STANDUP'),
                  self.ev(9, 30, title='DENTIST'), self.ev(12, 0, title='A VERY LONG LUNCH')]
        self.assertEqual(calendar_app.event_rows(events, self.NOW, 16), [
            'BIRTHDAY        ',
            '   NOW STANDUP  ',
            ' 9:30A DENTIST  ',
            '12:00P A VERY LO',
        ])

    def test_an_ical_feed_end_to_end(self):
        now = datetime.now(TZ)
        today = now.date()
        later = now + timedelta(minutes=30)
        stamp = lambda dt: dt.astimezone(pytz.utc).strftime('%Y%m%dT%H%M%SZ')  # noqa: E731
        ics = '\r\n'.join([
            'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:test',
            'BEGIN:VEVENT', 'UID:1', f'DTSTART:{stamp(later)}', f'DTEND:{stamp(later + timedelta(minutes=5))}',
            'SUMMARY:Café chat', 'END:VEVENT',
            # Weekly from a week ago: today's happens today.
            'BEGIN:VEVENT', 'UID:2', f'DTSTART;VALUE=DATE:{today - timedelta(days=7):%Y%m%d}',
            f'DTEND;VALUE=DATE:{today - timedelta(days=6):%Y%m%d}', 'RRULE:FREQ=WEEKLY',
            'SUMMARY:Bins out', 'END:VEVENT',
            'END:VCALENDAR', ''])
        grid = Grid(4, 16)
        settings = {'calendar_ical_url': 'webcal://example.com/basic.ics', 'timezone': 'US/Eastern'}
        with mock.patch.object(requests, 'get', return_value=_response(ics.encode())) as get:
            frames = calendar_app.CalendarApp().get_pages(settings, {}, grid)
        self.assertEqual(get.call_args[0][0], 'https://example.com/basic.ics')
        rows = _lines(grid, frames[0].text)
        self.assertEqual(rows[0], 'BINS OUT'.ljust(16))
        # (Unless "later" crossed midnight, which leaves it off today.)
        if later.date() == today:
            self.assertRegex(rows[1], r'^ ?\d+:\d\d[AP] CAFE CHAT *$')

    def test_no_address_and_a_failed_fetch_say_so(self):
        grid = Grid(3, 15)
        self.assertIn('NO ICAL ADDRESS', calendar_app.CalendarApp().get_pages({}, {}, grid)[0].text)
        with mock.patch.object(requests, 'get', side_effect=requests.ConnectionError()):
            frames = calendar_app.CalendarApp().get_pages({'calendar_ical_url': 'https://x'}, {}, grid)
        self.assertIn('FETCH ERROR', frames[0].text)


FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


class WordOfTheDayTest(unittest.TestCase):
    # The start of Merriam-Webster's real feed on 11 Oct 2026.
    with open(os.path.join(FIXTURES, 'mw_wotd.xml'), 'rb') as f:
        REAL = f.read()

    def test_the_real_feed(self):
        self.assertEqual(word_of_the_day.parse_feed(self.REAL),
                         {'word': 'galore', 'part': 'adjective', 'meaning': 'in large numbers or amounts'})

    def test_the_real_description_without_a_short_definition(self):
        feed = self.REAL.replace(b'<merriam:shortdef><![CDATA[in large numbers or amounts]]></merriam:shortdef>', b'')
        wotd = word_of_the_day.parse_feed(feed)
        self.assertEqual(wotd['part'], 'adjective')
        self.assertTrue(wotd['meaning'].startswith('Galore is an informal adjective'))

    def parse(self, description, extra=''):
        return word_of_the_day.parse_feed(
            f'<rss xmlns:mw="https://www.merriam-webster.com"><channel><item><title>ebullient</title>{extra}'
            f'<description><![CDATA[{description}]]></description></item>'
            f'<item><title>yesterday</title></item></channel></rss>')

    def test_a_what_it_means_heading(self):
        wotd = self.parse("<p><strong>Merriam-Webster's Word of the Day for October 11, 2026 is:</strong></p>"
                          '<p><strong>ebullient</strong> &#92;ih-BULL-yunt&#92; <em>adjective</em></p>'
                          '<p><strong>WHAT IT MEANS</strong></p>'
                          '<p>Someone <em>ebullient</em> is full of lively enthusiasm.</p>'
                          '<p><strong>// EXAMPLES</strong></p><p>The ebullient crowd cheered.</p>')
        self.assertEqual(wotd, {'word': 'ebullient', 'part': 'adjective',
                                'meaning': 'Someone ebullient is full of lively enthusiasm.'})

    def test_a_colon_definition(self):
        wotd = self.parse('<p><strong>ebullient</strong> \\ih-BULL-yunt\\ <em>adjective</em></p>'
                          '<p>: full of lively enthusiasm</p>')
        self.assertEqual((wotd['part'], wotd['meaning']), ('adjective', 'full of lively enthusiasm'))

    def test_a_short_definition_wins(self):
        wotd = self.parse('<p>anything</p>', extra='<mw:shortdef>lively</mw:shortdef>')
        self.assertEqual(wotd['meaning'], 'lively')

    def test_pages(self):
        grid = Grid(4, 16)
        wotd = {'word': 'ebullient', 'part': 'adjective', 'meaning': 'full of lively enthusiasm'}
        with mock.patch.object(word_of_the_day, '_fetch', return_value=wotd):
            frames = word_of_the_day.WordOfTheDayApp().get_pages({}, {}, grid)
        self.assertEqual([_lines(grid, f.text) for f in frames], [
            ['WORD OF THE DAY ', '   EBULLIENT    ', '   ADJECTIVE    ', ' ' * 16],
            ['   EBULLIENT    ', ' FULL OF LIVELY ', '   ENTHUSIASM   ', ' ' * 16],
        ])


class OnThisDayTest(unittest.TestCase):
    EVENTS = [(1500, 'TOO OLD'), (1800, 'ON THE EDGE'), (1850, 'A'), (1962, 'B'), (2001, 'C'), (2015, 'EDGE'),
              (2020, 'TOO NEW')]

    def test_only_years_strictly_between(self):
        picked = on_this_day.pick_events(self.EVENTS, 1800, 2015, 10, seed='x')
        self.assertEqual([y for y, _ in picked], [1850, 1962, 2001])

    def test_the_same_pick_all_day_oldest_first(self):
        first = on_this_day.pick_events(self.EVENTS, 0, 3000, 3, seed='2026-10-11')
        self.assertEqual(first, on_this_day.pick_events(self.EVENTS, 0, 3000, 3, seed='2026-10-11'))
        self.assertEqual(first, sorted(first))
        self.assertEqual(len(first), 3)

    def test_bc_years(self):
        self.assertEqual(on_this_day.year_label(-44), '44 BC')

    def test_pages_from_the_feed(self):
        grid = Grid(3, 15)
        data = {'events': [{'year': 1962, 'text': 'The council opens.'}, {'year': 2020, 'text': 'Too new'}]}
        with mock.patch.object(requests, 'get', return_value=_response(data=data)) as get:
            frames = on_this_day.OnThisDayApp().get_pages({}, {}, grid)
        self.assertIn('/onthisday/events/', get.call_args[0][0])
        self.assertEqual(_lines(grid, frames[1].text), ['      1962     ', '  THE COUNCIL  ', '     OPENS.    '])
        self.assertEqual(len(frames), 2)

    def test_nothing_in_range_says_so(self):
        with mock.patch.object(requests, 'get', return_value=_response(data={'events': []})):
            frames = on_this_day.OnThisDayApp().get_pages({}, {}, Grid(3, 15))
        self.assertIn('NO EVENTS', frames[0].text)


if __name__ == '__main__':
    unittest.main()
