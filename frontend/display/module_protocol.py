"""Wire-protocol details for a module's boolean settings.

Shared by the inspector toggle route and backup restore so the command letters
live in exactly one place. See firmware/splitflapfirmwarev8/tranceiver.h for
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
# Both delays are stored by the firmware as a uint8, so 255 is their ceiling.
GLOBAL_SETTINGS = {
    'stepDelay':       {'cmd': 'k', 'type': 'int',  'min': 1, 'max': 255, 'default': 1},
    'homingStepDelay': {'cmd': 'l', 'type': 'int',  'min': 1, 'max': 255, 'default': 1},
    'debounceMs':      {'cmd': 'b', 'type': 'int',  'min': 0, 'max': 65535, 'default': 50},
    'recalculateHome': {'cmd': 'j', 'type': 'bool', 'default': True},
}


def global_command(key: str, value) -> str:
    """The broadcast message that sets global setting `key` on every module."""
    return f"m*{GLOBAL_SETTINGS[key]['cmd']}{int(value)}"
