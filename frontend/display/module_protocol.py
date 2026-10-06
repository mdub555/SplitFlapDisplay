"""Wire-protocol details for a module's boolean settings.

Shared by the inspector toggle route and backup restore so the command letters
live in exactly one place. See firmware/splitflapfirmwarev8/transceiver.h for
the full message grammar.
"""

# Settings key (as stored under settings['modules'][id]) -> firmware command:
#   m<ID>a<0|1>  auto-home on boot
#   m<ID>w<0|1>  motor direction (1 = clockwise)
#   m<ID>r<0|1>  release the motor coils when idle
TOGGLE_COMMANDS = {
    'autoHome': 'a',
    'motorClockwise': 'w',
    'motorRelease': 'r',
}


def toggle_command(mod_id: int, key: str, value: bool) -> str:
    """The bus message that sets boolean setting `key` on module `mod_id`."""
    return f"m{mod_id:02d}{TOGGLE_COMMANDS[key]}{int(value)}"


# Settings that are identical on every module. They live once in
# settings['firmware'] and are applied with a broadcast (m*<cmd><value>)
# rather than per module. Key -> firmware command and accepted range:
#   m*k<ms>   delay between motor steps during normal moves
#   m*l<ms>   delay between motor steps while homing / calibrating
#   m*b<ms>   home-sensor debounce
#   m*j<0|1>  recalculate position every time the home sensor is passed
#   m*u<ms>   step delay at the start and end of a move (moves ramp between
#             this and the step delay)
#   m*n<n>    steps the ramp takes at each end of a move (0 = no ramp)
#   m*e<ms>   hold the coils this long after a move before releasing them
#   m*y<ms>   startup stagger: auto-home waits this long per module ID
# The delays, ramp steps, settle time and stagger are stored by the firmware
# as a uint8, so 255 is their ceiling.
GLOBAL_SETTINGS = {
    'stepDelay':       {'cmd': 'k', 'type': 'int',  'min': 1, 'max': 255, 'default': 1},
    'homingStepDelay': {'cmd': 'l', 'type': 'int',  'min': 1, 'max': 255, 'default': 1},
    'debounceMs':      {'cmd': 'b', 'type': 'int',  'min': 0, 'max': 65535, 'default': 50},
    'recalculateHome': {'cmd': 'j', 'type': 'bool', 'default': True},
    'rampStartDelay':  {'cmd': 'u', 'type': 'int',  'min': 1, 'max': 255, 'default': 3},
    'rampSteps':       {'cmd': 'n', 'type': 'int',  'min': 0, 'max': 255, 'default': 0},
    'settleMs':        {'cmd': 'e', 'type': 'int',  'min': 0, 'max': 255, 'default': 0},
    'staggerMs':       {'cmd': 'y', 'type': 'int',  'min': 0, 'max': 255, 'default': 150},
}


# A broadcast dump (m*d) is answered by each provisioned module in turn, ID
# x DUMP_SLOT_S after the request (or after it finishes a move it was busy
# with). Matches DUMP_SLOT_MS in the firmware.
DUMP_SLOT_S = 0.075


def global_command(key: str, value) -> str:
    """The broadcast message that sets global setting `key` on every module."""
    return f"m*{GLOBAL_SETTINGS[key]['cmd']}{int(value)}"
