import logging
import time

from config import NUM_MODULES
from display.state import state
from display.charset import FLAP_CHARS, COLOR_MAP, QUOTE_CHAR, QUOTE_SUBSTITUTE
from display.layout import get_animation_order
from display.serial_link import ser, serial_lock
from apps.base import Frame
from apps.registry import registry
from settings.store import settings


def send_to_display(text, order=None, raw=False, step_delay_ms=15):
    """Push one frame of text to the physical modules in `order`, updating
    DisplayState to match. Returns the largest single-module travel
    distance (in flap positions) so the caller can wait out the physical
    rotation time before moving on."""
    if not text:
        return 0

    clean_text = text if raw else text.upper()
    for emoji, char in COLOR_MAP.items():
        clean_text = clean_text.replace(emoji, char)
    clean_text = clean_text.replace(QUOTE_CHAR, QUOTE_SUBSTITUTE)
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
    with serial_lock:
        for i in order:
            if i >= len(clean_text):
                continue
            char = clean_text[i]
            if ser:
                ser.write(f"m{i:02d}-{char}\n".encode())
                ser.flush()
                time.sleep(step_delay_ms / 1000.0)

            target_idx = FLAP_CHARS.find(char)
            if target_idx == -1:
                target_idx = 0
            dist = 128 if indices[i] == -1 else (target_idx - indices[i]) % 64
            max_dist = max(max_dist, dist)
            indices[i] = target_idx

    state.set_display(clean_text, indices)
    return max_dist


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


def _manual_frames():
    """Wrap the frontend-pushed playlist (list of page dicts/strings) into
    Frame objects so it goes through the exact same loop as every app."""
    frames = []
    for page in state.current_playlist:
        if isinstance(page, dict):
            frames.append(Frame(
                text=page.get('text', ''),
                delay=float(page.get('delay', state.loop_delay)),
                style=page.get('style', 'ltr'),
                speed=int(page.get('speed', 15)),
            ))
        else:
            frames.append(Frame(text=page, delay=state.loop_delay))
    return frames


def playlist_loop():
    cache = {}

    while True:
        app = registry.get(state.active_app) if state.active_app else None

        try:
            frames = app.get_pages(settings, cache) if app else _manual_frames()
        except Exception as e:
            logging.error(f"App '{state.active_app}' get_pages() failed: {e}")
            frames = []

        if not frames:
            time.sleep(1)
            continue

        for frame in frames:
            if state.stop_event.is_set():
                break

            order = get_animation_order(frame.style)
            if frame.raw or frame.text != state.last_sent_page:
                max_dist = send_to_display(frame.text, order, raw=frame.raw, step_delay_ms=frame.speed)
                state.last_sent_page = frame.text
            else:
                max_dist = 0

            if not wait(max_dist * (4.0 / 64.0), state.stop_event, poll=0.1):
                break
            if not wait(frame.delay if frame.delay is not None else 5, state.stop_event):
                break

        if state.stop_event.is_set():
            state.clear_stop()
