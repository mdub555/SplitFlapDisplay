import logging
import time

from config import GRID_COLS, GRID_ROWS, NUM_MODULES, BAUD_RATE, FRAME_BROADCAST
from display.state import state
from display.charset import FLAP_CHARS, NUM_FLAPS, SECONDS_PER_FLAP, normalize_text
from display.layout import get_animation_order
from display.module_protocol import BROADCAST, FRAME_MAX_MODULES, Cmd, message
from display.serial_link import serial_lock, write_serial
from apps.base import Frame, Grid
from apps.registry import registry
from settings.store import settings



def _bus_ms(num_bytes):
    """Time to send `num_bytes` at BAUD_RATE (8N1: 10 bits per byte)."""
    return num_bytes * 10 * 1000.0 / BAUD_RATE


def frame_message(text, order, interval_ms):
    """The frame broadcast for `text`: m*f<interval>:<pairs>, where pairs
    are each module's character and its rank in `order`, for modules 0, 1,
    2, ... in turn. A module starts moving rank x interval_ms after the
    frame ends. See transceiver.h in the firmware."""
    ranks = [0] * len(text)
    for rank, i in enumerate(order):
        if i < len(text):
            ranks[i] = rank
    pairs = ''.join(char + chr(ord('!') + rank) for char, rank in zip(text, ranks))
    return f"{message(BROADCAST, Cmd.FRAME, interval_ms)}:{pairs}\n"


def send_to_display(text, order=None, raw=False, step_delay_ms=15):
    """Push one frame of text to the physical modules, starting them in
    `order` `step_delay_ms` apart, and update DisplayState to match. Returns
    how many seconds until the last module has finished turning, so the
    caller can wait it out before moving on."""
    if not text:
        return 0

    clean_text = normalize_text(text, raw)
    # A character with no physical flap (e.g. ';' or "'" on the v8 reels) is
    # ignored by the module, leaving the old character up while our state
    # claimed otherwise. Send a blank instead so state and hardware agree.
    clean_text = ''.join(c if c in FLAP_CHARS else ' ' for c in clean_text)
    clean_text = clean_text.ljust(NUM_MODULES)[:NUM_MODULES]
    logging.info(f"DISPLAY: {clean_text}")

    if order is None:
        order = list(range(NUM_MODULES))

    with state.lock:
        indices = list(state.current_indices)

    max_dist = 0
    for i in order:
        if i >= len(clean_text):
            continue
        target_idx = FLAP_CHARS.index(clean_text[i])  # every character has a flap by now
        # A module whose position is unknown homes first: up to two revolutions.
        dist = 2 * NUM_FLAPS if indices[i] == -1 else (target_idx - indices[i]) % NUM_FLAPS
        max_dist = max(max_dist, dist)
        indices[i] = target_idx

    # One message per module took its send time plus step_delay_ms each, so
    # a frame keeps the same spacing between modules.
    interval_ms = round(step_delay_ms + _bus_ms(len(message(0, Cmd.DISPLAY_CHAR, 'A')) + 1))
    if FRAME_BROADCAST and NUM_MODULES <= FRAME_MAX_MODULES and interval_ms <= 255:
        # The modules cascade on their own; we only wait for the last one.
        cascade_s = (len(order) - 1) * interval_ms / 1000.0
        with serial_lock:
            write_serial(frame_message(clean_text, order, interval_ms))
    else:
        cascade_s = 0  # sending one message at a time is the cascade
        with serial_lock:
            for i in order:
                if i >= len(clean_text):
                    continue
                # No port (or it just went): don't wait out the bus for nothing.
                if write_serial(f"{message(i, Cmd.DISPLAY_CHAR, clean_text[i])}\n"):
                    time.sleep(step_delay_ms / 1000.0)

    state.set_display(clean_text, indices)
    return cascade_s + max_dist * SECONDS_PER_FLAP


def wait(seconds, stop_event, poll=0.1):
    """Interruptible sleep — bails early (returns False) if stop_event fires
    mid-wait. Every app used to hand-roll its own version of this; now it's
    shared since all apps go through the same frame loop."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        if stop_event.is_set():
            return False
        time.sleep(poll)
    return True


def _page_frame(page):
    """A frontend-pushed playlist page (a dict, or a plain string from an
    older saved playlist) as a Frame, so it goes through the same path as
    every app's."""
    if isinstance(page, dict):
        return Frame(
            text=page.get('text', ''),
            delay=float(page.get('delay', state.loop_delay)),
            style=page.get('style', Frame.style),
            speed=int(page.get('speed', Frame.speed)),
        )
    return Frame(text=page, delay=state.loop_delay)


def playlist_loop():
    """Plays whatever's active, for ever. Nothing that goes wrong while
    playing may end it (it would silently freeze the display until a
    restart), so an error is logged and the loop carries on."""
    while True:
        try:
            _play_once()
        except Exception:
            logging.exception('Playlist loop error; carrying on')
            time.sleep(1)


# The display's size, which every app is given.
GRID = Grid(GRID_ROWS, GRID_COLS)

# How long an app's error page stays up before it's asked for pages again.
APP_ERROR_DELAY = 10


def _app_frames(app):
    """The app's pages, or, if it fails, a page saying so (held a while, so a
    failing app isn't retried every second)."""
    try:
        return app.get_pages(settings, registry.cache_for(app.key), GRID)
    except Exception:
        logging.exception(f"App '{app.key}' get_pages() failed")
        return [Frame(text=GRID.page(app.name.upper(), 'APP ERROR'), delay=APP_ERROR_DELAY)]


# Which item each app shows next when a playlist reaches it, so each time
# round shows a different one (the next historical event, the next game).
# Kept for as long as the server runs.
_next_item = {}


def _app_items(app):
    """The app's items (see App.get_items), or, if it fails, an error page
    as its one item."""
    try:
        return [item for item in app.get_items(settings, registry.cache_for(app.key), GRID) if item]
    except Exception:
        logging.exception(f"App '{app.key}' get_items() failed")
        return [[Frame(text=GRID.page(app.name.upper(), 'APP ERROR'), delay=APP_ERROR_DELAY)]]


def _play_frames(frames):
    """Shows each frame and holds it for its delay. False if something else
    was started part-way (the stop event)."""
    for frame in frames:
        if state.stop_event.is_set():
            return False
        order = get_animation_order(frame.style)
        if frame.raw or frame.text != state.last_sent_page:
            busy_s = send_to_display(frame.text, order, raw=frame.raw, step_delay_ms=frame.speed)
            state.last_sent_page = frame.text
        else:
            busy_s = 0
        if not wait(busy_s, state.stop_event, poll=0.1):
            return False
        if not wait(frame.delay if frame.delay is not None else 5, state.stop_event):
            return False
    return True


def _play_app_step(app, min_seconds):
    """A playlist's app step: the app's next item, for at least
    `min_seconds`. An item that's over sooner (a clock's one page, held a
    second) is asked for again, so it stays up to date, until it's been up
    that long. False if something else was started part-way."""
    started = time.time()
    while True:
        items = _app_items(app)
        if not items:
            return wait(1, state.stop_event)
        n = _next_item.get(app.key, 0) % len(items)
        if not _play_frames(items[n]):
            return False
        if time.time() - started >= min_seconds:
            break
    _next_item[app.key] = n + 1
    return True


def _play_once():
    """One pass through the active app's pages, or the playlist's steps."""
    app = registry.get(state.active_app) if state.active_app else None
    if app:
        frames = _app_frames(app)
        if frames:
            _play_frames(frames)
        else:
            time.sleep(1)
    else:
        played = False
        for index, step in enumerate(list(state.current_playlist)):
            state.set_playlist_page(index)
            if isinstance(step, dict) and 'app' in step:
                step_app = registry.get(step['app'])
                if not step_app:
                    logging.warning(f"Playlist: no app {step['app']!r}")
                    continue
                ok = _play_app_step(step_app, float(step.get('delay') or state.loop_delay))
            else:
                ok = _play_frames([_page_frame(step)])
            played = True
            if not ok:
                break
        if not played:   # an empty playlist, or only apps that are gone
            time.sleep(1)

    if state.stop_event.is_set():
        state.clear_stop()
