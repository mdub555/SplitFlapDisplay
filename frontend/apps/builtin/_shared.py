import logging
import random
import time

import pytz

from config import GRID_ROWS, NUM_MODULES
from display.layout import format_lines
from apps.base import Frame


DEFAULT_TZ = 'US/Eastern'


def get_tz(settings):
    """The timezone from the global settings. One that isn't a real timezone
    (say, typed in before the setting was a list) falls back to the default,
    so the clocks keep working instead of every app failing."""
    name = settings.get('timezone') or DEFAULT_TZ
    try:
        return pytz.timezone(name)
    except pytz.UnknownTimeZoneError:
        logging.warning(f'Unknown timezone {name!r}; using {DEFAULT_TZ}')
        return pytz.timezone(DEFAULT_TZ)


def clock(dt, spaced=True):
    """The time as 9:05 PM (or 9:05PM, when not `spaced`)."""
    return dt.strftime('%I:%M %p' if spaced else '%I:%M%p').lstrip('0')


def split_list(text, limit=None):
    """The non-empty items of a comma-separated setting, at most `limit`."""
    items = [item.strip() for item in text.split(',') if item.strip()]
    return items[:limit]


def cache_get_or_fetch(cache, key, interval, fetch_fn):
    """Simple time-boxed cache: re-run fetch_fn only if `interval` seconds
    have passed since the last successful call for this key."""
    now = time.time()
    last = cache.get(f'{key}_ts', 0)
    if key not in cache or now - last > interval:
        cache[key] = fetch_fn()
        cache[f'{key}_ts'] = now
    return cache[key]


def center_page(*rows):
    """Vertically centers up to GRID_ROWS text rows (each horizontally
    centered within GRID_COLS via format_lines). This is what most
    data apps should use instead of hand-building a fixed 3-row string."""
    rows = list(rows)[:GRID_ROWS]
    total_pad = GRID_ROWS - len(rows)
    top = total_pad // 2
    bottom = total_pad - top
    return format_lines(*([''] * top + rows + [''] * bottom))


def row_frames(pages, delay):
    """A centered frame for each page, where a page is a tuple of rows."""
    return [Frame(text=center_page(*rows), delay=delay) for rows in pages]


NOISE_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$&?%*-+'


def matrix_burst_frames(reveal_page, reveal_style='center_out', noise_delay=0.6, reveal_delay=5):
    """Three frames of random noise (using different animation orders so the
    cascade reads as scrambling from multiple directions) followed by a
    clean reveal frame. Shared by the Matrix animation app and the Demo app."""
    def noise():
        return ''.join(random.choice(NOISE_CHARS) for _ in range(NUM_MODULES))
    return [
        Frame(text=noise(), delay=noise_delay, style='random', raw=True),
        Frame(text=noise(), delay=noise_delay, style='rain', raw=True),
        Frame(text=noise(), delay=noise_delay, style='spiral', raw=True),
        Frame(text=reveal_page, delay=reveal_delay, style=reveal_style),
    ]
