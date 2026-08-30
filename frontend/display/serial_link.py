import logging
import threading
import time

import serial

from config import SERIAL_PORT, BAUD_RATE

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
            time.sleep(0.02)


def read_dump(mod_id: int, timeout: float = 5.0):
    """m<ID>d — request and parse an EEPROM dump (home offset + total steps).
    Returns a dict or None on timeout/parse failure."""
    if not ser:
        return None
    with serial_lock:
        ser.reset_input_buffer()
        ser.write(f"m{mod_id:02d}d\n".encode())
        ser.flush()
        start = time.time()
        buffer = ""
        target = f"m{mod_id:02d}d:"
        while time.time() - start < timeout:
            if ser.in_waiting > 0:
                try:
                    chunk = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                    buffer += chunk
                    if target in buffer and '\n' in buffer[buffer.find(target):]:
                        valid_part = buffer[buffer.find(target):].split('\n')[0]
                        data = valid_part.split('d:', 1)[1]
                        parts = data.split(':')
                        if len(parts) >= 2:
                            return {'home_offset': int(parts[0]), 'total_steps': int(parts[1])}
                except Exception as e:
                    logging.error(f"Parse error reading module {mod_id} dump: {e}")
            time.sleep(0.05)
    return None


def calibrate_module(mod_id: int, timeout: float = 45.0):
    """m<ID>c — spin one revolution, parse the measured step count, and push
    it back as the module's new total-steps value. Returns the step count,
    or None on timeout."""
    if not ser:
        return None
    with serial_lock:
        ser.reset_input_buffer()
        ser.write(f"m{mod_id:02d}c\n".encode())
        ser.flush()
        start = time.time()
        buffer = ""
        target = f"m{mod_id:02d}:"
        while time.time() - start < timeout:
            if ser.in_waiting > 0:
                chunk = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                buffer += chunk
                if target in buffer and '\n' in buffer[buffer.find(target):]:
                    valid_part = buffer[buffer.find(target):].split('\n')[0]
                    try:
                        val = int(valid_part.split(target)[1])
                        ser.write(f"m{mod_id:02d}t{val}\n".encode())
                        ser.flush()
                        return val
                    except (ValueError, IndexError):
                        pass
            time.sleep(0.1)
    return None
