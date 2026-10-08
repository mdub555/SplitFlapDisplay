import logging
import re
import threading
import time

import serial

from config import SERIAL_PORT, BAUD_RATE
from display.module_protocol import (
    BROADCAST, DUMP_SLOT_S, Cmd, dump_reply_pattern, message, parse_dump_fields)
from display.state import state

serial_lock = threading.Lock()

# The open port, or None when there isn't one (simulation mode). It can come
# and go while the app runs: a failed write or read drops it (the USB adapter
# was unplugged, say), and keep_connected() opens it again once it's back.
# Always use it through this module, never a copy of it taken at import.
ser = None

# Errors that mean the port has gone, rather than a bad message.
PORT_ERRORS = (serial.SerialException, OSError)


def _open():
    """Tries to open the port. Call with serial_lock held."""
    global ser
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.5)
    except Exception as e:
        ser = None
        return e
    logging.info(f"Serial connected on {SERIAL_PORT}")
    state.log_serial(f"SERIAL CONNECTED: {SERIAL_PORT}")
    # Whatever was sent while the port was gone never arrived: resend the page.
    state.last_sent_page = None
    state.set_hardware_connected(True)
    return None


def _lost(error):
    """The port stopped working: let it go until it can be opened again.
    Call with serial_lock held."""
    global ser
    try:
        ser.close()
    except Exception:
        pass
    ser = None
    logging.error(f"Serial port lost: {error}. Retrying in the background.")
    state.log_serial(f"SERIAL LOST: {error}")
    state.set_hardware_connected(False)


_startup_error = _open()
if _startup_error:
    logging.error(f"Serial failed. Simulation Mode until it opens. Reason: {_startup_error}")


def is_connected() -> bool:
    return ser is not None


def write_serial(data: str) -> bool:
    """Writes `data` to the bus, if there's a port, and logs it to the
    Debug page's serial log either way (as SENT, SIMULATED SENT or NOT
    SENT), so every message shows there however it was sent. Call with
    serial_lock held. False if there's no port, or the write failed (and the
    port is now treated as gone), so the caller can skip waiting for the bus."""
    shown = data.strip()
    if ser is None:
        state.log_serial(f"SIMULATED SENT: {shown}")
        return False
    try:
        ser.write(data.encode())
        ser.flush()
    except PORT_ERRORS as e:
        _lost(e)
        state.log_serial(f"NOT SENT (serial lost): {shown}")
        return False
    state.log_serial(f"SENT: {shown}")
    return True


def keep_connected(interval=5.0):
    """Runs for ever (in its own thread, see app.py): reopens the port when
    it's missing, and notices when an open port has gone, even while nothing
    is being sent, so the page shows it."""
    while True:
        time.sleep(interval)
        with serial_lock:
            if ser is None:
                _open()
                continue
            try:
                ser.in_waiting   # raises once the device has gone away
            except PORT_ERRORS as e:
                _lost(e)


def send_raw(cmd: str):
    """Fire-and-forget a command string to the bus."""
    if not cmd.endswith('\n'):
        cmd += '\n'
    with serial_lock:
        if write_serial(cmd):   # which logs it
            time.sleep(0.02)


def read_dump(mod_id: int, timeout: float = 5.0):
    """m<ID>? — request and parse a module's dump (its settings, revolution
    count and drift; see DUMP_FIELDS in module_protocol). Returns a dict or
    None on timeout/parse failure, or if the port is missing or goes."""
    with serial_lock:
        if ser is None:
            return None
        try:
            ser.reset_input_buffer()
            request = message(mod_id, Cmd.DUMP_STATE)
            ser.write(f"{request}\n".encode())
            ser.flush()
            state.log_serial(f"SENT: {request}")
            start = time.time()
            buffer = ""
            while time.time() - start < timeout:
                if ser.in_waiting > 0:
                    chunk = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                    buffer += chunk
                    try:
                        dump = parse_buffer(buffer, mod_id)
                    except Exception as e:
                        state.log_serial(f"MONITOR ERROR: {e}")
                        logging.error(f"Parse error reading module {mod_id} dump: {e}")
                        dump = None
                    if dump is not None:
                        state.log_serial(f"RECV: {buffer}")
                        return dump
                time.sleep(0.05)
        except PORT_ERRORS as e:
            _lost(e)
    return None


def read_all_dumps(max_id: int, margin: float = 0.5, on_reply=None):
    """m*? — ask every module for its dump at once. Each provisioned module
    answers in its own slot (ID x DUMP_SLOT_S after the request), so this
    listens until module `max_id`'s slot has passed, plus `margin`. Returns
    {mod_id: dump} for every reply received; modules that were busy (they
    answer after finishing) or didn't answer are missing. `on_reply(mod_id,
    dump)`, if given, is called for each reply as soon as it arrives. If the
    port goes part-way through, the replies so far are returned."""
    buffer = ""
    with serial_lock:
        if ser is None:
            return {}
        try:
            ser.reset_input_buffer()
            request = message(BROADCAST, Cmd.DUMP_STATE)
            ser.write(f"{request}\n".encode())
            ser.flush()
            state.log_serial(f"SENT: {request}")
            deadline = time.time() + (max_id + 1) * DUMP_SLOT_S + margin
            reported = set()
            while time.time() < deadline:
                if ser.in_waiting > 0:
                    buffer += ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                    if on_reply:
                        for mod_id, dump in parse_all_dumps(buffer).items():
                            if mod_id not in reported:
                                reported.add(mod_id)
                                on_reply(mod_id, dump)
                time.sleep(0.02)
        except PORT_ERRORS as e:
            _lost(e)
    if buffer:
        state.log_serial(f"RECV: {buffer}")
    return parse_all_dumps(buffer)


def parse_buffer(buffer, mod_id=None):
    """Find a complete dump reply line (m<ID>? and its tab-separated fields)
    anywhere in `buffer` and parse it. Pass `mod_id` to only accept that
    module's reply (any ID matches when omitted). Only newline-terminated lines
    count, so a half-received reply is ignored until the rest arrives; the
    firmware ends lines with \\r\\n (Serial.println), which is stripped here.
    Returns None when no complete, well-formed dump line is present."""
    id_pattern = r'\d+' if mod_id is None else f'{mod_id:02d}'
    for match in re.finditer(dump_reply_pattern(id_pattern), buffer):
        dump = parse_dump_fields(match.group(2))
        if dump is not None:
            return dump
    return None


def parse_all_dumps(buffer):
    """Every complete, well-formed dump line in `buffer`, as {mod_id: dump}."""
    dumps = {}
    for match in re.finditer(dump_reply_pattern(), buffer):
        dump = parse_dump_fields(match.group(2))
        if dump is not None:
            dumps[int(match.group(1))] = dump
    return dumps


def calibrate_module(mod_id: int, timeout: float = 45.0):
    """m<ID>c — spin one revolution, parse the measured step count, and push
    it back as the module's new total-steps value. Returns the step count,
    or None on timeout."""
    send_raw(message(mod_id, Cmd.CALIBRATE))
    dump = read_dump(mod_id, timeout)
    if dump is None:
        return None
    return dump['totalSteps']
