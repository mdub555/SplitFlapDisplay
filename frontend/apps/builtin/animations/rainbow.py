from apps.builtin.animations.base import AnimationApp


def generate_pages(grid):
    """7 pages cycling the colour tiles across the board."""
    colors = 'roygbpw'
    return [grid.cells(lambda r, c: colors[(c + off) % 7]) for off in range(7)]


class RainbowApp(AnimationApp):
    key = 'anim_rainbow'
    name = 'Rainbow'
    icon = '🌈'
    desc = 'Colour wave'
    order = 150
    default_speed = '0.4'

    def frames(self, grid):
        return generate_pages(grid)
