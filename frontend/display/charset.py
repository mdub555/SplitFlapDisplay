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


NUM_FLAPS = len(FLAP_CHARS)


def normalize_text(text: str, raw: bool = False) -> str:
    """`text` the way the modules take it: uppercased (unless `raw`), colour
    emoji as their codes, and " as its substitute. Characters with no flap
    are left as they are."""
    if not raw:
        text = text.upper()
    for emoji, code in COLOR_MAP.items():
        text = text.replace(emoji, code)
    return text.replace(QUOTE_CHAR, QUOTE_SUBSTITUTE)


def to_flap_char(value):
    """One typed character, normalized like a page of text, or None unless
    the result is a single character that has a flap."""
    if not isinstance(value, str):
        return None
    char = normalize_text(value)
    return char if len(char) == 1 and char in FLAP_CHARS else None
