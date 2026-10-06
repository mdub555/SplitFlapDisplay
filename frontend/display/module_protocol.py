"""The firmware's bus protocol: every command letter, and how messages are built.

All command letters live here, so the rest of the frontend never spells one
out. Cmd mirrors COMMANDS in firmware/splitflapfirmwarev8/transceiver.cpp
(tests/test_module_protocol.py checks the two match); see transceiver.h for
the full message grammar.
"""

import re


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


def message(mod_id, cmd: str, data='') -> str:
    """The bus message m<ID><cmd><data>, without the newline. `mod_id` is a
    module ID (sent as at least two digits) or BROADCAST."""
    target = mod_id if mod_id == BROADCAST else f"{mod_id:02d}"
    return f"m{target}{cmd}{data}"


def dump_reply_pattern(id_pattern: str = r'\d+') -> str:
    """Regex for a dump reply line, m<ID>?:<fields>, with groups for the ID
    and the fields. `id_pattern` narrows the ID (a regex, default any)."""
    return rf'm({id_pattern}){re.escape(Cmd.DUMP_STATE)}:([^\r\n]*)\r?\n'


# Settings key (as stored under settings['modules'][id]) -> firmware command:
#   m<ID>A<0|1>  auto-home on boot
#   m<ID>C<0|1>  motor direction (1 = clockwise)
#   m<ID>F<0|1>  free (release) the motor coils when idle
TOGGLE_COMMANDS = {
    'autoHome': Cmd.SET_AUTO_HOME,
    'motorClockwise': Cmd.SET_MOTOR_CW,
    'motorRelease': Cmd.SET_MOTOR_RELEASE,
}


def toggle_command(mod_id: int, key: str, value: bool) -> str:
    """The bus message that sets boolean setting `key` on module `mod_id`."""
    return message(mod_id, TOGGLE_COMMANDS[key], int(value))


# Settings that are identical on every module. They live once in
# settings['firmware'] and are applied with a broadcast (m*<cmd><value>)
# rather than per module. Key -> firmware command and accepted range:
#   m*S<us>   delay between motor steps during normal moves
#   m*H<us>   delay between motor steps while homing / calibrating
#   m*D<ms>   home-sensor debounce
#   m*E<0|1>  recalculate position every time the home sensor edge is passed
#   m*R<us>   step delay at the start and end of a move (moves ramp between
#             this and the step delay)
#   m*L<n>    steps the ramp takes at each end of a move (0 = no ramp)
#   m*W<ms>   wait, holding the coils, this long after a move before releasing
#   m*P<ms>   power-on stagger: auto-home waits this long per module ID
# The step delays are in microseconds and stored by the firmware as a uint16,
# so 65535 is their ceiling; the ramp steps, settle time and stagger are stored
# as a uint8, so 255 is theirs.
GLOBAL_SETTINGS = {
    'stepDelayUs':       {'cmd': Cmd.SET_STEP_DELAY,         'type': 'int',  'min': 1, 'max': 65535, 'default': 1000},
    'homingStepDelayUs': {'cmd': Cmd.SET_HOMING_STEP_DELAY,  'type': 'int',  'min': 1, 'max': 65535, 'default': 1000},
    'debounceMs':        {'cmd': Cmd.SET_DEBOUNCE_MS,        'type': 'int',  'min': 0, 'max': 65535, 'default': 50},
    'recalculateHome':   {'cmd': Cmd.SET_RECALCULATE_HOME,   'type': 'bool', 'default': True},
    'rampStartDelayUs':  {'cmd': Cmd.SET_RAMP_START_DELAY,   'type': 'int',  'min': 1, 'max': 65535, 'default': 3000},
    'rampSteps':         {'cmd': Cmd.SET_RAMP_STEPS,         'type': 'int',  'min': 0, 'max': 255, 'default': 0},
    'settleMs':          {'cmd': Cmd.SET_SETTLE_MS,          'type': 'int',  'min': 0, 'max': 255, 'default': 0},
    'staggerMs':         {'cmd': Cmd.SET_STAGGER_MS,         'type': 'int',  'min': 0, 'max': 255, 'default': 150},
}


# A broadcast dump (m*?) is answered by each provisioned module in turn, ID
# x DUMP_SLOT_S after the request (or after it finishes a move it was busy
# with). Matches DUMP_SLOT_MS in the firmware.
DUMP_SLOT_S = 0.090


def global_command(key: str, value) -> str:
    """The broadcast message that sets global setting `key` on every module."""
    return message(BROADCAST, GLOBAL_SETTINGS[key]['cmd'], int(value))
