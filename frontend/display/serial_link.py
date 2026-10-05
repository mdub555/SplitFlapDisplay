import logging
import re
import threading
import time

import serial

from config import SERIAL_PORT, BAUD_RATE
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
    """m<ID>d — request and parse an EEPROM dump (home offset + total steps).
    Returns a dict or None on timeout/parse failure."""
    # Sends: m<ID>d:<homeOffset>:<totalSteps>:<debounceMs>:<stepDelay>:<homingStepDelay>
    #              :<clockwise>:<autoHome>:<releaseMotor>:<recalculateHome>
    if not ser:
        return None
    with serial_lock:
        ser.reset_input_buffer()
        ser.write(f"m{mod_id:02d}d\n".encode())
        ser.flush()
        state._broadcast_serial(f"SENT: m{mod_id:02d}d")
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
            'stepDelay': int(parts[3]),
            'homingStepDelay': int(parts[4]),
            'motorClockwise': parts[5] == '1',
            'autoHome': parts[6] == '1',
            'motorRelease': parts[7] == '1',
            'recalculateHome': parts[8] == '1',
        }
    except ValueError:
        return None


def parse_buffer(buffer, mod_id=None):
    """Find a complete `m<ID>d:<homeOffset>:<totalSteps>:<debounceMs>:<stepDelay>:
    <homingStepDelay>:<clockwise>:<autoHome>:<releaseMotor>:<recalculateHome>`
    line anywhere in `buffer` and parse it. Pass `mod_id` to only accept that
    module's reply (any ID matches when omitted). Only newline-terminated lines
    count, so a half-received reply is ignored until the rest arrives; the
    firmware ends lines with \\r\\n (Serial.println), which is stripped here.
    Returns None when no complete, well-formed dump line is present."""
    id_pattern = r'\d+' if mod_id is None else f'{mod_id:02d}'
    for match in re.finditer(rf'm{id_pattern}d:([^\r\n]*)\r?\n', buffer):
        dump = _parse_dump_fields(match.group(1))
        if dump is not None:
            return dump
    return None


def calibrate_module(mod_id: int, timeout: float = 45.0):
    """m<ID>c — spin one revolution, parse the measured step count, and push
    it back as the module's new total-steps value. Returns the step count,
    or None on timeout."""
    send_raw(f"m{mod_id:02d}c\n")
    dump = read_dump(mod_id, timeout)
    if dump is None:
        return None
    return dump['totalSteps']
