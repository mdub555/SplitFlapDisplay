# The ordered set of characters modules can display. Position 0 is blank/home.
#
# IMPORTANT: this must match the firmware's FLAP_CHARS array EXACTLY, in the
# same order. The v8 firmware and this file agree.
FLAP_CHARS = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789?!,.q:@#$&()+-*/=%dhwroygbp"

# The physical " flap is addressed as 'q' in firmware since a literal quote
# character can't safely travel through some serial/JSON boundaries.
QUOTE_CHAR = '"'
QUOTE_SUBSTITUTE = 'q'

# The colour tiles the compose UI offers: (emoji, code on the wire, name).
# Black is the blank flap.
COLOR_TILES = [
    ('\U0001f7e5', 'r', 'Red'), ('\U0001f7e7', 'o', 'Orange'), ('\U0001f7e8', 'y', 'Yellow'),
    ('\U0001f7e9', 'g', 'Green'), ('\U0001f7e6', 'b', 'Blue'), ('\U0001f7ea', 'p', 'Purple'),
    ('\u2b1c', 'w', 'White'), ('\u2b1b', ' ', 'Black'),
]

# Characters typed or shown in the UI -> their code on the wire.
COLOR_MAP = {
    **{emoji: code for emoji, code, _ in COLOR_TILES},
    '\u00B0': 'd', '\u2665': 'h',
}

# How the UI shows each code that isn't shown as itself.
DISPLAY_CHARS = {
    **{code: shown for shown, code in COLOR_MAP.items() if code != ' '},
    QUOTE_SUBSTITUTE: QUOTE_CHAR,
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
