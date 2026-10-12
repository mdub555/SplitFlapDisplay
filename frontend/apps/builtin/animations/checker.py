from apps.builtin.animations.base import AnimationApp


def generate_pages(grid):
    """Alternating two-colour checkerboard that swaps through several palettes."""
    def board(even, odd):
        return grid.cells(lambda r, c: even if (r + c) % 2 == 0 else odd)

    pages = []
    for a, b in [('r', 'b'), ('o', 'p'), ('y', 'g'), ('r', 'w'), ('g', 'b')]:
        pages += [board(a, b), board(b, a)]
    return pages


class CheckerApp(AnimationApp):
    key = 'anim_checker'
    name = 'Checker'
    icon = '🎭'
    desc = 'Checkerboard'
    order = 180
    default_speed = '0.6'

    def frames(self, grid):
        return generate_pages(grid)
