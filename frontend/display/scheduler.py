"""The schedule: what the display shows at which times of the week.

The schedule lives in settings['schedule']:

    {
        'enabled': True,
        'default': 'app:time',          # outside every entry; '' leaves things be
        'entries': [
            {'days': [0, 1, 2, 3, 4],   # Monday is 0, as datetime.weekday()
             'start': '07:00', 'end': '09:30',
             'target': 'playlist:Morning'},
        ],
    }

A target is 'app:<key>', 'playlist:<saved playlist name>', or 'blank' to
clear the display and keep it clear (quiet hours, say). Entries are
checked in order and the first that covers the current time wins. An entry
whose end is before its start runs past midnight (into the next day), and
one whose start and end are equal runs all day.

The scheduler only acts when the target the schedule calls for changes, so
starting or stopping something by hand stays in effect until the schedule
next changes. It acts straight away when it's enabled or the schedule is
saved, and on startup.
"""
import logging
import re
import threading
from datetime import datetime, timedelta

DAYS = range(7)
BLANK = 'blank'   # the target that clears the display (DisplayState.run_blank)
_TIME = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')
_UNSET = object()   # the target before the first check, so that one always acts


def minutes(text):
    """'HH:MM' as minutes after midnight, or None if it isn't one."""
    match = _TIME.match(text) if isinstance(text, str) else None
    return int(match.group(1)) * 60 + int(match.group(2)) if match else None


def entry_covers(entry, now):
    """Whether `entry` covers the moment `now` (a datetime)."""
    start, end = minutes(entry['start']), minutes(entry['end'])
    days = entry['days']
    at = now.hour * 60 + now.minute
    today = now.weekday()
    if start == end:
        return today in days
    if start < end:
        return today in days and start <= at < end
    # Past midnight: from start to the end of its own day, then into the next.
    yesterday = (now - timedelta(days=1)).weekday()
    return (today in days and at >= start) or (yesterday in days and at < end)


def target_for(schedule, now):
    """The target the schedule calls for at `now`, or '' for none."""
    for entry in schedule.get('entries', []):
        if entry_covers(entry, now):
            return entry['target']
    return schedule.get('default', '')


def _valid_target(target, app_keys, allow_empty=False):
    if target == '' and allow_empty:
        return True
    if target == BLANK:
        return True
    if not isinstance(target, str):
        return False
    kind, _, key = target.partition(':')
    if kind == 'app':
        return key in app_keys
    return kind == 'playlist' and bool(key)


def validate(data, app_keys):
    """The schedule in `data` (as the page sends it), cleaned up, and None;
    or None and what's wrong with it."""
    if not isinstance(data, dict):
        return None, 'Schedule must be an object'
    default = data.get('default', '')
    if not _valid_target(default, app_keys, allow_empty=True):
        return None, f'Unknown default: {default}'
    entries = []
    for n, entry in enumerate(data.get('entries') or [], 1):
        if not isinstance(entry, dict):
            return None, f'Entry {n} must be an object'
        days = entry.get('days')
        if not isinstance(days, list) or not days or any(d not in DAYS or isinstance(d, bool) for d in days):
            return None, f'Entry {n} needs at least one day'
        if minutes(entry.get('start')) is None or minutes(entry.get('end')) is None:
            return None, f'Entry {n} needs a start and end time (HH:MM)'
        if not _valid_target(entry.get('target'), app_keys):
            return None, f'Entry {n} needs something to show'
        entries.append({'days': sorted(set(days)), 'start': entry['start'], 'end': entry['end'],
                        'target': entry['target']})
    return {'enabled': bool(data.get('enabled')), 'default': default, 'entries': entries}, None


class Scheduler:
    """Runs whatever the schedule calls for on `state` (a DisplayState).
    `settings` is the settings dict; `now()` gives the current local time;
    `app_exists(key)` says whether an app key is real."""

    def __init__(self, state, settings, now, app_exists):
        self.state = state
        self.settings = settings
        self.now = now
        self.app_exists = app_exists
        self._last = _UNSET
        self._wake = threading.Event()

    def check_soon(self):
        """Check the schedule now rather than at the next interval (say,
        because it was just saved)."""
        self._last = _UNSET
        self._wake.set()

    def tick(self):
        schedule = self.settings.get('schedule') or {}
        if not schedule.get('enabled'):
            if self._last is not _UNSET:
                self.state.set_scheduled_target(None)
            self._last = _UNSET
            return
        target = target_for(schedule, self.now())
        if target == self._last:
            return
        previous, self._last = self._last, target
        if target:
            self._run(target)
        else:
            # Out of every entry with no default: stop what the schedule
            # started, unless something else was started by hand since.
            if previous is not _UNSET and previous and self.state.current_target() == previous:
                self.state.stop()
            self.state.set_scheduled_target(None)

    def _run(self, target):
        if self.state.current_target() != target:
            kind, _, key = target.partition(':')
            if target == BLANK:
                self.state.run_blank()
            elif kind == 'app':
                if not self.app_exists(key):
                    logging.warning(f'Schedule: no app {key!r}')
                    return
                self.state.run_app(key)
            else:
                playlist = self.settings.get('saved_playlists', {}).get(key)
                if playlist is None:
                    logging.warning(f'Schedule: no saved playlist {key!r}')
                    return
                self.state.run_playlist(playlist.get('pages', []), playlist.get('delay'), key)
            logging.info(f'Schedule: started {target}')
        self.state.set_scheduled_target(target)

    def run_forever(self, interval=20):
        while True:
            try:
                self.tick()
            except Exception as e:
                logging.error(f'Schedule check failed: {e}')
            self._wake.wait(interval)
            self._wake.clear()


def local_now(settings):
    """The current time in the timezone from the global settings."""
    from apps.builtin._shared import get_tz
    try:
        return datetime.now(get_tz(settings))
    except Exception:
        return datetime.now()


_scheduler = None


def get_scheduler():
    """The one Scheduler, for the display's own state and settings. Built on
    first use so importing this module has no side effects."""
    global _scheduler
    if _scheduler is None:
        from apps.registry import registry
        from display.state import state
        from settings.store import settings
        _scheduler = Scheduler(state, settings, lambda: local_now(settings),
                               lambda key: registry.get(key) is not None)
    return _scheduler
