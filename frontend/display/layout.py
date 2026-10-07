import random
from collections import namedtuple

from config import GRID_ROWS, GRID_COLS, NUM_MODULES


def format_lines(*lines) -> str:
    """Center-pad any number of text rows into one NUM_MODULES-length page
    string. Extra rows beyond GRID_ROWS are dropped; missing rows are blank."""
    rows = list(lines)[:GRID_ROWS]
    rows += [''] * (GRID_ROWS - len(rows))
    return ''.join(r.center(GRID_COLS)[:GRID_COLS] for r in rows)


# --- Animation orders --------------------------------------------------------
# Each returns every module index once, in the order the modules should start
# moving.

def _cell(row, col):
    return row * GRID_COLS + col


def _left_to_right():
    return list(range(NUM_MODULES))


def _right_to_left():
    return list(range(NUM_MODULES - 1, -1, -1))


def _center_out():
    """Column by column outwards from the middle, top to bottom in each."""
    mid = GRID_COLS // 2
    order = []
    for d in range(GRID_COLS):
        cols = [mid] if d == 0 else [mid - d, mid + d]
        for r in range(GRID_ROWS):
            order += [_cell(r, c) for c in cols if 0 <= c < GRID_COLS]
    return order


def _outside_in():
    return _center_out()[::-1]


def _spiral():
    """Clockwise round the edge, then each ring inside it."""
    order = []
    top, bottom, left, right = 0, GRID_ROWS - 1, 0, GRID_COLS - 1
    while top <= bottom and left <= right:
        order += [_cell(top, c) for c in range(left, right + 1)]
        order += [_cell(r, right) for r in range(top + 1, bottom + 1)]
        if top < bottom:
            order += [_cell(bottom, c) for c in range(right - 1, left - 1, -1)]
        if left < right:
            order += [_cell(r, left) for r in range(bottom - 1, top, -1)]
        top, bottom, left, right = top + 1, bottom - 1, left + 1, right - 1
    return order


def _diagonal():
    """Diagonals from the top left corner."""
    return [_cell(r, d - r) for d in range(GRID_ROWS + GRID_COLS - 1)
            for r in range(GRID_ROWS) if 0 <= d - r < GRID_COLS]


def _anti_diagonal():
    """Diagonals from the top right corner."""
    return [_cell(r, GRID_COLS - 1 - d + r) for d in range(GRID_ROWS + GRID_COLS - 1)
            for r in range(GRID_ROWS) if 0 <= GRID_COLS - 1 - d + r < GRID_COLS]


def _random():
    return random.sample(range(NUM_MODULES), NUM_MODULES)


def _rain():
    return [_cell(r, c) for r in range(GRID_ROWS) for c in range(GRID_COLS)]


def _reverse_rain():
    return [_cell(r, c) for r in range(GRID_ROWS - 1, -1, -1) for c in range(GRID_COLS)]


def _columns():
    return [_cell(r, c) for c in range(GRID_COLS) for r in range(GRID_ROWS)]


def _columns_rtl():
    return [_cell(r, c) for c in range(GRID_COLS - 1, -1, -1) for r in range(GRID_ROWS)]


def _alternating():
    """Zig-zag: direction alternates per row, interleaved column by column."""
    return [_cell(r, c if r % 2 == 0 else GRID_COLS - 1 - c)
            for c in range(GRID_COLS) for r in range(GRID_ROWS)]


Style = namedtuple('Style', 'label order')

# Every animation order by name, with the label the UI shows for it, in the
# order the UI lists them.
STYLES = {
    'ltr':           Style('Left → Right', _left_to_right),
    'rtl':           Style('Right → Left', _right_to_left),
    'diagonal':      Style('Diagonal ↘', _diagonal),
    'anti_diagonal': Style('Diagonal ↙', _anti_diagonal),
    'center_out':    Style('Center Out', _center_out),
    'outside_in':    Style('Outside In', _outside_in),
    'random':        Style('Random', _random),
    'rain':          Style('Rain (Top→Bot)', _rain),
    'reverse_rain':  Style('Rain (Bot→Top)', _reverse_rain),
    'spiral':        Style('Spiral', _spiral),
    'columns':       Style('Columns', _columns),
    'columns_rtl':   Style('Columns (R→L)', _columns_rtl),
    'alternating':   Style('Alt (↔↔↔)', _alternating),
}


def get_animation_order(style='ltr'):
    """The NUM_MODULES module indices in the order `style` sends them. An
    unknown style is left to right."""
    return STYLES.get(style, STYLES['ltr']).order()
