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
