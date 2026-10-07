import requests

from apps.base import App, SettingField
from apps.builtin._shared import cache_get_or_fetch, row_frames, split_list


def _fetch(teams):
    try:
        games = requests.get('https://api-web.nhle.com/v1/score/now', timeout=5).json().get('games', [])
        pages = []
        for g in games:
            away = g['awayTeam']['abbrev']
            home = g['homeTeam']['abbrev']
            if away in teams or home in teams:
                score = f"{away} {g['awayTeam'].get('score', 0)} {home} {g['homeTeam'].get('score', 0)}"
                gstate = g['gameState']
                if gstate in ('F', 'FINAL'):
                    clock = 'FINAL'
                elif gstate in ('LIVE', 'CRIT'):
                    clock = f"P{g['period']} {g['clock']['timeRemaining']}"
                else:
                    clock = 'SCHEDULED'
                pages.append(('NHL SCORE', score, clock))
        return pages or [('NHL SCORES', 'NO GAMES', 'TODAY')]
    except Exception:
        return [('SPORTS ERR', '', '')]


class SportsApp(App):
    key = 'sports'
    name = 'Sports'
    icon = '🏒'
    desc = 'NHL scores'
    settings_fields = [
        SettingField('nhl_teams', 'NHL Teams (comma-separated)', default='BOS,DAL', placeholder='BOS,DAL'),
    ]

    def get_pages(self, settings, cache):
        teams = split_list(self.setting(settings, 'nhl_teams'))
        return row_frames(cache_get_or_fetch(cache, 'sports', 60, lambda: _fetch(teams)), delay=5)
