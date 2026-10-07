"""The firmware's bus protocol: every command letter, and how messages are built.

All command letters live here, so the rest of the frontend never spells one
out. Cmd mirrors COMMANDS in firmware/splitflapfirmwarev8/transceiver.cpp
(tests/test_module_protocol.py checks the two match); see transceiver.h for
the full message grammar.
"""

import re
from collections import namedtuple


class Cmd:
    """Firmware command letters, named as in the firmware's CommandType.
    Lowercase (and - +) are actions, punctuation is about the module
    itself, uppercase are saved settings."""
    # Actions
    DISPLAY_CHAR = '-'
    DISPLAY_INDEX = '+'
    HOME = 'h'
    CALIBRATE = 'c'
    NUDGE = 'n'
    MOVE_TO_STEP = 'g'
    STOP = 'x'
    EXERCISE = 'e'
    IDENTIFY = 'b'
    REBOOT = 'r'
    FRAME = 'f'
    # Module
    DUMP_STATE = '?'
    RESET_SETTINGS = '!'
    SET_MODULE_ID = '@'
    # Settings
    SET_OFFSET = 'O'
    SET_TOTAL_STEPS = 'T'
    SET_DEBOUNCE_MS = 'D'
    SET_RECALCULATE_HOME = 'E'
    SET_AUTO_HOME = 'A'
    SET_MOTOR_CW = 'C'
    SET_MOTOR_RELEASE = 'F'
    SET_STEP_DELAY = 'S'
    SET_HOMING_STEP_DELAY = 'H'
    SET_RAMP_START_DELAY = 'R'
    SET_RAMP_STEPS = 'L'
    SET_SETTLE_MS = 'W'
    SET_STAGGER_MS = 'P'


BROADCAST = '*'

# The ID of a module that hasn't been given one yet (UNPROVISIONED_ID in the
# firmware's eeprom_store.h).
UNPROVISIONED_ID = 255


# A frame broadcast (m*f<interval>:<pairs>) gives each module's place in the
# animation as one printable byte ('!' + rank), so it covers up to 94 modules.
FRAME_MAX_MODULES = 94


def message(mod_id, cmd: str, data='') -> str:
    """The bus message m<ID><cmd><data>, without the newline. `mod_id` is a
    module ID (sent as at least two digits) or BROADCAST."""
    target = mod_id if mod_id == BROADCAST else f"{mod_id:02d}"
    return f"m{target}{cmd}{data}"


# The dump reply (see Transceiver::dump() in the firmware): m<ID>? and then
# each field as a tab, a label and the value, e.g.
#   m05?\tO480\tT4096\tD100\tS1000\tH1000\tC1\tA1\tF1\tE1\tR3000\tL0\tW0\tP150\t#12\t~-3
# A setting is labelled with the letter that sets it; the two read-only
# fields have their own labels (REVOLUTIONS_CODE / DRIFT_CODE in the firmware).
DUMP_REVOLUTIONS = '#'
DUMP_DRIFT = '~'

# key: the settings key the value is stored under; kind: 'int' or 'bool';
# name and unit: how the Debug page describes it.
DumpField = namedtuple('DumpField', 'key kind name unit')

# Label -> field, in the order the firmware sends them.
DUMP_FIELDS = {
    Cmd.SET_OFFSET:            DumpField('homeOffset',        'int',  'home offset',       'steps'),
    Cmd.SET_TOTAL_STEPS:       DumpField('totalSteps',        'int',  'total steps',       'steps'),
    Cmd.SET_DEBOUNCE_MS:       DumpField('debounceMs',        'int',  'debounce',          'ms'),
    Cmd.SET_STEP_DELAY:        DumpField('stepDelayUs',       'int',  'step delay',        'µs'),
    Cmd.SET_HOMING_STEP_DELAY: DumpField('homingStepDelayUs', 'int',  'homing step delay', 'µs'),
    Cmd.SET_MOTOR_CW:          DumpField('motorClockwise',    'bool', 'clockwise',         ''),
    Cmd.SET_AUTO_HOME:         DumpField('autoHome',          'bool', 'auto-home',         ''),
    Cmd.SET_MOTOR_RELEASE:     DumpField('motorRelease',      'bool', 'release coils',     ''),
    Cmd.SET_RECALCULATE_HOME:  DumpField('recalculateHome',   'bool', 'recalculate home',  ''),
    Cmd.SET_RAMP_START_DELAY:  DumpField('rampStartDelayUs',  'int',  'ramp start delay',  'µs'),
    Cmd.SET_RAMP_STEPS:        DumpField('rampSteps',         'int',  'ramp length',       'steps'),
    Cmd.SET_SETTLE_MS:         DumpField('settleMs',          'int',  'settle',            'ms'),
    Cmd.SET_STAGGER_MS:        DumpField('staggerMs',         'int',  'stagger',           'ms'),
    DUMP_REVOLUTIONS:          DumpField('revolutions',       'int',  'revolutions',       ''),
    DUMP_DRIFT:                DumpField('drift',             'int',  'drift',             'steps'),
}


def dump_reply_pattern(id_pattern: str = r'\d+') -> str:
    """Regex for a complete dump reply line, with groups for the ID and the
    fields (each starting with its tab). `id_pattern` narrows the ID (a
    regex, default any)."""
    return rf'm({id_pattern}){re.escape(Cmd.DUMP_STATE)}((?:\t[^\t\r\n]*)+)\r?\n'


def parse_dump_fields(fields: str):
    """The settings dict for a dump reply's fields (the text after m<ID>?),
    or None if any field is malformed, unknown or repeated, or one is
    missing: the frontend and firmware are deployed together, so a reply
    that doesn't match exactly is a garbled one."""
    dump = {}
    for field in fields.split('\t')[1:]:
        spec = DUMP_FIELDS.get(field[:1])
        if spec is None or spec.key in dump or not re.fullmatch(r'-?\d+', field[1:]):
            return None
        value = int(field[1:])
        dump[spec.key] = bool(value) if spec.kind == 'bool' else value
    return dump if len(dump) == len(DUMP_FIELDS) else None


def dump_format():
    """The dump layout for the Debug page, which parses replies itself."""
    return {
        'marker': Cmd.DUMP_STATE,
        'fields': [dict(label=label, **spec._asdict()) for label, spec in DUMP_FIELDS.items()],
    }


# A module's on/off settings, shown as toggles in the inspector: the settings
# key (as stored under settings['modules'][id]) -> the command that sets it
# (m<ID><cmd><0|1>), and how the inspector describes it.
Toggle = namedtuple('Toggle', 'cmd label hint')

MODULE_TOGGLES = {
    'autoHome': Toggle(Cmd.SET_AUTO_HOME, 'Auto-home on boot',
                       'Find the home flap whenever this module powers up'),
    'motorClockwise': Toggle(Cmd.SET_MOTOR_CW, 'Motor clockwise',
                             'Off = counter-clockwise. Only change this if the reel turns the wrong way'),
    'motorRelease': Toggle(Cmd.SET_MOTOR_RELEASE, 'Release motor when idle',
                           'Cut coil power after each move so the motor runs cooler'),
}

TOGGLE_COMMANDS = {key: toggle.cmd for key, toggle in MODULE_TOGGLES.items()}


def toggle_command(mod_id: int, key: str, value: bool) -> str:
    """The bus message that sets boolean setting `key` on module `mod_id`."""
    return message(mod_id, TOGGLE_COMMANDS[key], int(value))


# Settings that are identical on every module. They live once in
# settings['firmware'] and are applied with a broadcast (m*<cmd><value>)
# rather than per module. Each has its command, accepted range and default,
# and how the settings form shows it (label, unit and hint).
# The step delays are in microseconds and stored by the firmware as a uint16,
# so 65535 is their ceiling; the ramp steps, settle time and stagger are stored
# as a uint8, so 255 is theirs.
GLOBAL_SETTINGS = {
    'stepDelayUs': {
        'cmd': Cmd.SET_STEP_DELAY, 'type': 'int', 'min': 1, 'max': 65535, 'default': 1000,
        'label': 'Step delay', 'unit': 'µs',
        'hint': 'Pause between motor steps during normal moves, in microseconds (1000 µs = 1 ms). '
                'Lower is faster; too low and the motor skips steps.'},
    'homingStepDelayUs': {
        'cmd': Cmd.SET_HOMING_STEP_DELAY, 'type': 'int', 'min': 1, 'max': 65535, 'default': 1000,
        'label': 'Homing step delay', 'unit': 'µs',
        'hint': 'Pause between steps while homing and calibrating, in microseconds.'},
    'debounceMs': {
        'cmd': Cmd.SET_DEBOUNCE_MS, 'type': 'int', 'min': 0, 'max': 65535, 'default': 50,
        'label': 'Home sensor debounce', 'unit': 'ms',
        'hint': 'Ignore repeat home-sensor triggers within this time. Raise it if home is detected '
                'more than once per rotation.'},
    'recalculateHome': {
        'cmd': Cmd.SET_RECALCULATE_HOME, 'type': 'bool', 'default': True,
        'label': 'Recalculate home each rotation',
        'hint': "On: every pass over the home sensor re-syncs the module's position. "
                'Off: position is only set while homing.'},
    'rampStartDelayUs': {
        'cmd': Cmd.SET_RAMP_START_DELAY, 'type': 'int', 'min': 1, 'max': 65535, 'default': 3000,
        'label': 'Ramp start delay', 'unit': 'µs',
        'hint': 'Step delay at the start and end of a move, in microseconds. Moves speed up from '
                'this to the step delay, and slow back down at the end.'},
    'rampSteps': {
        'cmd': Cmd.SET_RAMP_STEPS, 'type': 'int', 'min': 0, 'max': 255, 'default': 0,
        'label': 'Ramp length', 'unit': 'steps',
        'hint': 'Steps spent speeding up and slowing down at each end of a move. 0 turns the ramp off.'},
    'settleMs': {
        'cmd': Cmd.SET_SETTLE_MS, 'type': 'int', 'min': 0, 'max': 255, 'default': 0,
        'label': 'Settle time', 'unit': 'ms',
        'hint': 'Keep the coils powered this long after a move so the flap stops swinging. '
                'Only applies when the motor is released when idle.'},
    'staggerMs': {
        'cmd': Cmd.SET_STAGGER_MS, 'type': 'int', 'min': 0, 'max': 255, 'default': 150,
        'label': 'Startup stagger', 'unit': 'ms per module',
        'hint': "After power-on, each module waits this long times its ID before auto-homing, so "
                "the motors don't all start at once. Takes effect at the next power-on."},
}


# A broadcast dump (m*?) is answered by each provisioned module in turn, ID
# x DUMP_SLOT_S after the request (or after it finishes a move it was busy
# with). Matches DUMP_SLOT_MS in the firmware.
DUMP_SLOT_S = 0.105


def global_command(key: str, value) -> str:
    """The broadcast message that sets global setting `key` on every module."""
    return message(BROADCAST, GLOBAL_SETTINGS[key]['cmd'], int(value))
