import random

from config import GRID_ROWS, GRID_COLS, NUM_MODULES


def format_lines(*lines) -> str:
    """Center-pad any number of text rows into one NUM_MODULES-length page
    string. Extra rows beyond GRID_ROWS are dropped; missing rows are blank.
    This replaces the old format_lines(l1, l2, l3) which hardcoded 3 rows."""
    rows = list(lines)[:GRID_ROWS]
    while len(rows) < GRID_ROWS:
        rows.append('')
    return ''.join(r.center(GRID_COLS)[:GRID_COLS] for r in rows)


def get_animation_order(style='ltr'):
    """Return the NUM_MODULES module indices in the requested send order."""

    def m(r, c):
        return r * GRID_COLS + c

    if style == 'rtl':
        return list(range(NUM_MODULES - 1, -1, -1))

    if style == 'center_out':
        order, seen = [], set()
        mid_col = GRID_COLS // 2
        for d in range(GRID_COLS):
            for r in range(GRID_ROWS):
                cols = [mid_col] if d == 0 else [mid_col - d, mid_col + d]
                for c in cols:
                    if 0 <= c < GRID_COLS:
                        idx = m(r, c)
                        if idx not in seen:
                            seen.add(idx)
                            order.append(idx)
        return order

    if style == 'outside_in':
        return list(reversed(get_animation_order('center_out')))

    if style == 'spiral':
        vis = [[False] * GRID_COLS for _ in range(GRID_ROWS)]
        order = []
        top, bottom, left, right = 0, GRID_ROWS - 1, 0, GRID_COLS - 1
        while top <= bottom and left <= right:
            for c in range(left, right + 1):
                if not vis[top][c]:
                    vis[top][c] = True
                    order.append(m(top, c))
            for r in range(top + 1, bottom + 1):
                if not vis[r][right]:
                    vis[r][right] = True
                    order.append(m(r, right))
            if top < bottom:
                for c in range(right - 1, left - 1, -1):
                    if not vis[bottom][c]:
                        vis[bottom][c] = True
                        order.append(m(bottom, c))
            if left < right:
                for r in range(bottom - 1, top, -1):
                    if not vis[r][left]:
                        vis[r][left] = True
                        order.append(m(r, left))
            top += 1
            bottom -= 1
            left += 1
            right -= 1
        return order

    if style == 'diagonal':
        order, seen = [], set()
        for d in range(GRID_ROWS + GRID_COLS - 1):
            for r in range(GRID_ROWS):
                c = d - r
                if 0 <= c < GRID_COLS:
                    idx = m(r, c)
                    if idx not in seen:
                        seen.add(idx)
                        order.append(idx)
        return order

    if style == 'anti_diagonal':
        order, seen = [], set()
        for d in range(GRID_ROWS + GRID_COLS - 1):
            for r in range(GRID_ROWS):
                c = (GRID_COLS - 1 - d) + r
                if 0 <= c < GRID_COLS:
                    idx = m(r, c)
                    if idx not in seen:
                        seen.add(idx)
                        order.append(idx)
        return order

    if style == 'random':
        return random.sample(range(NUM_MODULES), NUM_MODULES)

    if style == 'rain':
        return [m(r, c) for r in range(GRID_ROWS) for c in range(GRID_COLS)]

    if style == 'reverse_rain':
        return [m(r, c) for r in range(GRID_ROWS - 1, -1, -1) for c in range(GRID_COLS)]

    if style == 'columns':
        return [m(r, c) for c in range(GRID_COLS) for r in range(GRID_ROWS)]

    if style == 'columns_rtl':
        return [m(r, c) for c in range(GRID_COLS - 1, -1, -1) for r in range(GRID_ROWS)]

    if style == 'alternating':
        # Zig-zag: direction alternates per row, interleaved column by column.
        order = []
        for c in range(GRID_COLS):
            for r in range(GRID_ROWS):
                col = c if r % 2 == 0 else (GRID_COLS - 1 - c)
                order.append(m(r, col))
        return order

    return list(range(NUM_MODULES))  # default: ltr
