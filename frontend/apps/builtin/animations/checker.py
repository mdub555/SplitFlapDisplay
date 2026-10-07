from apps.builtin.animations.base import AnimationApp
from config import GRID_ROWS, GRID_COLS


def generate_pages():
    """Alternating two-colour checkerboard that swaps through several palettes."""
    def board(even, odd):
        return ''.join(even if (r + c) % 2 == 0 else odd for r in range(GRID_ROWS) for c in range(GRID_COLS))

    pages = []
    for a, b in [('r', 'b'), ('o', 'p'), ('y', 'g'), ('r', 'w'), ('g', 'b')]:
        pages += [board(a, b), board(b, a)]
    return pages


class CheckerApp(AnimationApp):
    key = 'anim_checker'
    name = 'Checker'
    icon = '🎭'
    desc = 'Checkerboard'
    default_speed = '0.6'

    def frames(self):
        return generate_pages()
