# The ordered set of characters modules can display. Position 0 is blank/home.
#
# IMPORTANT: this must match the firmware's FLAP_CHARS array EXACTLY, in the
# same order. The v8 firmware and this file agree.
FLAP_CHARS = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789?!,.q:@#$&()+-*/=%dhwroygbp"

# The physical " flap is addressed as 'q' in firmware since a literal quote
# character can't safely travel through some serial/JSON boundaries.
QUOTE_CHAR = '"'
QUOTE_SUBSTITUTE = 'q'

# Emoji color tiles used in the compose UI <-> single-char codes on the wire.
COLOR_MAP = {
    '\U0001f7e5': 'r', '\U0001f7e7': 'o', '\U0001f7e8': 'y', '\U0001f7e9': 'g',
    '\U0001f7e6': 'b', '\U0001f7ea': 'p', '\u2b1c': 'w', '\u2b1b': ' ',
    '\u00B0': 'd', '\u2665': 'h',
}


def flap_index(ch: str) -> int:
    return FLAP_CHARS.find(ch)


def flap_char(index: int) -> str:
    if 0 <= index < len(FLAP_CHARS):
        return FLAP_CHARS[index]
    return '?'
