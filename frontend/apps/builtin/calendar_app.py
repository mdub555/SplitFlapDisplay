import logging
from datetime import datetime, timedelta

import icalendar
import recurring_ical_events
import requests

from apps.base import App, Frame, SettingField
from apps.builtin._shared import cache_get_or_fetch, get_tz, plain_text


def _fetch(url, tz):
    """The events from now until the end of tomorrow in the calendar at
    `url` (an iCal feed), as (start, end, all_day, title), start and end in
    `tz`; or None if it couldn't be read. Repeating events come out as each
    time they happen."""
    try:
        # Apple and Outlook hand out webcal:// links; it's https underneath.
        res = requests.get(url.replace('webcal://', 'https://', 1), timeout=10)
        res.raise_for_status()
        cal = icalendar.Calendar.from_ical(res.content)
    except Exception as e:
        logging.error(f'Calendar fetch error: {e}')
        return None
    now = datetime.now(tz)
    until = tz.localize(datetime.combine(now.date() + timedelta(days=2), datetime.min.time()))
    events = []
    for ev in recurring_ical_events.of(cal).between(now - timedelta(days=1), until):
        start, end = ev.get('DTSTART').dt, ev.get('DTEND')
        end = end.dt if end else start
        all_day = not isinstance(start, datetime)
        if not all_day:
            # A time with no timezone ("floating") is local time.
            start = tz.localize(start) if start.tzinfo is None else start.astimezone(tz)
            end = tz.localize(end) if end.tzinfo is None else end.astimezone(tz)
        events.append((start, end, all_day, plain_text(ev.get('SUMMARY', '')) or 'BUSY'))
    return events


def todays_events(events, now, all_day=True):
    """The events still to come or under way today, all-day ones first."""
    today = now.date()
    timed = sorted((e for e in events if not e[2] and e[1] > now and e[0].date() <= today),
                   key=lambda e: e[0])
    whole_days = [e for e in events if e[2] and e[0] <= today < max(e[1], e[0] + timedelta(days=1))]
    return (whole_days if all_day else []) + timed


def short_time(start, now):
    """9:30A / 12:00P, or NOW for an event already under way."""
    if start <= now:
        return 'NOW'
    return start.strftime('%I:%M').lstrip('0') + ('A' if start.hour < 12 else 'P')


def event_rows(events, now, cols):
    """A row for each event, `cols` wide: an all-day event's title across the
    row, a timed one's time and title, the times right-aligned to the longest
    (so 9:30A sits under 12:00P) and the titles lined up after them."""
    times = [short_time(start, now) for start, _, all_day, _ in events if not all_day]
    width = max(map(len, times), default=0)
    rows = []
    for start, _, all_day, title in events:
        row = title if all_day else f'{short_time(start, now):>{width}} {title}'
        rows.append(row[:cols].ljust(cols))
    return rows


class CalendarApp(App):
    key = 'calendar'
    name = 'Calendar'
    icon = '🗓️'
    desc = "Today's events"
    order = 55
    settings_fields = [
        SettingField('calendar_ical_url', 'Calendar iCal address (Google: Settings → your calendar → '
                     'Integrate calendar → Secret address in iCal format)', type='password',
                     placeholder='https://calendar.google.com/calendar/ical/.../basic.ics'),
        SettingField('calendar_all_day', 'Show all-day events', type='checkbox', default=True),
    ]

    def get_pages(self, settings, cache, grid):
        url = self.setting(settings, 'calendar_ical_url').strip()
        if not url:
            return [Frame(text=grid.page('CALENDAR', 'NO ICAL ADDRESS'), delay=5)]
        tz = get_tz(settings)
        events = cache_get_or_fetch(cache, 'calendar', 300, lambda: _fetch(url, tz))
        if events is None:
            return [Frame(text=grid.page('CALENDAR', 'FETCH ERROR'), delay=5)]
        now = datetime.now(tz)
        events = todays_events(events, now, self.setting(settings, 'calendar_all_day') in (True, 'true'))
        if not events:
            return [Frame(text=grid.page('NO MORE EVENTS', 'TODAY'), delay=5)]
        return [Frame(text=''.join(event_rows(chunk, now, grid.cols)).ljust(grid.size), delay=5)
                for chunk in grid.chunks(events)]
