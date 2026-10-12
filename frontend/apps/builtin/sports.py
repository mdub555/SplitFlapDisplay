import logging
import re
from datetime import datetime

import requests

from apps.base import App, SettingField
from apps.builtin._shared import cache_get_or_fetch, get_tz, plain_text, row_frames, split_list

# ESPN's scoreboard feed: the same shape for every league.
SCOREBOARD_URL = 'https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard'

# (label on the display, ESPN sport, ESPN league, the teams setting).
LEAGUES = [
    ('NHL', 'hockey', 'nhl', 'nhl_teams'),
    ('NBA', 'basketball', 'nba', 'nba_teams'),
    ('NFL', 'football', 'nfl', 'nfl_teams'),
    ('MLB', 'baseball', 'mlb', 'mlb_teams'),
]

# The soccer league setting's choices -> (label, ESPN league).
SOCCER_LEAGUES = {
    'Premier League': ('EPL', 'eng.1'),
    'MLS': ('MLS', 'usa.1'),
    'La Liga': ('LA LIGA', 'esp.1'),
    'Bundesliga': ('BUNDESLIGA', 'ger.1'),
    'Serie A': ('SERIE A', 'ita.1'),
    'Ligue 1': ('LIGUE 1', 'fra.1'),
    'Champions League': ('UCL', 'uefa.champions'),
}


def _wanted(team, picks):
    """Whether `team` (an ESPN team) is one of `picks`: an abbreviation or a
    name ("BOS", "Celtics", "Arsenal"), or ALL for every team."""
    if 'ALL' in picks:
        return True
    names = {str(team.get(k, '')).upper() for k in ('abbreviation', 'shortDisplayName', 'displayName', 'name')}
    return bool(names & picks)


def _status(sport, status, start, tz, now):
    """What the game's third row says: when it starts, how far in it is, or
    that it's over."""
    kind = status.get('type', {})
    state = kind.get('state')
    detail = plain_text(kind.get('shortDetail', ''))
    if state == 'pre':
        local = start.astimezone(tz)
        clock = local.strftime('%I:%M%p').lstrip('0')
        return clock if local.date() == now.date() else f"{local.strftime('%a').upper()} {clock}"
    if state == 'post':
        # "Final", "Final/OT", and soccer's "FT".
        return 'FINAL' if detail in ('FT', 'FULL TIME') else detail
    # Under way.
    period, clock = status.get('period', 0), status.get('displayClock', '')
    if kind.get('name') in ('STATUS_HALFTIME', 'STATUS_END_PERIOD') or sport == 'baseball' or not clock:
        return detail   # "HALFTIME", "END OF 2ND", "TOP 7TH"
    if sport == 'soccer':
        return f"{re.sub(r'[^0-9+]', '', clock)} MIN"   # 67' -> 67 MIN
    prefix = 'P' if sport == 'hockey' else 'Q'
    regulation = 3 if sport == 'hockey' else 4
    return f'{prefix}{period} {clock}' if period <= regulation else f'OT {clock}'


def _game_rows(label, sport, event, tz, now):
    """The rows for one game: the league, the teams and score, its status."""
    competition = (event.get('competitions') or [{}])[0]
    sides = {c.get('homeAway'): c for c in competition.get('competitors', [])}
    home, away = sides.get('home', {}), sides.get('away', {})
    abbrev = lambda side: plain_text(side.get('team', {}).get('abbreviation', '?'))  # noqa: E731
    status = event.get('status') or competition.get('status') or {}
    start = datetime.fromisoformat(event['date'].replace('Z', '+00:00'))
    started = status.get('type', {}).get('state') != 'pre'
    if sport == 'soccer':   # home team first, as soccer scores are given
        score = (f"{abbrev(home)} {home.get('score', 0)}-{away.get('score', 0)} {abbrev(away)}" if started
                 else f'{abbrev(home)} V {abbrev(away)}')
    else:
        score = (f"{abbrev(away)} {away.get('score', 0)} @ {abbrev(home)} {home.get('score', 0)}" if started
                 else f'{abbrev(away)} @ {abbrev(home)}')
    return start, (label, score, _status(sport, status, start, tz, now))


def _fetch(sport, league):
    """The league's games on ESPN's scoreboard now, or None if it couldn't be
    read."""
    try:
        res = requests.get(SCOREBOARD_URL.format(sport=sport, league=league), timeout=8)
        res.raise_for_status()
        return res.json().get('events', [])
    except Exception as e:
        logging.error(f'Sports fetch error ({league}): {e}')
        return None


class SportsApp(App):
    key = 'sports'
    name = 'Sports'
    icon = '🏒'
    desc = 'Live scores'
    order = 80
    settings_fields = [
        SettingField('nhl_teams', 'NHL teams', default='BOS,DAL', placeholder='BOS,DAL (ALL for every game)'),
        SettingField('nba_teams', 'NBA teams', placeholder='BOS,LAL (ALL for every game)'),
        SettingField('nfl_teams', 'NFL teams', placeholder='NE,KC (ALL for every game)'),
        SettingField('mlb_teams', 'MLB teams', placeholder='BOS,NYY (ALL for every game)'),
        SettingField('soccer_league', 'Soccer league', type='select', default='Premier League',
                     opts=list(SOCCER_LEAGUES)),
        SettingField('soccer_teams', 'Soccer teams', placeholder='ARS,Liverpool (ALL for every game)'),
    ]

    def _leagues(self, settings):
        """(label, sport, league, picked teams) for each league with teams set."""
        label, code = SOCCER_LEAGUES.get(self.setting(settings, 'soccer_league'), SOCCER_LEAGUES['Premier League'])
        leagues = [*LEAGUES, (label, 'soccer', code, 'soccer_teams')]
        picked = [(label, sport, league, {t.upper() for t in split_list(self.setting(settings, key))})
                  for label, sport, league, key in leagues]
        return [league for league in picked if league[3]]

    def get_items(self, settings, cache, grid):
        """A game each: the league's games in the order they start, league by
        league."""
        leagues = self._leagues(settings)
        if not leagues:
            return [row_frames(grid, [('SPORTS', 'NO TEAMS SET')], delay=5)]
        tz = get_tz(settings)
        now = datetime.now(tz)
        games, failed = [], 0
        for label, sport, league, picks in leagues:
            events = cache_get_or_fetch(cache, league, 60, lambda: _fetch(sport, league))
            if events is None:
                failed += 1
                continue
            wanted = [e for e in events if any(_wanted(c.get('team', {}), picks)
                                               for c in (e.get('competitions') or [{}])[0].get('competitors', []))]
            games += sorted(_game_rows(label, sport, e, tz, now) for e in wanted)
        if not games:
            return [row_frames(grid, [('SPORTS', 'FETCH ERROR' if failed == len(leagues) else 'NO GAMES TODAY')],
                               delay=5)]
        return [row_frames(grid, [rows], delay=5) for _, rows in games]
