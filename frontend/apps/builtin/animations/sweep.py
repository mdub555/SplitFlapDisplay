from apps.builtin.animations.base import AnimationApp


def generate_pages(grid):
    """Colour band sweeping across the board, then back."""
    colors = 'roygbpw'

    def band(width, color):
        return grid.cells(lambda r, c: color if c < width else ' ')

    return ([band(i, colors[i % 7]) for i in range(1, grid.cols + 1)]
            + [band(i, colors[(i + 3) % 7]) for i in range(grid.cols - 1, 0, -1)])


class SweepApp(AnimationApp):
    key = 'anim_sweep'
    name = 'Sweep'
    icon = '〰️'
    desc = 'Colour sweep'
    order = 160
    default_speed = '0.25'
    min_speed = 0.05
    max_speed = '2'
    speed_step = '0.05'

    def frames(self, grid):
        return generate_pages(grid)
