from apps.builtin.animations.base import AnimationApp
from config import GRID_ROWS, GRID_COLS


def generate_pages():
    """Colour band sweeping across the board, then back."""
    colors = 'roygbpw'

    def band(width, color):
        return ''.join(color if c < width else ' ' for r in range(GRID_ROWS) for c in range(GRID_COLS))

    return ([band(i, colors[i % 7]) for i in range(1, GRID_COLS + 1)]
            + [band(i, colors[(i + 3) % 7]) for i in range(GRID_COLS - 1, 0, -1)])


class SweepApp(AnimationApp):
    key = 'anim_sweep'
    name = 'Sweep'
    icon = '〰️'
    desc = 'Colour sweep'
    default_speed = '0.25'
    min_speed = 0.05
    max_speed = '2'
    speed_step = '0.05'

    def frames(self):
        return generate_pages()
