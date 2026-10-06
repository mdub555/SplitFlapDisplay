"""Wire-protocol details for a module's boolean settings.

Shared by the inspector toggle route and backup restore so the command letters
live in exactly one place. See firmware/splitflapfirmwarev8/transceiver.h for
the full message grammar.
"""

# Settings key (as stored under settings['modules'][id]) -> firmware command:
#   m<ID>A<0|1>  auto-home on boot
#   m<ID>C<0|1>  motor direction (1 = clockwise)
#   m<ID>F<0|1>  free (release) the motor coils when idle
TOGGLE_COMMANDS = {
    'autoHome': 'A',
    'motorClockwise': 'C',
    'motorRelease': 'F',
}


def toggle_command(mod_id: int, key: str, value: bool) -> str:
    """The bus message that sets boolean setting `key` on module `mod_id`."""
    return f"m{mod_id:02d}{TOGGLE_COMMANDS[key]}{int(value)}"


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
    'stepDelayUs':       {'cmd': 'S', 'type': 'int',  'min': 1, 'max': 65535, 'default': 1000},
    'homingStepDelayUs': {'cmd': 'H', 'type': 'int',  'min': 1, 'max': 65535, 'default': 1000},
    'debounceMs':        {'cmd': 'D', 'type': 'int',  'min': 0, 'max': 65535, 'default': 50},
    'recalculateHome':   {'cmd': 'E', 'type': 'bool', 'default': True},
    'rampStartDelayUs':  {'cmd': 'R', 'type': 'int',  'min': 1, 'max': 65535, 'default': 3000},
    'rampSteps':         {'cmd': 'L', 'type': 'int',  'min': 0, 'max': 255, 'default': 0},
    'settleMs':          {'cmd': 'W', 'type': 'int',  'min': 0, 'max': 255, 'default': 0},
    'staggerMs':         {'cmd': 'P', 'type': 'int',  'min': 0, 'max': 255, 'default': 150},
}


# A broadcast dump (m*?) is answered by each provisioned module in turn, ID
# x DUMP_SLOT_S after the request (or after it finishes a move it was busy
# with). Matches DUMP_SLOT_MS in the firmware.
DUMP_SLOT_S = 0.090


def global_command(key: str, value) -> str:
    """The broadcast message that sets global setting `key` on every module."""
    return f"m*{GLOBAL_SETTINGS[key]['cmd']}{int(value)}"
