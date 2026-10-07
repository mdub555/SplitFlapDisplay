#!/usr/bin/env python3
"""
splitflap_test.py — Interactive RS-485 test tool for split-flap display modules.

Sends commands to one or more modules over a serial RS-485 bus and prints any
responses received.  All commands match the firmware v8 protocol (see
transceiver.h for the full reference):

  Actions
    m<ID>-<char>        Show a character               e.g. m38-B
    m<ID>+<index>       Show flap by index (0–63)      e.g. m38+7
    m<ID>h              Home the module
    m<ID>c              Calibrate (measure revolution)
    m<ID>n<n>           Nudge N steps (offset unchanged) e.g. m38n10
    m<ID>g<n>           Go to raw step position        e.g. m38g512
    m<ID>x              Stop the motor
    m<ID>e<n>           Exercise every flap, N laps    e.g. m38e1
    m<ID>b              Identify (blink LED for 10 s)
    m<ID>r              Reboot
    m*f<ms>:<pairs>     Frame broadcast (every module at once)

  Module
    m<ID>?              Dump state (reply: m<ID>?\\tO480\\tT4096...)
    m<ID>!              Reset all settings to defaults (keeps ID), reboot
    m<ID>@<n>           Set module ID                  e.g. m255@5

  Settings (saved to EEPROM)
    m<ID>O<n>  Home offset, steps (0 = make current position blank flap)
    m<ID>T<n>  Total steps per revolution
    m<ID>D<n>  Home sensor debounce, ms
    m<ID>E<b>  Recalculate home at every home edge (0/1)
    m<ID>A<b>  Auto-home on boot (0/1)
    m<ID>C<b>  Motor direction (1 = clockwise, 0 = counter-clockwise)
    m<ID>F<b>  Release motor coils when idle (0/1)
    m<ID>S<n>  Step delay, µs
    m<ID>H<n>  Homing/calibration step delay, µs
    m<ID>R<n>  Ramp start/end step delay, µs
    m<ID>L<n>  Ramp length, steps (0–255, 0 = no ramp)
    m<ID>W<n>  Settle time before releasing coils, ms (0–255)
    m<ID>P<n>  Power-on stagger, ms per module ID (0–255)

  Use * as ID to broadcast to all modules.

Usage:
  python3 splitflap_test.py [--port /dev/ttyUSB0] [--baud 9600]

Requirements:
  pip install pyserial
"""

import argparse
import sys
import threading
import time

try:
    import serial
except ImportError:
    print("ERROR: pyserial not installed.  Run:  pip install pyserial")
    sys.exit(1)

# ── ANSI colours (disabled automatically on Windows or when not a tty) ────────
USE_COLOUR = sys.stdout.isatty() and sys.platform != "win32"

def _c(code, text):
    return f"\033[{code}m{text}\033[0m" if USE_COLOUR else text

def green(t):  return _c("32", t)
def yellow(t): return _c("33", t)
def cyan(t):   return _c("36", t)
def red(t):    return _c("31", t)
def bold(t):   return _c("1",  t)
def dim(t):    return _c("2",  t)

# ── Character set (must match FLAP_CHARS in splitflap.cpp) ────────────────────
FLAP_CHARS = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789?!,.q:@#$&()+-*/=%dhwroygbp"
NUM_FLAPS = len(FLAP_CHARS)

# Flaps whose code on the wire isn't what the flap shows.
FLAP_NAMES = {
    " ": "blank", "q": '"', "d": "°", "h": "♥", "w": "white",
    "r": "red", "o": "orange", "y": "yellow", "g": "green",
    "b": "blue", "p": "purple",
}

MAX_FRAME_MODULES = 94  # ranks are sent as printable bytes '!' + rank

def flap_index(ch):
    """Return the index of a character in the flap set, or -1 if not present."""
    return FLAP_CHARS.find(ch)

def flap_char(index):
    """Return the character at a given flap index, or '?' if out of range."""
    if 0 <= index < NUM_FLAPS:
        return FLAP_CHARS[index]
    return "?"

def flap_label(ch):
    """A readable description of a flap code, e.g. 'q' -> 'q (")'."""
    name = FLAP_NAMES.get(ch)
    if ch == " ":
        return "' ' (blank)"
    return f"{ch} ({name})" if name else ch

# ── Dump reply decoding ────────────────────────────────────────────────────────

# Label -> (description, unit), in the order the firmware sends them.
DUMP_FIELDS = {
    "O": ("home offset",          "steps"),
    "T": ("total steps",          "steps"),
    "D": ("debounce",             "ms"),
    "S": ("step delay",           "µs"),
    "H": ("homing step delay",    "µs"),
    "C": ("clockwise",            ""),
    "A": ("auto-home",            ""),
    "F": ("release motor",        ""),
    "E": ("recalculate home",     ""),
    "R": ("ramp start delay",     "µs"),
    "L": ("ramp steps",           "steps"),
    "W": ("settle time",          "ms"),
    "P": ("power-on stagger",     "ms/ID"),
    "#": ("revolutions",          ""),
    "~": ("last drift",           "steps"),
}

def format_dump(line):
    """
    Pretty-print a dump reply ("m05?\\tO480\\tT4096..."), or return None if the
    line isn't one.
    """
    fields = line.split("\t")
    head = fields[0]
    if not (head.startswith("m") and head.endswith("?") and head[1:-1].isdigit()):
        return None
    out = [bold(f"Module {int(head[1:-1])} state:")]
    for field in fields[1:]:
        if not field:
            continue
        label, value = field[0], field[1:]
        desc, unit = DUMP_FIELDS.get(label, (f"unknown '{label}'", ""))
        out.append(f"      {label}  {desc:<20} {value} {unit}".rstrip())
    return "\n".join(out)

# ── Serial helpers ─────────────────────────────────────────────────────────────

def open_port(port, baud):
    """Open the serial port; exit with a clear message on failure."""
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,        # short read timeout for the listener thread
        )
        print(green(f"✓ Opened {port} at {baud} baud"))
        return ser
    except serial.SerialException as e:
        print(red(f"✗ Could not open {port}: {e}"))
        sys.exit(1)

def send(ser, message):
    """Send a message string (appends \\n if missing) and print what was sent."""
    if not message.endswith("\n"):
        message += "\n"
    ser.write(message.encode("ascii"))
    ser.flush()
    print(cyan(f"  → {repr(message.strip())}"))

# ── Background listener ────────────────────────────────────────────────────────

_listener_running = False

def start_listener(ser):
    """
    Spawn a daemon thread that prints any lines arriving from the bus.
    Modules only transmit in response to '?' (dump state); dump replies are
    decoded into one field per line.
    """
    global _listener_running
    _listener_running = True

    def _listen():
        buf = ""
        while _listener_running:
            try:
                raw = ser.read(64)
            except serial.SerialException:
                break
            if raw:
                buf += raw.decode("ascii", errors="replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        print(yellow(f"\n  ← {line!r}"))
                        pretty = format_dump(line)
                        if pretty:
                            print(yellow(f"    {pretty}"))
                        print(bold("command> "), end="", flush=True)

    t = threading.Thread(target=_listen, daemon=True)
    t.start()

def stop_listener():
    global _listener_running
    _listener_running = False

# ── Prompt helpers ─────────────────────────────────────────────────────────────

def build_message(module_id, cmd):
    """Prefix a command string with the module address."""
    return f"m{module_id}{cmd}"

def prompt_id():
    """Ask the user for a module ID (number, or * for broadcast)."""
    while True:
        raw = input(bold("  Module ID (number or * for broadcast): ")).strip()
        if raw in ("", "*", "**"):
            return "*"
        if raw.isdigit() and int(raw) <= 255:
            return f"{int(raw):02d}"
        print(red("  Enter a number 0–255 or *"))

def prompt_int(label, lo=None, hi=None):
    """Ask for an integer, optionally within a range.  Returns None on blank."""
    while True:
        raw = input(bold(f"  {label}: ")).strip()
        if raw == "":
            return None
        try:
            val = int(raw)
            if lo is not None and val < lo:
                print(red(f"  Must be ≥ {lo}"))
                continue
            if hi is not None and val > hi:
                print(red(f"  Must be ≤ {hi}"))
                continue
            return val
        except ValueError:
            print(red("  Not a valid integer — try again"))

def confirm(question):
    return input(bold(f"  {question} [y/N]: ")).strip().lower() == "y"

# ── Action handlers ────────────────────────────────────────────────────────────

def cmd_show_char(ser):
    """m<ID>-<char>  — display a character."""
    mid = prompt_id()
    print(dim('  (special flaps: q = ", d = °, h = ♥, r o y g b p w = colours)'))
    ch = input(bold("  Character to display: "))
    if len(ch) != 1:
        ch = ch.strip()
    if ch == '"':
        ch = "q"
    if len(ch) != 1:
        print(red("  Enter exactly one character"))
        return
    idx = flap_index(ch)
    if idx >= 0:
        print(dim(f"  (flap index {idx})"))
    else:
        print(red("  ⚠ character not on the reel — the module will ignore it"))
    send(ser, build_message(mid, f"-{ch}"))

def cmd_show_index(ser):
    """m<ID>+<n>  — display a flap by index."""
    mid = prompt_id()
    idx = prompt_int(f"Flap index (0–{NUM_FLAPS - 1})", 0, NUM_FLAPS - 1)
    if idx is None:
        return
    print(dim(f"  (flap at index {idx}: {flap_label(flap_char(idx))})"))
    send(ser, build_message(mid, f"+{idx}"))

def cmd_home(ser):
    """m<ID>h  — home the module."""
    mid = prompt_id()
    send(ser, build_message(mid, "h"))

def cmd_calibrate(ser):
    """m<ID>c  — measure revolution length, then dump to report the result."""
    mid = prompt_id()
    print(dim("  (module will spin to measure one revolution and save it as T)"))
    send(ser, build_message(mid, "c"))
    if confirm("Request a state dump (sent once calibration finishes)?"):
        send(ser, build_message(mid, "?"))
        print(dim("  The dump reply will appear when the module goes idle."))

def cmd_nudge(ser):
    """m<ID>n<n>  — nudge N steps forward (home offset unchanged)."""
    mid = prompt_id()
    val = prompt_int("Steps to nudge (less than total steps)", 0)
    if val is None:
        return
    send(ser, build_message(mid, f"n{val}"))
    print(dim("  (use 'Set home offset' with 0 to save this position as the blank flap)"))

def cmd_goto_step(ser):
    """m<ID>g<n>  — move to a raw step position."""
    mid = prompt_id()
    val = prompt_int("Target step position (less than total steps)", 0)
    if val is None:
        return
    print(dim("  (ignored until the module has been homed)"))
    send(ser, build_message(mid, f"g{val}"))

def cmd_stop(ser):
    """m<ID>x  — stop whatever the motor is doing."""
    mid = prompt_id()
    send(ser, build_message(mid, "x"))

def cmd_exercise(ser):
    """m<ID>e<n>  — step through every flap, N laps of the reel."""
    mid = prompt_id()
    val = prompt_int("Laps of the reel (1–255)", 1, 255)
    if val is None:
        return
    print(dim("  (any other motion command or Stop ends it)"))
    send(ser, build_message(mid, f"e{val}"))

def cmd_identify(ser):
    """m<ID>b  — blink the status LED quickly for 10 seconds."""
    mid = prompt_id()
    send(ser, build_message(mid, "b"))

def cmd_reboot(ser):
    """m<ID>r  — reboot the module."""
    mid = prompt_id()
    send(ser, build_message(mid, "r"))

def cmd_frame(ser):
    """m*f<interval>:<pairs>  — set every module at once."""
    print(dim(f"  Each character goes to module ID 0, 1, 2, … in order (up to {MAX_FRAME_MODULES})."))
    print(dim('  Special flaps: " (or q), d = °, h = ♥, r o y g b p w = colours.'))
    text = input(bold("  Text: ")).replace('"', "q")
    if not text:
        return
    if len(text) > MAX_FRAME_MODULES:
        print(red(f"  At most {MAX_FRAME_MODULES} characters"))
        return
    missing = sorted({ch for ch in text if flap_index(ch) < 0})
    if missing:
        print(red(f"  ⚠ not on the reel (modules will ignore them): {''.join(missing)!r}"))
    interval = prompt_int("Cascade interval per rank, ms (0–255, blank = 0)", 0, 255) or 0
    print(f"  Order:  {cyan('1')} left to right   {cyan('2')} right to left   "
          f"{cyan('3')} all at once")
    order = input(bold("  Order [1]: ")).strip() or "1"
    n = len(text)
    if order == "2":
        ranks = [n - 1 - i for i in range(n)]
    elif order == "3":
        ranks = [0] * n
    else:
        ranks = list(range(n))
    pairs = "".join(ch + chr(ord("!") + rank) for ch, rank in zip(text, ranks))
    send(ser, f"m*f{interval}:{pairs}")

# ── Module handlers ────────────────────────────────────────────────────────────

def cmd_dump(ser):
    """m<ID>?  — dump module state.  Reply decoded by the listener."""
    mid = prompt_id()
    if mid == "*":
        print(dim("  (each provisioned module replies in turn, ID × 105 ms apart)"))
    else:
        print(dim("  (a busy module replies once it finishes moving)"))
    send(ser, build_message(mid, "?"))
    time.sleep(0.5)

def cmd_set_id(ser):
    """m<ID>@<n>  — assign a new bus ID to a module."""
    print(yellow("  ⚠  This changes the module's address.  A broadcast (*) is only"))
    print(yellow("     accepted by unprovisioned modules (ID 255)."))
    mid = prompt_id()
    newid = prompt_int("New module ID (0–255, 255 = unprovisioned)", 0, 255)
    if newid is None:
        return
    send(ser, build_message(mid, f"@{newid}"))

def cmd_reset_settings(ser):
    """m<ID>!  — reset every setting to its default (keeps the ID), then reboot."""
    mid = prompt_id()
    if confirm(f"Reset ALL settings for module {mid} to defaults?"):
        send(ser, build_message(mid, "!"))
    else:
        print(dim("  Cancelled"))

# ── Settings ───────────────────────────────────────────────────────────────────

# (letter, menu label, prompt, lo, hi, note)
SETTINGS = [
    ("O", "Set home offset",              "Home offset in steps (0 = current position is blank)", 0, 65535,
     "Changing it marks the position unknown; the next move homes first."),
    ("T", "Set total steps/rev",          "Total steps per revolution", 1, 65535,
     "Stops any move and marks the position unknown."),
    ("D", "Set home sensor debounce",     "Debounce in ms (0–65535)", 0, 65535, None),
    ("E", "Set recalculate home on edge", "Recalculate home at every home edge? (1=yes, 0=no)", 0, 1, None),
    ("A", "Set auto-home on boot",        "Auto-home on boot? (1=yes, 0=no)", 0, 1, None),
    ("C", "Set motor direction",          "Direction (1=clockwise, 0=counter-clockwise)", 0, 1, None),
    ("F", "Set release motor when idle",  "Release coils when idle? (1=release, 0=keep energized)", 0, 1, None),
    ("S", "Set step delay",               "Step delay in µs (1–65535)", 1, 65535, None),
    ("H", "Set homing step delay",        "Homing/calibration step delay in µs (1–65535)", 1, 65535, None),
    ("R", "Set ramp start delay",         "Ramp start/end step delay in µs (1–65535)", 1, 65535,
     "Moves ramp between this and the step delay."),
    ("L", "Set ramp length",              "Ramp steps at each end of a move (0–255, 0 = no ramp)", 0, 255, None),
    ("W", "Set settle time",              "Hold coils after a move for N ms (0–255)", 0, 255,
     "Only used when release motor is on."),
    ("P", "Set power-on stagger",         "Auto-home stagger, ms per module ID (0–255)", 0, 255,
     "Takes effect on the next boot."),
]

def make_setting_handler(letter, prompt, lo, hi, note):
    def handler(ser):
        mid = prompt_id()
        val = prompt_int(prompt, lo, hi)
        if val is None:
            return
        if note:
            print(dim(f"  ({note})"))
        send(ser, build_message(mid, f"{letter}{val}"))
    handler.__doc__ = f"m<ID>{letter}<n>"
    return handler

# ── Utilities ──────────────────────────────────────────────────────────────────

def cmd_raw(ser):
    """Send a raw message string directly — useful for experimenting."""
    raw = input(bold("  Raw message (without leading 'm', e.g. '05-B'): ")).strip()
    if not raw:
        return
    send(ser, f"m{raw}")

def cmd_show_flap_table(_ser):
    """Print the full flap character table with indices."""
    print()
    print(bold("  Flap character table:"))
    print(dim("  idx  flap          idx  flap          idx  flap          idx  flap"))
    print(dim("  " + "─" * 68))
    for i in range(0, NUM_FLAPS, 4):
        row = ""
        for k in range(i, min(i + 4, NUM_FLAPS)):
            row += f"  {k:>3}  {flap_label(FLAP_CHARS[k]):<12}"
        print(row)
    print()

# ── Menu ───────────────────────────────────────────────────────────────────────

# Section headings are (title, None).
MENU = [
    ("Actions", None),
    ("Show character",               cmd_show_char),
    ("Show by flap index",           cmd_show_index),
    ("Home module",                  cmd_home),
    ("Calibrate revolution",         cmd_calibrate),
    ("Nudge steps",                  cmd_nudge),
    ("Go to raw step position",      cmd_goto_step),
    ("Stop motor",                   cmd_stop),
    ("Exercise (step every flap)",   cmd_exercise),
    ("Identify (blink LED)",         cmd_identify),
    ("Reboot module",                cmd_reboot),
    ("Frame broadcast (all modules)", cmd_frame),
    ("Module", None),
    ("Dump module state",            cmd_dump),
    ("Set module ID",                cmd_set_id),
    ("Reset settings to defaults",   cmd_reset_settings),
    ("Settings (saved to EEPROM)", None),
    *[(label, make_setting_handler(letter, prompt, lo, hi, note))
      for letter, label, prompt, lo, hi, note in SETTINGS],
    ("Utilities", None),
    ("Send raw message",             cmd_raw),
    ("Show flap character table",    cmd_show_flap_table),
]

# Just the selectable entries, numbered from 1.
COMMANDS = [(label, handler) for label, handler in MENU if handler]

def print_menu():
    print()
    print(bold("─── Split-Flap RS-485 Test Tool (firmware v8) ─────"))
    n = 0
    for label, handler in MENU:
        if handler is None:
            print(dim(f"  {label}"))
            continue
        n += 1
        print(f"  {cyan(str(n)):>4}  {label}")
    print(f"  {cyan('q'):>4}  Quit")
    print()

def run(ser):
    start_listener(ser)
    while True:
        print_menu()
        try:
            choice = input(bold("command> ")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if choice in ("q", "quit", "exit"):
            break

        try:
            idx = int(choice) - 1
        except ValueError:
            print(red("  Enter a menu number or 'q' to quit"))
            continue

        if not (0 <= idx < len(COMMANDS)):
            print(red(f"  Please enter a number between 1 and {len(COMMANDS)}"))
            continue

        label, handler = COMMANDS[idx]
        print(dim(f"\n  ── {label} ──"))
        try:
            handler(ser)
        except (KeyboardInterrupt, EOFError):
            print(dim("\n  (cancelled)"))

    stop_listener()
    ser.close()
    print(dim("Bye."))

# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Interactive RS-485 test tool for split-flap display modules (firmware v8)"
    )
    parser.add_argument(
        "--port", default="/dev/ttyUSB0",
        help="Serial port (default: /dev/ttyUSB0)"
    )
    parser.add_argument(
        "--baud", type=int, default=9600,
        help="Baud rate (default: 9600)"
    )
    args = parser.parse_args()

    ser = open_port(args.port, args.baud)
    run(ser)

if __name__ == "__main__":
    main()
