import logging
import re
import threading
import time

import serial

from config import SERIAL_PORT, BAUD_RATE
from display.module_protocol import DUMP_SLOT_S
from display.state import state

serial_lock = threading.Lock()

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.5)
    logging.info(f"Serial connected on {SERIAL_PORT}")
except Exception as e:
    ser = None
    logging.error(f"Serial failed. Simulation Mode. Reason: {e}")


def is_connected() -> bool:
    return ser is not None


def send_raw(cmd: str):
    """Fire-and-forget a command string to the bus."""
    if not cmd.endswith('\n'):
        cmd += '\n'
    with serial_lock:
        if ser:
            ser.write(cmd.encode())
            ser.flush()
            state._broadcast_serial(f"SENT: {cmd.strip()}")
            time.sleep(0.02)
        else:
            state._broadcast_serial(f"SIMULATED SENT: {cmd.strip()}")


def read_dump(mod_id: int, timeout: float = 5.0):
    """m<ID>? — request and parse an EEPROM dump (home offset + total steps).
    Returns a dict or None on timeout/parse failure."""
    # Sends: m<ID>?:<homeOffset>:<totalSteps>:<debounceMs>:<stepDelayUs>:<homingStepDelayUs>
    #              :<clockwise>:<autoHome>:<releaseMotor>:<recalculateHome>
    #              [:<rampStartDelayUs>:<rampSteps>:<settleMs>:<staggerMs>[:<revolutions>]:<drift>]
    if not ser:
        return None
    with serial_lock:
        ser.reset_input_buffer()
        ser.write(f"m{mod_id:02d}?\n".encode())
        ser.flush()
        state._broadcast_serial(f"SENT: m{mod_id:02d}?")
        start = time.time()
        buffer = ""
        while time.time() - start < timeout:
            if ser.in_waiting > 0:
                try:
                    chunk = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                    buffer += chunk
                    dump = parse_buffer(buffer, mod_id)
                    if dump is not None:
                        state._broadcast_serial(f"RECV: {buffer}")
                        return dump
                except Exception as e:
                    state._broadcast_serial(f"MONITOR ERROR: {e}")
                    logging.error(f"Parse error reading module {mod_id} dump: {e}")
            time.sleep(0.05)
    return None


def read_all_dumps(max_id: int, margin: float = 0.5):
    """m*? — ask every module for its dump at once. Each provisioned module
    answers in its own slot (ID x DUMP_SLOT_S after the request), so this
    listens until module `max_id`'s slot has passed, plus `margin`. Returns
    {mod_id: dump} for every reply received; modules that were busy (they
    answer after finishing) or didn't answer are missing."""
    if not ser:
        return {}
    with serial_lock:
        ser.reset_input_buffer()
        ser.write(b"m*?\n")
        ser.flush()
        state._broadcast_serial("SENT: m*?")
        deadline = time.time() + (max_id + 1) * DUMP_SLOT_S + margin
        buffer = ""
        while time.time() < deadline:
            if ser.in_waiting > 0:
                buffer += ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
            time.sleep(0.02)
    if buffer:
        state._broadcast_serial(f"RECV: {buffer}")
    return parse_all_dumps(buffer)


# Fields newer firmware sends after the first nine, in this order, followed
# by drift (steps the tracked position was off by at the last home edge;
# positive = missed steps), which is always last. Each firmware version adds
# fields before drift, so a dump has the first N of these plus drift.
# Firmware from before any of them sends only the first nine fields.
# The step delays (stepDelayUs, homingStepDelayUs, rampStartDelayUs) are in
# microseconds; firmware from before EEPROM layout 0x07 reported them in ms.
_EXTENDED_FIELDS = ('rampStartDelayUs', 'rampSteps', 'settleMs', 'staggerMs', 'revolutions')
_MIN_EXTENDED = 4  # the ramp, settle and stagger settings came together


def _parse_extended_fields(parts):
    extra = parts[9:]
    if len(extra) < _MIN_EXTENDED + 1:
        return {}
    fields = {key: int(value) for key, value in zip(_EXTENDED_FIELDS, extra[:-1])}
    fields['drift'] = int(extra[-1])
    return fields


def _parse_dump_fields(text):
    parts = [p.strip() for p in text.split(':')]
    if len(parts) < 9:
        return None
    try:
        # Same key names the rest of the app (settings.json, tuning.js,
        # backup/restore, module routes) uses for a module's config.
        return {
            'homeOffset': int(parts[0]),
            'totalSteps': int(parts[1]),
            'debounceMs': int(parts[2]),
            'stepDelayUs': int(parts[3]),
            'homingStepDelayUs': int(parts[4]),
            'motorClockwise': parts[5] == '1',
            'autoHome': parts[6] == '1',
            'motorRelease': parts[7] == '1',
            'recalculateHome': parts[8] == '1',
            **_parse_extended_fields(parts),
        }
    except ValueError:
        return None


def parse_buffer(buffer, mod_id=None):
    """Find a complete `m<ID>?:<homeOffset>:<totalSteps>:<debounceMs>:<stepDelayUs>:
    <homingStepDelayUs>:<clockwise>:<autoHome>:<releaseMotor>:<recalculateHome>`
    line anywhere in `buffer` and parse it. Pass `mod_id` to only accept that
    module's reply (any ID matches when omitted). Only newline-terminated lines
    count, so a half-received reply is ignored until the rest arrives; the
    firmware ends lines with \\r\\n (Serial.println), which is stripped here.
    Returns None when no complete, well-formed dump line is present."""
    id_pattern = r'\d+' if mod_id is None else f'{mod_id:02d}'
    for match in re.finditer(rf'm{id_pattern}\?:([^\r\n]*)\r?\n', buffer):
        dump = _parse_dump_fields(match.group(1))
        if dump is not None:
            return dump
    return None


def parse_all_dumps(buffer):
    """Every complete, well-formed dump line in `buffer`, as {mod_id: dump}."""
    dumps = {}
    for match in re.finditer(r'm(\d+)\?:([^\r\n]*)\r?\n', buffer):
        dump = _parse_dump_fields(match.group(2))
        if dump is not None:
            dumps[int(match.group(1))] = dump
    return dumps


def calibrate_module(mod_id: int, timeout: float = 45.0):
    """m<ID>c — spin one revolution, parse the measured step count, and push
    it back as the module's new total-steps value. Returns the step count,
    or None on timeout."""
    send_raw(f"m{mod_id:02d}c\n")
    dump = read_dump(mod_id, timeout)
    if dump is None:
        return None
    return dump['totalSteps']
