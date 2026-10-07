from apps.builtin.animations.base import AnimationApp
from config import GRID_ROWS, GRID_COLS


def generate_pages():
    """7 pages cycling the colour tiles across the board."""
    colors = 'roygbpw'
    return [''.join(colors[(c + off) % 7] for r in range(GRID_ROWS) for c in range(GRID_COLS))
            for off in range(7)]


class RainbowApp(AnimationApp):
    key = 'anim_rainbow'
    name = 'Rainbow'
    icon = '🌈'
    desc = 'Colour wave'
    default_speed = '0.4'

    def frames(self):
        return generate_pages()
