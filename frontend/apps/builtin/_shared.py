import random
import time

import pytz

from config import GRID_ROWS, NUM_MODULES
from display.layout import format_lines
from apps.base import Frame


def get_tz(settings):
    return pytz.timezone(settings.get('timezone', 'US/Eastern'))


def cache_get_or_fetch(cache, key, interval, fetch_fn):
    """Simple time-boxed cache: re-run fetch_fn only if `interval` seconds
    have passed since the last successful call for this key."""
    now = time.time()
    last = cache.get(f'{key}_ts', 0)
    if key not in cache or now - last > interval:
        cache[key] = fetch_fn()
        cache[f'{key}_ts'] = now
    return cache[key]


def pad(text, center=False):
    return (text.center(NUM_MODULES) if center else text.ljust(NUM_MODULES))[:NUM_MODULES]


def center_page(*rows):
    """Vertically centers up to GRID_ROWS text rows (each horizontally
    centered within GRID_COLS via format_lines). This is what most
    data apps should use instead of hand-building a fixed 3-row string."""
    rows = list(rows)[:GRID_ROWS]
    total_pad = GRID_ROWS - len(rows)
    top = total_pad // 2
    bottom = total_pad - top
    return format_lines(*([''] * top + rows + [''] * bottom))


def matrix_burst_frames(reveal_page, reveal_style='center_out'):
    """Three frames of random noise (using different animation orders so the
    cascade reads as scrambling from multiple directions) followed by a
    clean reveal frame. Shared by the Matrix animation app and the Demo app."""
    chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$&?%*'
    noise = lambda: ''.join(random.choice(chars) for _ in range(NUM_MODULES))
    return [
        Frame(text=noise(), delay=0.6, style='random', raw=True),
        Frame(text=noise(), delay=0.6, style='rain', raw=True),
        Frame(text=noise(), delay=0.6, style='spiral', raw=True),
        Frame(text=reveal_page, delay=5, style=reveal_style),
    ]
