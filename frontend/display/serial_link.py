import logging
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
    # Sends: m<ID>d:<homeOffset>:<totalSteps>:<clockwise>:<autoHome>:<releaseMotor>
    if not ser:
        return None
    with serial_lock:
        ser.reset_input_buffer()
        ser.write(f"m{mod_id:02d}d\n".encode())
        ser.flush()
        state._broadcast_serial(f"SENT: m{mod_id:02d}d")
        start = time.time()
        buffer = ""
        target = f"m{mod_id:02d}d:"
        while time.time() - start < timeout:
            if ser.in_waiting > 0:
                try:
                    chunk = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                    buffer += chunk
                    if target in buffer and '\n' in buffer[buffer.find(target):]:
                        state._broadcast_serial(f"RECV: {buffer}")
                        return parse_buffer(buffer)
                except Exception as e:
                    state._broadcast_serial(f"MONITOR ERROR: {e}")
                    logging.error(f"Parse error reading module {mod_id} dump: {e}")
            time.sleep(0.05)
    return None


def parse_buffer(buffer):
    data = valid_part.split('\n')[0].split('d:', 1)[1]
    parts = data.split(':')
    if len(parts) >= 5:
        return {
            'home_offset': int(parts[0]),
            'total_steps': int(parts[1]),
            'clockwise': bool(parts[2]),
            'auto_home': bool(parts[3]),
            'release_motor': bool(parts[4])
        }


def calibrate_module(mod_id: int, timeout: float = 45.0):
    """m<ID>c — spin one revolution, parse the measured step count, and push
    it back as the module's new total-steps value. Returns the step count,
    or None on timeout."""
    send_raw(f"m{mod_id:02d}c\n")
    return read_dump(mod_id)['total_steps']
