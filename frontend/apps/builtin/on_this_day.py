import logging
import random
from datetime import datetime

import requests

from apps.base import App, SettingField
from apps.builtin._shared import cache_get_or_fetch, get_tz, plain_text, row_frames, text_frames

# Wikipedia's "On this day" feed: what happened on a date, each with its year.
FEED_URL = 'https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/events/{month:02d}/{day:02d}'
# Wikimedia asks every client to say who it is.
USER_AGENT = 'SplitFlapDisplay/1.0 (https://github.com/mdub555/SplitFlapDisplay)'


def _fetch(month, day):
    """[(year, text)] for everything Wikipedia lists on that date, or None if
    it couldn't be read."""
    try:
        res = requests.get(FEED_URL.format(month=month, day=day), headers={'User-Agent': USER_AGENT}, timeout=10)
        res.raise_for_status()
        return [(int(e['year']), e['text']) for e in res.json().get('events', []) if 'year' in e and e.get('text')]
    except Exception as e:
        logging.error(f'On this day fetch error: {e}')
        return None


def pick_events(events, after, before, count, seed):
    """`count` of the events newer than `after` and older than `before`
    (years, both exclusive), picked at random but the same all day (`seed`),
    oldest first."""
    in_range = [e for e in events if after < e[0] < before]
    picked = random.Random(seed).sample(in_range, min(count, len(in_range)))
    return sorted(picked)


def year_label(year):
    return f'{-year} BC' if year < 0 else str(year)


def year_heading(grid, year):
    """The row above an event: ON THIS DAY 1962 when that fits across the
    display, otherwise === IN 1962 ===."""
    label = year_label(year)
    heading = f'ON THIS DAY {label}'
    return heading if len(heading) <= grid.cols else grid.banner(f'IN {label}')


class OnThisDayApp(App):
    key = 'on_this_day'
    name = 'On This Day'
    icon = '🏛️'
    desc = 'History today'
    order = 137
    settings_fields = [
        SettingField('on_this_day_after', 'Only events newer than (year)', type='number', default='1800',
                     placeholder='1800', step='1'),
        SettingField('on_this_day_before', 'Only events older than (year)', type='number', default='2015',
                     placeholder='2015', step='1'),
        SettingField('on_this_day_count', 'Events to show', type='number', default='5', placeholder='5',
                     min='1', max='20', step='1'),
    ]

    def _picked(self, settings, cache):
        """(today, the events to show), or (today, None) if they couldn't be
        fetched."""
        today = datetime.now(get_tz(settings)).date()
        events = cache_get_or_fetch(cache, f'events_{today:%m%d}', 6 * 3600,
                                    lambda: _fetch(today.month, today.day))
        if events is None:
            return today, None
        after = int(float(self.setting(settings, 'on_this_day_after')))
        before = int(float(self.setting(settings, 'on_this_day_before')))
        count = int(float(self.setting(settings, 'on_this_day_count')))
        return today, pick_events(events, after, before, count, seed=today.isoformat())

    def get_items(self, settings, cache, grid):
        """An event each: its pages, under its year."""
        _, picked = self._picked(settings, cache)
        if picked is None:
            return [row_frames(grid, [('ON THIS DAY', 'FETCH ERROR')], delay=5)]
        if not picked:
            after = int(float(self.setting(settings, 'on_this_day_after')))
            before = int(float(self.setting(settings, 'on_this_day_before')))
            return [row_frames(grid, [('ON THIS DAY', 'NO EVENTS', f'{after}-{before}')], delay=5)]
        return [text_frames(grid, plain_text(text), delay=5, heading=year_heading(grid, year))
                for year, text in picked]

    def get_pages(self, settings, cache, grid):
        """On its own: a title page with the date, then every event."""
        today, picked = self._picked(settings, cache)
        items = self.get_items(settings, cache, grid)
        if not picked:
            return items[0]
        title = row_frames(grid, [('ON THIS DAY', today.strftime('%B %d').upper().replace(' 0', ' '))], delay=4)
        return title + [frame for item in items for frame in item]
