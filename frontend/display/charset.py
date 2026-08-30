# The ordered set of characters modules can display. Position 0 is blank/home.
#
# IMPORTANT: this must match the firmware's FLAP_CHARS array EXACTLY, in the
# same order. The v7 firmware (splitflap_test.py) and this file agree; the
# v8 firmware (splitflap.cpp) currently does NOT — it uses a different
# character order, which means index-based commands (`+<idx>`, and the old
# custom-tune expected-step math) will show the wrong character if v8 is
# what's actually deployed. Fix that by making one of the two orders match
# before relying on index-based addressing with v8 hardware.
FLAP_CHARS = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$&()-+=;q:%'.,/?*roygbpw"

# The physical " flap is addressed as 'q' in firmware since a literal quote
# character can't safely travel through some serial/JSON boundaries.
QUOTE_CHAR = '"'
QUOTE_SUBSTITUTE = 'q'

# Emoji color tiles used in the compose UI <-> single-char codes on the wire.
COLOR_MAP = {
    '\U0001f7e5': 'r', '\U0001f7e7': 'o', '\U0001f7e8': 'y', '\U0001f7e9': 'g',
    '\U0001f7e6': 'b', '\U0001f7ea': 'p', '\u2b1c': 'w', '\u2b1b': ' ',
}


def flap_index(ch: str) -> int:
    return FLAP_CHARS.find(ch)


def flap_char(index: int) -> str:
    if 0 <= index < len(FLAP_CHARS):
        return FLAP_CHARS[index]
    return '?'
