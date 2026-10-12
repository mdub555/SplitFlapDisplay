"""Tests for the Sports app (apps/builtin/sports.py), with ESPN's
scoreboard feed faked.

Run from frontend/:   python -m unittest tests.test_sports
"""
import os
import sys
import unittest
from datetime import datetime
from unittest import mock

import pytz
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apps.base import Grid  # noqa: E402
from apps.builtin import sports  # noqa: E402

TZ = pytz.timezone('US/Eastern')
NOW = TZ.localize(datetime(2026, 10, 11, 20, 0))


def team(abbrev, name, short):
    return {'abbreviation': abbrev, 'displayName': name, 'shortDisplayName': short, 'name': short}


def event(date, away, home, state, away_score='0', home_score='0', name='STATUS_IN_PROGRESS', detail='',
          period=0, clock=''):
    return {
        'date': date,
        'status': {'period': period, 'displayClock': clock,
                   'type': {'state': state, 'name': name, 'shortDetail': detail}},
        'competitions': [{'competitors': [
            {'homeAway': 'home', 'team': home, 'score': home_score},
            {'homeAway': 'away', 'team': away, 'score': away_score},
        ]}],
    }


BOS = team('BOS', 'Boston Bruins', 'Bruins')
NYR = team('NYR', 'New York Rangers', 'Rangers')
DAL = team('DAL', 'Dallas Stars', 'Stars')
CHI = team('CHI', 'Chicago Blackhawks', 'Blackhawks')


class StatusTest(unittest.TestCase):
    def status(self, sport, **kw):
        ev = event('2026-10-11T23:00Z', BOS, NYR, **kw)
        return sports._game_rows('X', sport, ev, TZ, NOW)[1]

    def test_before_it_starts(self):
        self.assertEqual(self.status('hockey', state='pre'), ('X', 'BOS @ NYR', '7:00PM'))
        later = sports._game_rows('X', 'hockey', event('2026-10-13T00:30Z', BOS, NYR, state='pre'), TZ, NOW)[1]
        self.assertEqual(later[2], 'MON 8:30PM')

    def test_under_way(self):
        self.assertEqual(self.status('hockey', state='in', away_score='3', home_score='2', period=2, clock='12:34'),
                         ('X', 'BOS 3 @ NYR 2', 'P2 12:34'))
        self.assertEqual(self.status('basketball', state='in', period=3, clock='5:12')[2], 'Q3 5:12')
        self.assertEqual(self.status('football', state='in', period=5, clock='8:00')[2], 'OT 8:00')
        self.assertEqual(self.status('baseball', state='in', detail='Top 7th', period=7)[2], 'TOP 7TH')
        self.assertEqual(self.status('basketball', state='in', name='STATUS_HALFTIME', detail='Halftime',
                                     period=2, clock='0:00')[2], 'HALFTIME')

    def test_over(self):
        self.assertEqual(self.status('hockey', state='post', detail='Final/OT')[2], 'FINAL/OT')
        self.assertEqual(self.status('soccer', state='post', detail='FT')[2], 'FINAL')

    def test_soccer_puts_the_home_team_first(self):
        ars, che = team('ARS', 'Arsenal', 'Arsenal'), team('CHE', 'Chelsea', 'Chelsea')
        rows = sports._game_rows('EPL', 'soccer', event('2026-10-11T14:00Z', che, ars, state='in', away_score='1',
                                                         home_score='2', period=2, clock="67'"), TZ, NOW)[1]
        self.assertEqual(rows, ('EPL', 'ARS 2-1 CHE', '67 MIN'))


class PickingTest(unittest.TestCase):
    def test_teams_by_abbreviation_name_or_all(self):
        self.assertTrue(sports._wanted(BOS, {'BOS'}))
        self.assertTrue(sports._wanted(BOS, {'BRUINS'}))
        self.assertTrue(sports._wanted(BOS, {'BOSTON BRUINS'}))
        self.assertTrue(sports._wanted(BOS, {'ALL'}))
        self.assertFalse(sports._wanted(BOS, {'NYR'}))


class AppTest(unittest.TestCase):
    def fetch_from(self, feeds):
        def get(url, timeout):
            league = url.split('/')[-2]
            if league not in feeds:
                raise requests.ConnectionError('offline')
            res = mock.Mock()
            res.raise_for_status = lambda: None
            res.json = lambda: {'events': feeds[league]}
            return res
        return mock.patch.object(requests, 'get', side_effect=get)

    def lines(self, grid, frame):
        return [frame.text[i:i + grid.cols].strip() for i in range(0, grid.size, grid.cols)]

    def test_a_game_an_item_league_by_league_in_start_order(self):
        grid = Grid(4, 16)
        feeds = {
            'nhl': [event('2026-10-11T23:30Z', DAL, CHI, state='pre'),
                    event('2026-10-11T23:00Z', BOS, NYR, state='in', away_score='1', period=1, clock='4:00'),
                    event('2026-10-11T23:00Z', NYR, CHI, state='pre')],   # neither team picked
            'nba': [event('2026-10-11T23:00Z', team('LAL', 'Los Angeles Lakers', 'Lakers'),
                          team('BOS', 'Boston Celtics', 'Celtics'), state='post', away_score='99',
                          home_score='101', detail='Final')],
        }
        settings = {'timezone': 'US/Eastern', 'nhl_teams': 'BOS,DAL', 'nba_teams': 'Celtics'}
        with self.fetch_from(feeds):
            items = sports.SportsApp().get_items(settings, {}, grid)
        self.assertEqual([self.lines(grid, item[0])[:3] for item in items], [
            ['NHL', 'BOS 1 @ NYR 0', 'P1 4:00'],
            ['NHL', 'DAL @ CHI', mock.ANY],
            ['NBA', 'LAL 99 @ BOS 101', 'FINAL'],
        ])

    def test_nothing_set_nothing_on_and_a_failed_fetch(self):
        grid = Grid(3, 15)
        app = sports.SportsApp()
        self.assertIn('NO TEAMS SET', app.get_items({'nhl_teams': ''}, {}, grid)[0][0].text)
        with self.fetch_from({'nhl': []}):
            self.assertIn('NO GAMES TODAY', app.get_items({}, {}, grid)[0][0].text)
        with self.fetch_from({}):
            self.assertIn('FETCH ERROR', app.get_items({}, {}, grid)[0][0].text)

    def test_the_soccer_league_setting(self):
        with self.fetch_from({'usa.1': []}) as get:
            settings = {'nhl_teams': '', 'soccer_league': 'MLS', 'soccer_teams': 'ALL'}
            sports.SportsApp().get_items(settings, {}, Grid(3, 15))
        self.assertIn('/soccer/usa.1/scoreboard', get.call_args[0][0])


if __name__ == '__main__':
    unittest.main()
