import logging
import time

from config import NUM_MODULES, BAUD_RATE, FRAME_BROADCAST
from display.state import state
from display.charset import FLAP_CHARS, NUM_FLAPS, normalize_text
from display.layout import get_animation_order
from display.module_protocol import BROADCAST, FRAME_MAX_MODULES, Cmd, message
from display.serial_link import ser, serial_lock
from apps.base import Frame
from apps.registry import registry
from settings.store import settings


# Seconds for a module to turn one flap position (a revolution takes about 4 s).
SECONDS_PER_FLAP = 4.0 / NUM_FLAPS

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
        if ser:
            with serial_lock:
                ser.write(frame_message(clean_text, order, interval_ms).encode())
                ser.flush()
    else:
        cascade_s = 0  # sending one message at a time is the cascade
        with serial_lock:
            for i in order:
                if i >= len(clean_text):
                    continue
                if ser:
                    ser.write(f"{message(i, Cmd.DISPLAY_CHAR, clean_text[i])}\n".encode())
                    ser.flush()
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


def _manual_frames():
    """Wrap the frontend-pushed playlist (list of page dicts/strings) into
    Frame objects so it goes through the exact same loop as every app."""
    frames = []
    for page in state.current_playlist:
        if isinstance(page, dict):
            frames.append(Frame(
                text=page.get('text', ''),
                delay=float(page.get('delay', state.loop_delay)),
                style=page.get('style', Frame.style),
                speed=int(page.get('speed', Frame.speed)),
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
                busy_s = send_to_display(frame.text, order, raw=frame.raw, step_delay_ms=frame.speed)
                state.last_sent_page = frame.text
            else:
                busy_s = 0

            if not wait(busy_s, state.stop_event, poll=0.1):
                break
            if not wait(frame.delay if frame.delay is not None else 5, state.stop_event):
                break

        if state.stop_event.is_set():
            state.clear_stop()
