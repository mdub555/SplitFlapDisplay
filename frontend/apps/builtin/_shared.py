import logging
import random
import re
import time
import unicodedata

import pytz

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


# Punctuation the flaps don't have -> the nearest they do ('' drops it).
_PLAIN = str.maketrans({
    '\u2018': '', '\u2019': '', "'": '', '`': '',   # apostrophes: DONT reads better than DON T
    '\u201c': '"', '\u201d': '"',
    '\u2013': '-', '\u2014': '-', '\u2212': '-',
    ';': ',', '\u2026': '...',
})


def plain_text(text):
    """Free text (from a feed or an API) the way the flaps can show it:
    uppercase, accents dropped (É -> E), curly quotes and dashes swapped for
    ones the reels have, apostrophes dropped, and whitespace collapsed.
    Anything else with no flap still comes out blank."""
    text = unicodedata.normalize('NFKD', str(text))
    text = ''.join(c for c in text if not unicodedata.combining(c)).translate(_PLAIN)
    return re.sub(r'\s+', ' ', text).strip().upper()


def cache_get_or_fetch(cache, key, interval, fetch_fn):
    """Simple time-boxed cache: re-run fetch_fn only if `interval` seconds
    have passed since the last successful call for this key."""
    now = time.time()
    last = cache.get(f'{key}_ts', 0)
    if key not in cache or now - last > interval:
        cache[key] = fetch_fn()
        cache[f'{key}_ts'] = now
    return cache[key]


def row_frames(grid, pages, delay):
    """A centred frame for each page, where a page is a tuple of rows."""
    return [Frame(text=grid.page(*rows), delay=delay) for rows in pages]


def text_frames(grid, text, delay, heading=None):
    """`text` wrapped across as many pages as it takes. With a `heading`,
    it's on the top row of every page (even a last page with less text) and
    the text fills the rest."""
    body_rows = grid.rows - 1 if heading is not None and grid.rows > 1 else grid.rows
    lines = grid.wrap(text, max_lines=len(text) + 1)
    pages = [[heading, *chunk, *[''] * (body_rows - len(chunk))] if heading is not None and grid.rows > 1
             else chunk for chunk in grid.chunks(lines, body_rows)]
    return row_frames(grid, pages, delay)


def paired_frames(grid, pairs, delay):
    """For (first line, second line) pairs, such as a price and its change:
    a page of first lines, then the same items' second lines, an item a row,
    as many items to a page as the display has rows."""
    pages = []
    for chunk in grid.chunks(pairs):
        pages += [[first for first, _ in chunk], [second for _, second in chunk]]
    return row_frames(grid, pages, delay)


NOISE_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$&?%*-+'


def matrix_burst_frames(grid, reveal_page, reveal_style='center_out', noise_delay=0.6, reveal_delay=5):
    """Three frames of random noise (using different animation orders so the
    cascade reads as scrambling from multiple directions) followed by a
    clean reveal frame. Shared by the Matrix animation app and the Demo app."""
    def noise():
        return ''.join(random.choice(NOISE_CHARS) for _ in range(grid.size))
    return [
        Frame(text=noise(), delay=noise_delay, style='random', raw=True),
        Frame(text=noise(), delay=noise_delay, style='rain', raw=True),
        Frame(text=noise(), delay=noise_delay, style='spiral', raw=True),
        Frame(text=reveal_page, delay=reveal_delay, style=reveal_style),
    ]
